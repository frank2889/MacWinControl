#!/usr/bin/env python3
"""
MacWinControl Bridge - Simpele versie die werkt zonder suppress
"""

import json
import socket
import threading
import time
import tkinter as tk
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController
from Quartz import CGEventTapCreate, CGEventTapEnable, kCGSessionEventTap, kCGHeadInsertEventTap, CGEventMaskBit, kCGEventMouseMoved, kCGEventLeftMouseDragged, kCGEventRightMouseDragged

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_screen_bounds():
    try:
        from AppKit import NSScreen
        screens = NSScreen.screens()
        if not screens:
            return 0, 1920, 0, 1080
        min_x = min(s.frame().origin.x for s in screens)
        max_x = max(s.frame().origin.x + s.frame().size.width for s in screens)
        min_y = min(s.frame().origin.y for s in screens)
        max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
        return int(min_x), int(max_x), int(min_y), int(max_y)
    except:
        return 0, 1920, 0, 1080


class Server:
    def __init__(self, on_status):
        self.socket = None
        self.client = None
        self.connected = False
        self.running = True
        self.on_status = on_status
        
    def start(self, port=52525):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', port))
        self.socket.listen(1)
        threading.Thread(target=self._accept, daemon=True).start()
        
    def _accept(self):
        while self.running:
            try:
                self.socket.settimeout(1)
                client, addr = self.socket.accept()
                self.client = client
                self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.on_status(f"Verbonden: {addr[0]}")
                self._handle()
            except socket.timeout:
                continue
            except:
                break
                    
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
                                self._send({"type": "connected"})
                                self.connected = True
                                self.on_status(f"✅ {msg.get('name', 'Windows')}")
                            elif msg.get("type") == "ping":
                                self._send({"type": "pong"})
                except socket.timeout:
                    continue
        except:
            pass
        finally:
            self.connected = False
            self.client = None
            self.on_status("Wacht...")
            
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
            try: self.client.close()
            except: pass
        if self.socket:
            try: self.socket.close()
            except: pass


