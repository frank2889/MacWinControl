#!/usr/bin/env python3
"""
MacWinControl - Simple Terminal Version
"""

import json
import socket
import threading
import time
import sys
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController

print("=" * 50)
print("  MacWinControl - Terminal Versie")
print("=" * 50)

# Get local IP
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

class Server:
    def __init__(self):
        self.socket = None
        self.client = None
        self.connected = False
        self.running = True
        
    def start(self, port=52525):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', port))
        self.socket.listen(1)
        print(f"\n📡 Server draait op: {get_ip()}:{port}")
        print("   Voer dit IP in op je Windows PC!\n")
        threading.Thread(target=self._accept, daemon=True).start()
        
    def _accept(self):
        while self.running:
            try:
                self.socket.settimeout(1)
                client, addr = self.socket.accept()
                print(f"✅ Windows verbonden vanaf {addr[0]}")
                self.client = client
                self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._handle()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error: {e}")
                    
    def _handle(self):
        try:
            self._send({"type": "hello", "version": "1.0", "name": socket.gethostname()})
            buffer = ""
            while self.running and self.client:
                try:
                    self.client.settimeout(0.1)
                    data = self.client.recv(4096)
                    if not data:
                        break
                    buffer += data.decode()
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line:
                            msg = json.loads(line)
                            if msg.get("type") == "hello":
                                print(f"👋 Verbonden met: {msg.get('name', 'Windows')}")
                                self._send({"type": "connected"})
                                self.connected = True
                            elif msg.get("type") == "ping":
                                self._send({"type": "pong"})
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.connected = False
            self.client = None
            print("📴 Verbinding verbroken")
            
    def _send(self, obj):
        if self.client:
            try:
                self.client.send((json.dumps(obj) + "\n").encode())
            except:
                pass
                
    def send_event(self, event):
        if self.connected:
            self._send(event)
            
    def stop(self):
        self.running = False
        if self.client:
            self.client.close()
        if self.socket:
            self.socket.close()


