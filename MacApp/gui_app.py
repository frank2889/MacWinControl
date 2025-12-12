#!/usr/bin/env python3
"""
MacWinControl - GUI Version with Tkinter
"""

import json
import socket
import threading
import time
import sys
import tkinter as tk
from tkinter import messagebox
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController

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

# Get total screen bounds (for multi-monitor setups)
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
                                self.on_status(f"✅ Verbonden met: {msg.get('name', 'Windows')}")
                            elif msg.get("type") == "ping":
                                self._send({"type": "pong"})
                except socket.timeout:
                    continue
        except:
            pass
        finally:
            self.connected = False
            self.client = None
            self.on_status("Wacht op verbinding...")
            
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
    def __init__(self, server, on_mode_change):
        self.server = server
        self.on_mode_change = on_mode_change
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
        self.min_x, self.max_x, self.min_y, self.max_y = get_screen_bounds()
        print(f"Screen bounds: x={self.min_x} tot {self.max_x}, y={self.min_y} tot {self.max_y}")
        
    def start_polling(self):
        threading.Thread(target=self._poll, daemon=True).start()
        
    def _poll(self):
        while True:
            if not self.is_windows_mode and self.server.connected:
                try:
                    x, y = self.mouse_ctrl.position
                    # Check rechter rand van ALLE schermen
                    if x >= self.max_x - 5:
                        print(f"Edge detected! x={x}, max_x={self.max_x}")
                        self._to_windows(int(y))
                except Exception as e:
                    print(f"Poll error: {e}")
            time.sleep(0.01)
            
    def _to_windows(self, y):
        if self.is_windows_mode:
            return
        self.is_windows_mode = True
        self.win_x = 5
        self.win_y = y
        self.last_x, self.last_y = self.mouse_ctrl.position
        
        self.on_mode_change("🖥️ WINDOWS MODE")
        self.server.send_event({"type": "mode_switch", "active": True, "x": self.win_x, "y": self.win_y})
        
        # Zet muis in hoek en start tracking ZONDER suppress
        self._park_mouse()
        
        self.mouse_listener = mouse.Listener(
            on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll, suppress=False
        )
        self.mouse_listener.start()
        
        self.kb_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release, suppress=False
        )
        self.kb_listener.start()
        
    def _park_mouse(self):
        """Zet muis in rechter-onder hoek tijdens Windows mode"""
        self.mouse_ctrl.position = (self.max_x - 50, self.max_y - 50)
        self.last_x, self.last_y = self.mouse_ctrl.position
        
    def _to_mac(self):
        if not self.is_windows_mode:
            return
        self.is_windows_mode = False
        
        self.on_mode_change("🍎 MAC MODE")
        self.server.send_event({"type": "mode_switch", "active": False})
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.kb_listener:
            self.kb_listener.stop()
            
        # Zet muis terug aan rechter kant
        self.mouse_ctrl.position = (self.max_x - 100, self.win_y)
        
    def _on_move(self, x, y):
        if not self.is_windows_mode:
            return
        dx, dy = x - self.last_x, y - self.last_y
        
        # Bereken nieuwe Windows positie
        self.win_x += int(dx)
        self.win_y += int(dy)
        
        # Check of we terug naar Mac moeten
        if self.win_x <= 2:
            self._to_mac()
            return
            
        self.win_x = max(0, min(self.win_x, 3840))
        self.win_y = max(0, min(self.win_y, 2160))
        self.server.send_event({"type": "mouse_move", "x": self.win_x, "y": self.win_y})
        
        # Zet muis terug in hoek (zodat er altijd ruimte is om te bewegen)
        self._park_mouse()
        
    def _on_click(self, x, y, button, pressed):
        if not self.is_windows_mode:
            return
        btn = {mouse.Button.left: "left", mouse.Button.right: "right", mouse.Button.middle: "middle"}.get(button, "left")
        self.server.send_event({"type": "mouse_button", "button": btn, "action": "down" if pressed else "up"})
        
    def _on_scroll(self, x, y, dx, dy):
        if not self.is_windows_mode:
            return
        self.server.send_event({"type": "mouse_scroll", "deltaX": int(dx * 120), "deltaY": int(dy * 120)})
        
    def _on_press(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = True
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = True
            
        try:
            if self.ctrl and self.alt and hasattr(key, 'char') and key.char and key.char.lower() == 'm':
                self._to_mac()
                return
        except:
            pass
            
        vk = self._to_vk(key)
        if vk:
            self.server.send_event({"type": "key", "keyCode": vk, "action": "down"})
            
    def _on_release(self, key):
        if not self.is_windows_mode:
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl = False
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt = False
            
        vk = self._to_vk(key)
        if vk:
            self.server.send_event({"type": "key", "keyCode": vk, "action": "up"})
            
    def _to_vk(self, key):
        special = {
            keyboard.Key.enter: 13, keyboard.Key.tab: 9, keyboard.Key.backspace: 8,
            keyboard.Key.esc: 27, keyboard.Key.space: 32,
            keyboard.Key.shift: 16, keyboard.Key.ctrl: 17, keyboard.Key.alt: 18, keyboard.Key.cmd: 91,
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


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MacWinControl")
        self.root.geometry("400x300")
        self.root.configure(bg='#1e1e1e')
        self.root.resizable(False, False)
        
        # Header
        header = tk.Frame(self.root, bg='#007AFF', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🖥️ MacWinControl", font=('Helvetica', 20, 'bold'),
                fg='white', bg='#007AFF').pack(pady=15)
        
        # Content
        content = tk.Frame(self.root, bg='#1e1e1e', padx=20, pady=15)
        content.pack(fill=tk.BOTH, expand=True)
        
        # IP Address
        ip_frame = tk.Frame(content, bg='#2d2d2d', padx=15, pady=10)
        ip_frame.pack(fill=tk.X, pady=5)
        tk.Label(ip_frame, text="IP Adres voor Windows:", font=('Helvetica', 11),
                fg='#888', bg='#2d2d2d').pack(anchor='w')
        self.ip_label = tk.Label(ip_frame, text=get_ip(), font=('Helvetica', 24, 'bold'),
                                fg='#00FF88', bg='#2d2d2d')
        self.ip_label.pack(anchor='w')
        tk.Label(ip_frame, text="Poort: 52525", font=('Helvetica', 10), fg='#666', bg='#2d2d2d').pack(anchor='w')
        
        # Status
        status_frame = tk.Frame(content, bg='#2d2d2d', padx=15, pady=10)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_label = tk.Label(status_frame, text="⏳ Wacht op Windows...",
                                     font=('Helvetica', 14), fg='#FFAA00', bg='#2d2d2d')
        self.status_label.pack(anchor='w')
        
        # Mode
        mode_frame = tk.Frame(content, bg='#2d2d2d', padx=15, pady=10)
        mode_frame.pack(fill=tk.X, pady=5)
        self.mode_label = tk.Label(mode_frame, text="🍎 MAC MODE",
                                   font=('Helvetica', 12, 'bold'), fg='#888', bg='#2d2d2d')
        self.mode_label.pack(anchor='w')
        
        # Instructions
        tk.Label(content, text="💡 Muis naar rechter rand = Windows", font=('Helvetica', 9),
                fg='#555', bg='#1e1e1e').pack(pady=2)
        tk.Label(content, text="⌨️ Ctrl+Alt+M = terug naar Mac", font=('Helvetica', 9),
                fg='#555', bg='#1e1e1e').pack()
        
        # Server & Input
        self.server = Server(self.update_status)
        self.handler = InputHandler(self.server, self.update_mode)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def update_status(self, text):
        self.root.after(0, lambda: self.status_label.config(text=text))
        
    def update_mode(self, text):
        self.root.after(0, lambda: self.mode_label.config(text=text))
        
    def run(self):
        self.server.start()
        self.handler.start_polling()
        self.root.mainloop()
        
    def on_close(self):
        if self.handler.is_windows_mode:
            self.handler._to_mac()
        self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = App()
    app.run()
