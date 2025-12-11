#!/usr/bin/env python3
"""
MacWinControl - Automatische scherm-switching versie
Beweeg je muis naar de rand en hij gaat automatisch naar Windows!
"""

import json
import socket
import threading
import time
import sys
import subprocess
from dataclasses import dataclass
from typing import Optional, Callable, Tuple

# Check for dependencies
try:
    from pynput import mouse, keyboard
    from pynput.mouse import Controller as MouseController
except ImportError:
    print("Installing pynput...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput", "-q"])
    from pynput import mouse, keyboard
    from pynput.mouse import Controller as MouseController

try:
    import AppKit
    from AppKit import NSScreen
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False
    print("⚠️  AppKit not available")


class ScreenManager:
    """Manage screen bounds and edge detection."""
    
    def __init__(self):
        self.screens = []
        self.total_bounds = (0, 0, 1920, 1080)  # minX, minY, maxX, maxY
        self.update_screens()
    
    def update_screens(self):
        """Update screen information."""
        self.screens = []
        
        if HAS_APPKIT:
            for screen in NSScreen.screens():
                frame = screen.frame()
                self.screens.append({
                    'x': int(frame.origin.x),
                    'y': int(frame.origin.y),
                    'width': int(frame.size.width),
                    'height': int(frame.size.height)
                })
        else:
            # Fallback
            self.screens = [{'x': 0, 'y': 0, 'width': 1920, 'height': 1080}]
        
        if self.screens:
            min_x = min(s['x'] for s in self.screens)
            min_y = min(s['y'] for s in self.screens)
            max_x = max(s['x'] + s['width'] for s in self.screens)
            max_y = max(s['y'] + s['height'] for s in self.screens)
            self.total_bounds = (min_x, min_y, max_x, max_y)
        
        print(f"📺 Gedetecteerd: {len(self.screens)} scherm(en)")
        for i, s in enumerate(self.screens):
            print(f"   Scherm {i+1}: {s['width']}x{s['height']} op ({s['x']}, {s['y']})")
    
    def is_at_edge(self, x: int, y: int, edge: str, threshold: int = 3) -> bool:
        """Check if position is at screen edge."""
        min_x, min_y, max_x, max_y = self.total_bounds
        
        if edge == 'right':
            return x >= max_x - threshold
        elif edge == 'left':
            return x <= min_x + threshold
        return False
    
    def get_center(self) -> Tuple[int, int]:
        """Get center of primary screen."""
        if self.screens:
            s = self.screens[0]
            return (s['x'] + s['width'] // 2, s['y'] + s['height'] // 2)
        return (960, 540)


class NetworkServer:
    """TCP Server for Windows client communication."""
    
    def __init__(self, port: int = 52525):
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_name: str = ""
        self.running = False
        self.connected = False
        self.on_client_connected: Optional[Callable[[str], None]] = None
        self.on_client_disconnected: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()
        
    def get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def start(self):
        """Start the server."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(1)
        
        print(f"✅ Server gestart op {self.get_local_ip()}:{self.port}")
        
        threading.Thread(target=self._accept_loop, daemon=True).start()
    
    def _accept_loop(self):
        """Accept incoming connections."""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client, addr = self.server_socket.accept()
                print(f"📱 Client verbonden vanaf {addr}")
                
                with self._lock:
                    self.client_socket = client
                    self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                self._handle_client()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Accept error: {e}")
                break
    
    def _handle_client(self):
        """Handle client connection."""
        try:
            hello = {"type": "hello", "version": "1.0", "name": socket.gethostname()}
            self._send(hello)
            
            buffer = ""
            while self.running and self.client_socket:
                try:
                    self.client_socket.settimeout(0.1)
                    data = self.client_socket.recv(4096)
                    if not data:
                        break
                    
                    buffer += data.decode('utf-8')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line:
                            self._process_message(line)
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"❌ Receive error: {e}")
                    break
        finally:
            self.connected = False
            if self.on_client_disconnected:
                self.on_client_disconnected()
            with self._lock:
                self.client_socket = None
            self.client_name = ""
            print("📴 Verbinding verbroken - wacht op herverbinding...")
    
    def _process_message(self, message: str):
        """Process incoming message."""
        try:
            msg = json.loads(message)
            msg_type = msg.get("type", "")
            
            if msg_type == "hello":
                self.client_name = msg.get("name", "Windows PC")
                print(f"👋 Verbonden met: {self.client_name}")
                self._send({"type": "connected"})
                self.connected = True
                if self.on_client_connected:
                    self.on_client_connected(self.client_name)
            elif msg_type == "ping":
                self._send({"type": "pong"})
        except json.JSONDecodeError:
            pass
    
    def _send(self, obj: dict):
        """Send JSON message to client."""
        with self._lock:
            if self.client_socket:
                try:
                    data = json.dumps(obj) + "\n"
                    self.client_socket.send(data.encode('utf-8'))
                except:
                    pass
    
    def send_event(self, event: dict):
        """Send input event to client."""
        if self.connected:
            self._send(event)
    
    def stop(self):
        """Stop the server."""
        self.running = False
        with self._lock:
            if self.client_socket:
                self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()


class InputCapture:
    """Capture and forward mouse/keyboard input with automatic edge switching."""
    
    def __init__(self, server: NetworkServer, screen_manager: ScreenManager, windows_position: str = 'right'):
        self.server = server
        self.screen_manager = screen_manager
        self.windows_position = windows_position
        
        self.is_windows_mode = False
        self.mouse_controller = MouseController()
        
        self.windows_x = 0
        self.windows_y = 540
        
        self.mouse_listener: Optional[mouse.Listener] = None
        self.keyboard_listener: Optional[keyboard.Listener] = None
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        self.last_x = 0
        self.last_y = 0
        
    def start_edge_detection(self):
        """Start monitoring for edge hits."""
        print(f"🖱️  Edge detection actief - Windows staat {self.windows_position}s")
        threading.Thread(target=self._edge_poll_loop, daemon=True).start()
    
    def _edge_poll_loop(self):
        """Poll mouse position for edge detection."""
        while True:
            if not self.is_windows_mode and self.server.connected:
                try:
                    pos = self.mouse_controller.position
                    x, y = int(pos[0]), int(pos[1])
                    
                    if self.screen_manager.is_at_edge(x, y, self.windows_position):
                        self._switch_to_windows(y)
                except:
                    pass
            time.sleep(0.01)  # 100fps polling
    
    def _switch_to_windows(self, y_pos: int):
        """Switch to Windows mode."""
        if self.is_windows_mode:
            return
        
        self.is_windows_mode = True
        print()
        print("🖥️  ══════════════════════════════════════")
        print("🖥️  WINDOWS MODE - Ctrl+Alt+M om terug te gaan")
        print("🖥️  ══════════════════════════════════════")
        
        if self.windows_position == 'right':
            self.windows_x = 5
        else:
            self.windows_x = 1915
        self.windows_y = y_pos
        
        self.server.send_event({"type": "mode_switch", "active": True})
        self._start_capture()
    
    def _switch_to_mac(self):
        """Switch back to Mac mode."""
        if not self.is_windows_mode:
            return
        
        self.is_windows_mode = False
        print()
        print("🍎 ══════════════════════════════════════")
        print("🍎 MAC MODE")
        print("🍎 ══════════════════════════════════════")
        
        self.server.send_event({"type": "mode_switch", "active": False})
        self._stop_capture()
        
        # Move cursor back to Mac
        min_x, min_y, max_x, max_y = self.screen_manager.total_bounds
        if self.windows_position == 'right':
            new_x = max_x - 100
        else:
            new_x = min_x + 100
        
        self.mouse_controller.position = (new_x, self.windows_y)
    
    def _start_capture(self):
        """Start capturing input."""
        self.last_x, self.last_y = self.mouse_controller.position
        
        self.mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            suppress=True
        )
        self.mouse_listener.start()
        
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
            suppress=True
        )
        self.keyboard_listener.start()
    
    def _stop_capture(self):
        """Stop capturing input."""
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
    
    def _on_move(self, x, y):
        """Handle mouse move."""
        if not self.is_windows_mode:
            return
        
        dx = x - self.last_x
        dy = y - self.last_y
        self.last_x = x
        self.last_y = y
        
        self.windows_x += int(dx)
        self.windows_y += int(dy)
        
        self.windows_x = max(0, min(self.windows_x, 3840))
        self.windows_y = max(0, min(self.windows_y, 2160))
        
        # Check if should return to Mac
        if self.windows_position == 'right' and self.windows_x <= 2:
            self._switch_to_mac()
            return
        elif self.windows_position == 'left' and self.windows_x >= 1918:
            self._switch_to_mac()
            return
        
        self.server.send_event({
            "type": "mouse_move",
            "x": self.windows_x,
            "y": self.windows_y,
            "timestamp": int(time.time() * 1000)
        })
    
    def _on_click(self, x, y, button, pressed):
        """Handle mouse click."""
        if not self.is_windows_mode:
            return
        
        button_name = {
            mouse.Button.left: "left",
            mouse.Button.right: "right",
            mouse.Button.middle: "middle"
        }.get(button, "left")
        
        self.server.send_event({
            "type": "mouse_button",
            "button": button_name,
            "action": "down" if pressed else "up",
            "x": self.windows_x,
            "y": self.windows_y,
            "timestamp": int(time.time() * 1000)
        })
    
    def _on_scroll(self, x, y, dx, dy):
        """Handle mouse scroll."""
        if not self.is_windows_mode:
            return
        
        self.server.send_event({
            "type": "mouse_scroll",
            "deltaX": int(dx * 120),
            "deltaY": int(dy * 120),
            "timestamp": int(time.time() * 1000)
        })
    
    def _on_key_press(self, key):
        """Handle key press."""
        if not self.is_windows_mode:
            return
        
        # Track modifiers
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = True
        
        # Check for exit hotkey (Ctrl+Alt+M)
        try:
            if self.ctrl_pressed and self.alt_pressed and hasattr(key, 'char') and key.char and key.char.lower() == 'm':
                self._switch_to_mac()
                return
        except:
            pass
        
        vk = self._key_to_vk(key)
        self.server.send_event({
            "type": "key",
            "keyCode": vk,
            "action": "down",
            "modifiers": {"shift": False, "control": self.ctrl_pressed, "alt": self.alt_pressed, "meta": False},
            "timestamp": int(time.time() * 1000)
        })
    
    def _on_key_release(self, key):
        """Handle key release."""
        if not self.is_windows_mode:
            return
        
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False
        
        vk = self._key_to_vk(key)
        self.server.send_event({
            "type": "key",
            "keyCode": vk,
            "action": "up",
            "modifiers": {"shift": False, "control": self.ctrl_pressed, "alt": self.alt_pressed, "meta": False},
            "timestamp": int(time.time() * 1000)
        })
    
    def _key_to_vk(self, key) -> int:
        """Convert pynput key to Windows virtual key code."""
        special = {
            keyboard.Key.enter: 13, keyboard.Key.tab: 9, keyboard.Key.backspace: 8,
            keyboard.Key.esc: 27, keyboard.Key.space: 32,
            keyboard.Key.shift: 16, keyboard.Key.shift_l: 16, keyboard.Key.shift_r: 16,
            keyboard.Key.ctrl: 17, keyboard.Key.ctrl_l: 17, keyboard.Key.ctrl_r: 17,
            keyboard.Key.alt: 18, keyboard.Key.alt_l: 18, keyboard.Key.alt_r: 18,
            keyboard.Key.cmd: 91, keyboard.Key.cmd_l: 91, keyboard.Key.cmd_r: 92,
            keyboard.Key.caps_lock: 20,
            keyboard.Key.left: 37, keyboard.Key.up: 38, keyboard.Key.right: 39, keyboard.Key.down: 40,
            keyboard.Key.delete: 46, keyboard.Key.home: 36, keyboard.Key.end: 35,
            keyboard.Key.page_up: 33, keyboard.Key.page_down: 34,
            keyboard.Key.f1: 112, keyboard.Key.f2: 113, keyboard.Key.f3: 114, keyboard.Key.f4: 115,
            keyboard.Key.f5: 116, keyboard.Key.f6: 117, keyboard.Key.f7: 118, keyboard.Key.f8: 119,
            keyboard.Key.f9: 120, keyboard.Key.f10: 121, keyboard.Key.f11: 122, keyboard.Key.f12: 123,
        }
        if key in special:
            return special[key]
        try:
            if hasattr(key, 'char') and key.char:
                return ord(key.char.upper())
        except:
            pass
        return 0
    
    def set_windows_position(self, position: str):
        """Set which side Windows is on."""
        self.windows_position = position
        print(f"📍 Windows positie: {position}")


class MacWinControl:
    """Main application."""
    
    def __init__(self):
        self.screen_manager = ScreenManager()
        self.server = NetworkServer()
        self.input_capture = InputCapture(self.server, self.screen_manager, 'right')
        
        self.server.on_client_connected = self._on_connected
        self.server.on_client_disconnected = self._on_disconnected
        
    def _on_connected(self, name: str):
        print()
        print("╔══════════════════════════════════════════════════╗")
        print(f"║  ✅ VERBONDEN MET {name.upper():^30} ║")
        print("╚══════════════════════════════════════════════════╝")
        print()
        print("🖱️  Beweeg je muis naar de RECHTER rand om Windows te bedienen")
        print("⌨️  Druk Ctrl+Alt+M om terug te gaan naar Mac")
        print()
    
    def _on_disconnected(self):
        if self.input_capture.is_windows_mode:
            self.input_capture._switch_to_mac()
    
    def run(self):
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║         MacWinControl - Auto Switch              ║")
        print("║     Beweeg muis naar rand → switch naar Windows  ║")
        print("╚══════════════════════════════════════════════════╝")
        print()
        
        self.server.start()
        self.input_capture.start_edge_detection()
        
        print()
        print(f"📡 IP Adres: {self.server.get_local_ip()}")
        print(f"📡 Poort: {self.server.port}")
        print()
        print("⏳ Wacht op Windows client...")
        print("   Start de Windows app en voer dit IP adres in!")
        print()
        print("Commando's:  l=links  r=rechts  q=stoppen")
        print()
        
        try:
            while True:
                cmd = input().strip().lower()
                if cmd == 'q':
                    break
                elif cmd == 'l':
                    self.input_capture.set_windows_position('left')
                elif cmd == 'r':
                    self.input_capture.set_windows_position('right')
        except KeyboardInterrupt:
            pass
        finally:
            if self.input_capture.is_windows_mode:
                self.input_capture._switch_to_mac()
            self.server.stop()
            print("👋 Tot ziens!")


def main():
    import platform
    if platform.system() != 'Darwin':
        print("❌ Dit script is alleen voor macOS!")
        sys.exit(1)
    
    print()
    print("⚠️  BELANGRIJK: Accessibility Permissions nodig!")
    print()
    print("   1. Open Systeemvoorkeuren → Privacy en beveiliging")
    print("   2. Klik op 'Toegankelijkheid'")
    print("   3. Voeg 'Terminal' toe (of je IDE)")
    print()
    
    try:
        subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'], check=False)
    except:
        pass
    
    input("Druk Enter als de permissies zijn ingesteld...")
    
    app = MacWinControl()
    app.run()


if __name__ == "__main__":
    main()