class Bridge:
    def __init__(self, server, on_mode):
        self.server = server
        self.on_mode = on_mode
        self.mouse = MouseController()
        self.min_x, self.max_x, self.min_y, self.max_y = get_screen_bounds()
        self.is_windows = False
        self.win_x = 960
        self.win_y = 540
        self.ctrl = False
        self.alt = False
        self._last_x = 0
        self._last_y = 0
        print(f"Scherm: {self.min_x} tot {self.max_x}")
        
    def start(self):
        # Poll thread voor edge detection
        threading.Thread(target=self._poll_edge, daemon=True).start()
        # Start keyboard listener (altijd aan, voor Ctrl+Alt+M)
        self.kb_listener = keyboard.Listener(on_press=self._key_down, on_release=self._key_up)
        self.kb_listener.start()
        # Start mouse listener
        self.mouse_listener = mouse.Listener(on_move=self._mouse_move, on_click=self._mouse_click, on_scroll=self._mouse_scroll)
        self.mouse_listener.start()
        
    def _poll_edge(self):
        """Check edge zonder listener"""
        while True:
            try:
                if not self.is_windows and self.server.connected:
                    x, y = self.mouse.position
                    if x >= self.max_x - 5:
                        self._to_windows(int(y))
            except:
                pass
            time.sleep(0.02)
            
    def _to_windows(self, y):
        if self.is_windows:
            return
        print("-> WINDOWS")
        self.is_windows = True
        self.win_x = 10
        self.win_y = y
        self.on_mode("🖥️ WINDOWS")
        self.server.send_event({"type": "mode_switch", "active": True, "x": self.win_x, "y": self.win_y})
        # Zet muis in het midden
        mid_x = (self.min_x + self.max_x) // 2
        mid_y = (self.min_y + self.max_y) // 2
        self.mouse.position = (mid_x, mid_y)
        self._last_x = mid_x
        self._last_y = mid_y
        
    def _to_mac(self):
        if not self.is_windows:
            return
        print("-> MAC")
        self.is_windows = False
        self.on_mode("🍎 MAC")
        self.server.send_event({"type": "mode_switch", "active": False})
        # Zet muis aan rechterkant
        self.mouse.position = (self.max_x - 100, self.win_y)
        
    def _mouse_move(self, x, y):
        if not self.is_windows:
            return
        # Bereken delta
        dx = x - self._last_x
        dy = y - self._last_y
        
        self.win_x += int(dx)
        self.win_y += int(dy)
        
        # Terug naar Mac?
        if self.win_x <= 0:
            self._to_mac()
            return
            
        # Clamp en stuur
        self.win_x = max(0, min(self.win_x, 3840))
        self.win_y = max(0, min(self.win_y, 2160))
        self.server.send_event({"type": "mouse_move", "x": self.win_x, "y": self.win_y})
        
        # Houd muis in het midden (zodat we altijd kunnen bewegen)
        mid_x = (self.min_x + self.max_x) // 2
        mid_y = (self.min_y + self.max_y) // 2
        if abs(x - mid_x) > 200 or abs(y - mid_y) > 200:
            self.mouse.position = (mid_x, mid_y)
            self._last_x = mid_x
            self._last_y = mid_y
        else:
            self._last_x = x
            self._last_y = y
    
    def _mouse_click(self, x, y, button, pressed):
        if not self.is_windows:
            return
        btn = {mouse.Button.left: "left", mouse.Button.right: "right", mouse.Button.middle: "middle"}.get(button, "left")
        self.server.send_event({"type": "mouse_button", "button": btn, "action": "down" if pressed else "up"})
        
    def _mouse_scroll(self, x, y, dx, dy):
        if not self.is_windows:
            return
        self.server.send_event({"type": "mouse_scroll", "deltaX": int(dx * 120), "deltaY": int(dy * 120)})
        
    def _key_down(self, key):
        # Track modifiers
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = True
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = True
        # Ctrl+Alt+M = terug naar Mac
        try:
            if self.ctrl and self.alt and hasattr(key, 'char') and key.char and key.char.lower() == 'm':
                if self.is_windows:
                    self._to_mac()
                return
        except:
            pass
        # Forward naar Windows
        if self.is_windows:
            vk = self._vk(key)
            if vk:
                self.server.send_event({"type": "key", "keyCode": vk, "action": "down"})
                
    def _key_up(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = False
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = False
        if self.is_windows:
            vk = self._vk(key)
            if vk:
                self.server.send_event({"type": "key", "keyCode": vk, "action": "up"})
                
    def _vk(self, key):
        m = {
            keyboard.Key.enter: 13, keyboard.Key.tab: 9, keyboard.Key.backspace: 8,
            keyboard.Key.esc: 27, keyboard.Key.space: 32,
            keyboard.Key.shift: 16, keyboard.Key.shift_l: 16, keyboard.Key.shift_r: 16,
            keyboard.Key.ctrl: 17, keyboard.Key.ctrl_l: 17, keyboard.Key.ctrl_r: 17,
            keyboard.Key.alt: 18, keyboard.Key.alt_l: 18, keyboard.Key.alt_r: 18,
            keyboard.Key.cmd: 91, keyboard.Key.cmd_l: 91, keyboard.Key.cmd_r: 91,
            keyboard.Key.left: 37, keyboard.Key.up: 38, keyboard.Key.right: 39, keyboard.Key.down: 40,
            keyboard.Key.delete: 46, keyboard.Key.home: 36, keyboard.Key.end: 35,
            keyboard.Key.page_up: 33, keyboard.Key.page_down: 34,
            keyboard.Key.caps_lock: 20,
        }
        if key in m:
            return m[key]
        try:
            if hasattr(key, 'char') and key.char:
                return ord(key.char.upper())
        except:
            pass
        return 0


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MacWinControl")
        self.root.geometry("300x200")
        self.root.configure(bg='#1a1a2e')
        
        # Header
        tk.Label(self.root, text="🖥️ MacWinControl", font=('Helvetica', 18, 'bold'),
                fg='white', bg='#1a1a2e').pack(pady=10)
        
        # IP
        ip = get_ip()
        tk.Label(self.root, text=f"IP: {ip}", font=('Menlo', 20, 'bold'),
                fg='#00ff88', bg='#1a1a2e').pack(pady=5)
        tk.Label(self.root, text="Poort: 52525", font=('Helvetica', 11),
                fg='#666', bg='#1a1a2e').pack()
        
        # Status
        self.status = tk.Label(self.root, text="⏳ Wacht op Windows...", font=('Helvetica', 12),
                              fg='#ffaa00', bg='#1a1a2e')
        self.status.pack(pady=10)
        
        # Mode
        self.mode = tk.Label(self.root, text="🍎 MAC", font=('Helvetica', 14, 'bold'),
                            fg='#888', bg='#1a1a2e')
        self.mode.pack()
        
        # Tips
        tk.Label(self.root, text="Muis rechts = Windows | Ctrl+Alt+M = Mac",
                font=('Helvetica', 9), fg='#444', bg='#1a1a2e').pack(pady=10)
        
        # Server
        self.server = Server(self._set_status)
        self.bridge = Bridge(self.server, self._set_mode)
        
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        
    def _set_status(self, t):
        self.root.after(0, lambda: self.status.config(text=t))
        
    def _set_mode(self, t):
        self.root.after(0, lambda: self.mode.config(text=t))
        
    def run(self):
        self.server.start()
        self.bridge.start()
        print(f"Server draait op {get_ip()}:52525")
        self.root.mainloop()
        
    def _quit(self):
        if self.bridge.is_windows:
            self.bridge._to_mac()
        self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = App()
    app.run()
