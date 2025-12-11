#!/usr/bin/env python3
"""
MacWinControl - Volledige macOS App met GUI
Een echte app die je kunt openen met dubbelklik!
"""

import json
import socket
import threading
import time
import sys
import subprocess
import os
from dataclasses import dataclass
from typing import Optional, Callable, Tuple, List, Dict

# ==================== Dependencies ====================

def install_dependencies():
    """Install required packages."""
    try:
        import pynput
    except ImportError:
        print("Installing pynput...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput", "-q"])
    
    try:
        import rumps
    except ImportError:
        print("Installing rumps (menu bar support)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rumps", "-q"])

install_dependencies()

from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

try:
    import AppKit
    from AppKit import NSScreen, NSApplication, NSApp
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False

try:
    import rumps
    HAS_RUMPS = True
except ImportError:
    HAS_RUMPS = False


# ==================== Screen Management ====================

@dataclass
class VirtualScreen:
    """Represents a screen."""
    name: str
    width: int
    height: int
    x: int
    y: int
    is_mac: bool
    index: int = 0


class ScreenArrangement:
    """Manages screen arrangement."""
    
    def __init__(self):
        self.mac_screens: List[VirtualScreen] = []
        self.windows_screens: List[VirtualScreen] = []
        self.update_mac_screens()
        self.add_windows_screen(1920, 1080)
        self.add_windows_screen(1920, 1080)
        self._arrange_default()
    
    def update_mac_screens(self):
        self.mac_screens = []
        if HAS_APPKIT:
            for i, screen in enumerate(NSScreen.screens()):
                frame = screen.frame()
                self.mac_screens.append(VirtualScreen(
                    name=f"Mac {i+1}" if i > 0 else "Mac (Hoofd)",
                    width=int(frame.size.width),
                    height=int(frame.size.height),
                    x=int(frame.origin.x),
                    y=int(frame.origin.y),
                    is_mac=True,
                    index=i
                ))
        else:
            self.mac_screens = [VirtualScreen("Mac", 1920, 1080, 0, 0, True, 0)]
    
    def add_windows_screen(self, width: int, height: int):
        idx = len(self.windows_screens)
        self.windows_screens.append(VirtualScreen(
            name=f"Windows {idx+1}" if idx > 0 else "Windows (Hoofd)",
            width=width, height=height, x=0, y=0,
            is_mac=False, index=idx
        ))
    
    def set_windows_screens(self, screens: List[Dict]):
        self.windows_screens = []
        for i, s in enumerate(screens):
            self.windows_screens.append(VirtualScreen(
                name=f"Windows {i+1}" if i > 0 else "Windows (Hoofd)",
                width=s.get('width', 1920),
                height=s.get('height', 1080),
                x=s.get('x', 0), y=s.get('y', 0),
                is_mac=False, index=i
            ))
        self._arrange_default()
    
    def _arrange_default(self):
        if not self.mac_screens:
            return
        mac_right = max(s.x + s.width for s in self.mac_screens)
        mac_top = min(s.y for s in self.mac_screens)
        current_x = mac_right
        for ws in self.windows_screens:
            ws.x = current_x
            ws.y = mac_top
            current_x += ws.width
    
    def get_mac_bounds(self) -> Tuple[int, int, int, int]:
        if not self.mac_screens:
            return (0, 0, 1920, 1080)
        return (
            min(s.x for s in self.mac_screens),
            min(s.y for s in self.mac_screens),
            max(s.x + s.width for s in self.mac_screens),
            max(s.y + s.height for s in self.mac_screens)
        )
    
    def get_transition_edge(self, x: int, y: int, threshold: int = 5) -> Optional[str]:
        mac_bounds = self.get_mac_bounds()
        for ws in self.windows_screens:
            if x >= mac_bounds[2] - threshold:
                if ws.x == mac_bounds[2] and ws.y <= y < ws.y + ws.height:
                    return 'to_windows'
            if x <= mac_bounds[0] + threshold:
                if ws.x + ws.width == mac_bounds[0] and ws.y <= y < ws.y + ws.height:
                    return 'to_windows'
        return None
    
    def find_entry_point(self, x: int, y: int) -> Tuple[int, int, int]:
        mac_bounds = self.get_mac_bounds()
        for ws in self.windows_screens:
            if ws.x == mac_bounds[2] and ws.y <= y < ws.y + ws.height:
                return (ws.index, 5, y - ws.y)
            if ws.x + ws.width == mac_bounds[0] and ws.y <= y < ws.y + ws.height:
                return (ws.index, ws.width - 5, y - ws.y)
        return (0, 100, 540)
    
    def find_return_point(self, win_screen: int, lx: int, ly: int) -> Tuple[int, int]:
        if win_screen >= len(self.windows_screens):
            win_screen = 0
        ws = self.windows_screens[win_screen]
        mac_bounds = self.get_mac_bounds()
        if lx <= 5 and ws.x == mac_bounds[2]:
            return (mac_bounds[2] - 50, ws.y + ly)
        if lx >= ws.width - 5 and ws.x + ws.width == mac_bounds[0]:
            return (mac_bounds[0] + 50, ws.y + ly)
        return (self.mac_screens[0].x + self.mac_screens[0].width // 2,
                self.mac_screens[0].y + self.mac_screens[0].height // 2)


# ==================== Network ====================

class NetworkServer:
    """TCP Server."""
    
    def __init__(self, port: int = 52525):
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_name: str = ""
        self.running = False
        self.connected = False
        self.on_client_connected: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None
        self._lock = threading.Lock()
        self.client_screens: List[Dict] = []
        
    def get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(1)
        threading.Thread(target=self._accept_loop, daemon=True).start()
    
    def _accept_loop(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client, addr = self.server_socket.accept()
                with self._lock:
                    self.client_socket = client
                    self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._handle_client()
            except socket.timeout:
                continue
            except:
                break
    
    def _handle_client(self):
        try:
            self._send({"type": "hello", "version": "1.0", "name": socket.gethostname()})
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
                except:
                    break
        finally:
            self.connected = False
            if self.on_client_disconnected:
                self.on_client_disconnected()
            with self._lock:
                self.client_socket = None
            self.client_name = ""
    
    def _process_message(self, message: str):
        try:
            msg = json.loads(message)
            if msg.get("type") == "hello":
                self.client_name = msg.get("name", "Windows PC")
                self.client_screens = msg.get("screens", [{"width": 1920, "height": 1080, "x": 0, "y": 0}])
                self._send({"type": "connected"})
                self.connected = True
                if self.on_client_connected:
                    self.on_client_connected(self.client_name, self.client_screens)
            elif msg.get("type") == "ping":
                self._send({"type": "pong"})
        except:
            pass
    
    def _send(self, obj: dict):
        with self._lock:
            if self.client_socket:
                try:
                    self.client_socket.send((json.dumps(obj) + "\n").encode('utf-8'))
                except:
                    pass
    
    def send_event(self, event: dict):
        if self.connected:
            self._send(event)
    
    def stop(self):
        self.running = False
        with self._lock:
            if self.client_socket:
                self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()


# ==================== Input Capture ====================

class InputCapture:
    """Capture and forward input."""
    
    def __init__(self, server: NetworkServer, arrangement: ScreenArrangement):
        self.server = server
        self.arrangement = arrangement
        self.is_windows_mode = False
        self.mouse_controller = MouseController()
        self.current_win_screen = 0
        self.win_x = 0
        self.win_y = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.last_x = 0
        self.last_y = 0
        self.on_mode_change: Optional[Callable] = None
    
    def start_edge_detection(self):
        threading.Thread(target=self._edge_poll, daemon=True).start()
    
    def _edge_poll(self):
        while True:
            if not self.is_windows_mode and self.server.connected:
                try:
                    x, y = self.mouse_controller.position
                    if self.arrangement.get_transition_edge(int(x), int(y)):
                        self._switch_to_windows(int(x), int(y))
                except:
                    pass
            time.sleep(0.01)
    
    def _switch_to_windows(self, mx: int, my: int):
        if self.is_windows_mode:
            return
        self.is_windows_mode = True
        self.last_x, self.last_y = mx, my
        idx, lx, ly = self.arrangement.find_entry_point(mx, my)
        self.current_win_screen = idx
        self.win_x, self.win_y = lx, ly
        self.server.send_event({"type": "mode_switch", "active": True, "screen": idx, "x": lx, "y": ly})
        self._start_capture()
        if self.on_mode_change:
            self.on_mode_change(True)
    
    def _switch_to_mac(self):
        if not self.is_windows_mode:
            return
        self.is_windows_mode = False
        self.server.send_event({"type": "mode_switch", "active": False})
        self._stop_capture()
        mac_x, mac_y = self.arrangement.find_return_point(self.current_win_screen, self.win_x, self.win_y)
        self.mouse_controller.position = (mac_x, mac_y)
        if self.on_mode_change:
            self.on_mode_change(False)
    
    def _start_capture(self):
        self.mouse_listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll, suppress=True)
        self.mouse_listener.start()
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release, suppress=True)
        self.keyboard_listener.start()
    
    def _stop_capture(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
    
    def _on_move(self, x, y):
        if not self.is_windows_mode:
            return
        ws = self.arrangement.windows_screens[self.current_win_screen] if self.current_win_screen < len(self.arrangement.windows_screens) else None
        if not ws:
            return
        dx, dy = x - self.last_x, y - self.last_y
        self.last_x, self.last_y = x, y
        self.win_x += int(dx)
        self.win_y += int(dy)
        if self.win_x < 0 or self.win_x >= ws.width:
            self._switch_to_mac()
            return
        self.win_y = max(0, min(self.win_y, ws.height - 1))
        self.server.send_event({"type": "mouse_move", "screen": self.current_win_screen, "x": self.win_x, "y": self.win_y, "timestamp": int(time.time() * 1000)})
    
    def _on_click(self, x, y, button, pressed):
        if not self.is_windows_mode:
            return
        btn = {mouse.Button.left: "left", mouse.Button.right: "right", mouse.Button.middle: "middle"}.get(button, "left")
        self.server.send_event({"type": "mouse_button", "button": btn, "action": "down" if pressed else "up", "x": self.win_x, "y": self.win_y, "timestamp": int(time.time() * 1000)})
    
    def _on_scroll(self, x, y, dx, dy):
        if not self.is_windows_mode:
            return
        self.server.send_event({"type": "mouse_scroll", "deltaX": int(dx * 120), "deltaY": int(dy * 120), "timestamp": int(time.time() * 1000)})
    
    def _on_key_press(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = True
        try:
            if self.ctrl_pressed and self.alt_pressed and hasattr(key, 'char') and key.char and key.char.lower() == 'm':
                self._switch_to_mac()
                return
        except:
            pass
        self.server.send_event({"type": "key", "keyCode": self._key_to_vk(key), "action": "down", "modifiers": {"control": self.ctrl_pressed, "alt": self.alt_pressed}, "timestamp": int(time.time() * 1000)})
    
    def _on_key_release(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False
        self.server.send_event({"type": "key", "keyCode": self._key_to_vk(key), "action": "up", "modifiers": {"control": self.ctrl_pressed, "alt": self.alt_pressed}, "timestamp": int(time.time() * 1000)})
    
    def _key_to_vk(self, key) -> int:
        special = {keyboard.Key.enter: 13, keyboard.Key.tab: 9, keyboard.Key.backspace: 8, keyboard.Key.esc: 27, keyboard.Key.space: 32,
                   keyboard.Key.shift: 16, keyboard.Key.ctrl: 17, keyboard.Key.alt: 18, keyboard.Key.cmd: 91,
                   keyboard.Key.left: 37, keyboard.Key.up: 38, keyboard.Key.right: 39, keyboard.Key.down: 40,
                   keyboard.Key.delete: 46, keyboard.Key.home: 36, keyboard.Key.end: 35,
                   keyboard.Key.f1: 112, keyboard.Key.f2: 113, keyboard.Key.f3: 114, keyboard.Key.f4: 115,
                   keyboard.Key.f5: 116, keyboard.Key.f6: 117, keyboard.Key.f7: 118, keyboard.Key.f8: 119}
        if key in special:
            return special[key]
        try:
            if hasattr(key, 'char') and key.char:
                return ord(key.char.upper())
        except:
            pass
        return 0


# ==================== GUI Application ====================

class MacWinControlApp:
    """Main GUI Application."""
    
    def __init__(self):
        self.arrangement = ScreenArrangement()
        self.server = NetworkServer()
        self.input_capture = InputCapture(self.server, self.arrangement)
        
        self.server.on_client_connected = self._on_connected
        self.server.on_client_disconnected = self._on_disconnected
        self.input_capture.on_mode_change = self._on_mode_change
        
        self.root: Optional[tk.Tk] = None
        self.status_label: Optional[tk.Label] = None
        self.ip_label: Optional[tk.Label] = None
        self.mode_label: Optional[tk.Label] = None
        self.client_label: Optional[tk.Label] = None
    
    def _check_accessibility(self) -> bool:
        """Check and request accessibility permissions."""
        if not HAS_APPKIT:
            return True
        try:
            from ApplicationServices import AXIsProcessTrusted
            return AXIsProcessTrusted()
        except:
            return True
    
    def _request_accessibility(self):
        """Open accessibility settings."""
        try:
            subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'], check=False)
        except:
            pass
    
    def run(self):
        """Start the application."""
        if not HAS_TK:
            print("Tkinter is required!")
            return
        
        self.root = tk.Tk()
        self.root.title("MacWinControl")
        self.root.geometry("500x400")
        self.root.configure(bg='#1e1e1e')
        self.root.resizable(False, False)
        
        # Make window stay on top initially
        self.root.attributes('-topmost', True)
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))
        
        self._create_ui()
        self._start_server()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
    
    def _create_ui(self):
        """Create the user interface."""
        # Header
        header = tk.Frame(self.root, bg='#007AFF', height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="🖥️ MacWinControl", font=('Helvetica', 24, 'bold'),
                fg='white', bg='#007AFF').pack(pady=20)
        
        # Main content
        content = tk.Frame(self.root, bg='#1e1e1e', padx=30, pady=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # IP Address section
        ip_frame = tk.Frame(content, bg='#2d2d2d', padx=20, pady=15)
        ip_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(ip_frame, text="IP Adres voor Windows:", font=('Helvetica', 12),
                fg='#888888', bg='#2d2d2d').pack(anchor='w')
        
        self.ip_label = tk.Label(ip_frame, text=self.server.get_local_ip(),
                                 font=('Helvetica', 28, 'bold'), fg='#00FF88', bg='#2d2d2d')
        self.ip_label.pack(anchor='w', pady=5)
        
        tk.Label(ip_frame, text=f"Poort: {self.server.port}", font=('Helvetica', 11),
                fg='#666666', bg='#2d2d2d').pack(anchor='w')
        
        # Status section
        status_frame = tk.Frame(content, bg='#2d2d2d', padx=20, pady=15)
        status_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(status_frame, text="Status:", font=('Helvetica', 12),
                fg='#888888', bg='#2d2d2d').pack(anchor='w')
        
        self.status_label = tk.Label(status_frame, text="⏳ Wacht op Windows...",
                                     font=('Helvetica', 16), fg='#FFAA00', bg='#2d2d2d')
        self.status_label.pack(anchor='w', pady=5)
        
        self.client_label = tk.Label(status_frame, text="",
                                     font=('Helvetica', 11), fg='#666666', bg='#2d2d2d')
        self.client_label.pack(anchor='w')
        
        # Mode indicator
        mode_frame = tk.Frame(content, bg='#2d2d2d', padx=20, pady=15)
        mode_frame.pack(fill=tk.X, pady=10)
        
        self.mode_label = tk.Label(mode_frame, text="🍎 Mac Mode",
                                   font=('Helvetica', 14, 'bold'), fg='#888888', bg='#2d2d2d')
        self.mode_label.pack(anchor='w')
        
        # Instructions
        instructions = tk.Frame(content, bg='#1e1e1e')
        instructions.pack(fill=tk.X, pady=10)
        
        tk.Label(instructions, text="💡 Beweeg je muis naar de rand om naar Windows te gaan",
                font=('Helvetica', 10), fg='#555555', bg='#1e1e1e').pack()
        tk.Label(instructions, text="⌨️ Druk Ctrl+Alt+M om terug naar Mac te gaan",
                font=('Helvetica', 10), fg='#555555', bg='#1e1e1e').pack()
        
        # Arrange button
        btn_frame = tk.Frame(content, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="🖥️ Schermen Rangschikken", command=self._show_arrangement,
                 font=('Helvetica', 12), bg='#444444', fg='white', width=25, height=2,
                 activebackground='#555555', activeforeground='white', bd=0).pack()
    
    def _start_server(self):
        """Start the server and edge detection."""
        # Check accessibility
        if not self._check_accessibility():
            if messagebox.askyesno("Toegang Vereist", 
                "MacWinControl heeft Accessibility toegang nodig om je muis en toetsenbord te kunnen doorsturen.\n\n"
                "Wil je de Systeemvoorkeuren openen om dit in te stellen?"):
                self._request_accessibility()
        
        self.server.start()
        self.input_capture.start_edge_detection()
    
    def _on_connected(self, name: str, screens: List[Dict]):
        """Handle client connection."""
        self.arrangement.set_windows_screens(screens)
        
        if self.status_label:
            self.status_label.config(text="✅ Verbonden!", fg='#00FF88')
        if self.client_label:
            self.client_label.config(text=f"Client: {name} ({len(screens)} scherm{'en' if len(screens) > 1 else ''})")
    
    def _on_disconnected(self):
        """Handle client disconnection."""
        if self.status_label:
            self.status_label.config(text="⏳ Wacht op Windows...", fg='#FFAA00')
        if self.client_label:
            self.client_label.config(text="")
        if self.mode_label:
            self.mode_label.config(text="🍎 Mac Mode", fg='#888888')
    
    def _on_mode_change(self, is_windows: bool):
        """Handle mode change."""
        if self.mode_label:
            if is_windows:
                self.mode_label.config(text="🖥️ Windows Mode - Ctrl+Alt+M om terug", fg='#00AAFF')
            else:
                self.mode_label.config(text="🍎 Mac Mode", fg='#888888')
    
    def _show_arrangement(self):
        """Show screen arrangement window."""
        arr_window = tk.Toplevel(self.root)
        arr_window.title("Scherm Rangschikking")
        arr_window.geometry("700x500")
        arr_window.configure(bg='#2d2d2d')
        arr_window.transient(self.root)
        arr_window.grab_set()
        
        # Header
        tk.Label(arr_window, text="🖥️ Sleep de Windows schermen naar de juiste positie",
                font=('Helvetica', 14, 'bold'), fg='white', bg='#2d2d2d').pack(pady=15)
        
        # Canvas
        canvas = tk.Canvas(arr_window, bg='#3d3d3d', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        dragging = {'screen': None, 'offset': (0, 0)}
        
        def draw():
            canvas.delete('all')
            all_screens = self.arrangement.mac_screens + self.arrangement.windows_screens
            if not all_screens:
                return
            
            min_x = min(s.x for s in all_screens)
            min_y = min(s.y for s in all_screens)
            max_x = max(s.x + s.width for s in all_screens)
            max_y = max(s.y + s.height for s in all_screens)
            
            cw, ch = canvas.winfo_width(), canvas.winfo_height()
            if cw < 100 or ch < 100:
                return
            
            scale = min((cw - 40) / (max_x - min_x), (ch - 40) / (max_y - min_y)) * 0.8
            ox = (cw - (max_x - min_x) * scale) / 2 - min_x * scale
            oy = (ch - (max_y - min_y) * scale) / 2 - min_y * scale
            
            for s in self.arrangement.mac_screens:
                x1, y1 = s.x * scale + ox, s.y * scale + oy
                x2, y2 = (s.x + s.width) * scale + ox, (s.y + s.height) * scale + oy
                canvas.create_rectangle(x1, y1, x2, y2, fill='#4a4a4a', outline='#888', width=2)
                canvas.create_text((x1+x2)/2, (y1+y2)/2, text=s.name, fill='white', font=('Helvetica', 10, 'bold'))
            
            for s in self.arrangement.windows_screens:
                x1, y1 = s.x * scale + ox, s.y * scale + oy
                x2, y2 = (s.x + s.width) * scale + ox, (s.y + s.height) * scale + oy
                color = '#0088FF' if dragging['screen'] == s else '#0066CC'
                rid = canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='#00AAFF', width=3, tags=f'win{s.index}')
                canvas.create_text((x1+x2)/2, (y1+y2)/2 - 10, text=s.name, fill='white', font=('Helvetica', 10, 'bold'))
                canvas.create_text((x1+x2)/2, (y1+y2)/2 + 10, text='⋮⋮ sleep ⋮⋮', fill='#88ccff', font=('Helvetica', 8))
        
        def on_click(e):
            for s in self.arrangement.windows_screens:
                items = canvas.find_withtag(f'win{s.index}')
                for item in items:
                    coords = canvas.coords(item)
                    if len(coords) >= 4 and coords[0] <= e.x <= coords[2] and coords[1] <= e.y <= coords[3]:
                        dragging['screen'] = s
                        dragging['offset'] = (e.x, e.y)
                        return
        
        def on_drag(e):
            if not dragging['screen']:
                return
            s = dragging['screen']
            
            all_screens = self.arrangement.mac_screens + self.arrangement.windows_screens
            min_x = min(sc.x for sc in all_screens)
            max_x = max(sc.x + sc.width for sc in all_screens)
            min_y = min(sc.y for sc in all_screens)
            max_y = max(sc.y + sc.height for sc in all_screens)
            
            cw, ch = canvas.winfo_width(), canvas.winfo_height()
            scale = min((cw - 40) / (max_x - min_x), (ch - 40) / (max_y - min_y)) * 0.8
            
            dx = (e.x - dragging['offset'][0]) / scale
            dy = (e.y - dragging['offset'][1]) / scale
            s.x += int(dx)
            s.y += int(dy)
            dragging['offset'] = (e.x, e.y)
            
            # Snap
            mac_bounds = self.arrangement.get_mac_bounds()
            if abs(s.x - mac_bounds[2]) < 100:
                s.x = mac_bounds[2]
            if abs(s.x + s.width - mac_bounds[0]) < 100:
                s.x = mac_bounds[0] - s.width
            
            draw()
        
        def on_release(e):
            dragging['screen'] = None
            draw()
        
        canvas.bind('<Button-1>', on_click)
        canvas.bind('<B1-Motion>', on_drag)
        canvas.bind('<ButtonRelease-1>', on_release)
        canvas.bind('<Configure>', lambda e: draw())
        
        # Buttons
        btn_frame = tk.Frame(arr_window, bg='#2d2d2d')
        btn_frame.pack(fill=tk.X, pady=15)
        
        tk.Button(btn_frame, text="Opslaan", command=arr_window.destroy,
                 font=('Helvetica', 12), bg='#007AFF', fg='white', width=15, bd=0).pack(side=tk.RIGHT, padx=20)
        tk.Button(btn_frame, text="Reset", command=lambda: (self.arrangement._arrange_default(), draw()),
                 font=('Helvetica', 12), bg='#555', fg='white', width=15, bd=0).pack(side=tk.RIGHT, padx=5)
        
        arr_window.after(100, draw)
    
    def _on_close(self):
        """Handle window close."""
        if self.input_capture.is_windows_mode:
            self.input_capture._switch_to_mac()
        self.server.stop()
        self.root.destroy()


# ==================== Entry Point ====================

def main():
    import platform
    if platform.system() != 'Darwin':
        print("Dit programma is alleen voor macOS!")
        sys.exit(1)
    
    app = MacWinControlApp()
    app.run()


if __name__ == "__main__":
    main()