class InputHandler:
    def __init__(self, server):
        self.server = server
        self.mouse_ctrl = MouseController()
        self.is_windows_mode = False
        self.win_x = 960
        self.win_y = 540
        self.last_x = 0
        self.last_y = 0
        self.ctrl = False
        self.alt = False
        self.mouse_listener = None
        self.kb_listener = None
        
        # Get screen bounds
        try:
            from AppKit import NSScreen
            screen = NSScreen.mainScreen().frame()
            self.screen_width = int(screen.size.width)
            self.screen_height = int(screen.size.height)
        except:
            self.screen_width = 1920
            self.screen_height = 1080
        print(f"📺 Scherm: {self.screen_width}x{self.screen_height}")
        
    def start_polling(self):
        print("\n🖱️  Beweeg muis naar RECHTER RAND om naar Windows te gaan")
        print("⌨️  Druk Ctrl+Alt+M om terug naar Mac te gaan\n")
        threading.Thread(target=self._poll, daemon=True).start()
        
    def _poll(self):
        while True:
            if not self.is_windows_mode and self.server.connected:
                try:
                    x, y = self.mouse_ctrl.position
                    # Check right edge
                    if x >= self.screen_width - 3:
                        self._to_windows(int(y))
                except:
                    pass
            time.sleep(0.01)
            
    def _to_windows(self, y):
        if self.is_windows_mode:
            return
        self.is_windows_mode = True
        self.win_x = 5
        self.win_y = y
        self.last_x, self.last_y = self.mouse_ctrl.position
        
        print("\n🖥️  >>> WINDOWS MODE <<< (Ctrl+Alt+M = terug)")
        
        self.server.send_event({"type": "mode_switch", "active": True, "x": self.win_x, "y": self.win_y})
        
        # Start capturing
        self.mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            suppress=True
        )
        self.mouse_listener.start()
        
        self.kb_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=True
        )
        self.kb_listener.start()
        
    def _to_mac(self):
        if not self.is_windows_mode:
            return
        self.is_windows_mode = False
        
        print("\n🍎 >>> MAC MODE <<<")
        
        self.server.send_event({"type": "mode_switch", "active": False})
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.kb_listener:
            self.kb_listener.stop()
            
        # Move mouse back
        self.mouse_ctrl.position = (self.screen_width - 100, self.win_y)
        
    def _on_move(self, x, y):
        if not self.is_windows_mode:
            return
        dx = x - self.last_x
        dy = y - self.last_y
        self.last_x, self.last_y = x, y
        
        self.win_x += int(dx)
        self.win_y += int(dy)
        
        # Check if returning to Mac (left edge)
        if self.win_x <= 2:
            self._to_mac()
            return
            
        self.win_x = max(0, min(self.win_x, 3840))
        self.win_y = max(0, min(self.win_y, 2160))
        
        self.server.send_event({
            "type": "mouse_move",
            "x": self.win_x,
            "y": self.win_y
        })
        
    def _on_click(self, x, y, button, pressed):
        if not self.is_windows_mode:
            return
        btn = {mouse.Button.left: "left", mouse.Button.right: "right", mouse.Button.middle: "middle"}.get(button, "left")
        self.server.send_event({
            "type": "mouse_button",
            "button": btn,
            "action": "down" if pressed else "up",
            "x": self.win_x,
            "y": self.win_y
        })
        
    def _on_scroll(self, x, y, dx, dy):
        if not self.is_windows_mode:
            return
        self.server.send_event({
            "type": "mouse_scroll",
            "deltaX": int(dx * 120),
            "deltaY": int(dy * 120)
        })
        
    def _on_press(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = True
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = True
            
        # Check for Ctrl+Alt+M
        try:
            if self.ctrl and self.alt and hasattr(key, 'char') and key.char and key.char.lower() == 'm':
                self._to_mac()
                return
        except:
            pass
            
        vk = self._to_vk(key)
        if vk:
            self.server.send_event({
                "type": "key",
                "keyCode": vk,
                "action": "down"
            })
            
    def _on_release(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = False
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = False
            
        vk = self._to_vk(key)
        if vk:
            self.server.send_event({
                "type": "key",
                "keyCode": vk,
                "action": "up"
            })
            
    def _to_vk(self, key):
        special = {
            keyboard.Key.enter: 13, keyboard.Key.tab: 9, keyboard.Key.backspace: 8,
            keyboard.Key.esc: 27, keyboard.Key.space: 32,
            keyboard.Key.shift: 16, keyboard.Key.shift_l: 16, keyboard.Key.shift_r: 16,
            keyboard.Key.ctrl: 17, keyboard.Key.ctrl_l: 17, keyboard.Key.ctrl_r: 17,
            keyboard.Key.alt: 18, keyboard.Key.alt_l: 18, keyboard.Key.alt_r: 18,
            keyboard.Key.cmd: 91,
            keyboard.Key.left: 37, keyboard.Key.up: 38, keyboard.Key.right: 39, keyboard.Key.down: 40,
            keyboard.Key.delete: 46, keyboard.Key.home: 36, keyboard.Key.end: 35,
        }
        if key in special:
            return special[key]
        try:
            if hasattr(key, 'char') and key.char:
                return ord(key.char.upper())
        except:
            pass
        return 0


def main():
    server = Server()
    server.start()
    
    handler = InputHandler(server)
    handler.start_polling()
    
    print("Druk 'q' + Enter om te stoppen\n")
    
    try:
        while True:
            cmd = input().strip().lower()
            if cmd == 'q':
                break
    except KeyboardInterrupt:
        pass
    finally:
        if handler.is_windows_mode:
            handler._to_mac()
        server.stop()
        print("\n👋 Tot ziens!")


if __name__ == "__main__":
    main()
