#!/usr/bin/env python3
"""
MacWinControl Bridge v3 - Zonder muis warping
Muis blijft normaal werken op Mac, alleen events worden geforward naar Windows
"""

import json
import socket
import threading
import time
import tkinter as tk
from AppKit import NSScreen, NSEvent
from Quartz import CGWarpMouseCursorPosition, CGPoint

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
    screens = NSScreen.screens()
    if not screens:
        return 0, 1920, 0, 1080
    min_x = min(s.frame().origin.x for s in screens)
    max_x = max(s.frame().origin.x + s.frame().size.width for s in screens)
    min_y = min(s.frame().origin.y for s in screens)
    max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
    return int(min_x), int(max_x), int(min_y), int(max_y)


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
        try:
            if self.client: self.client.close()
            if self.socket: self.socket.close()
        except: pass


class Bridge:
    def __init__(self, server, on_mode):
        self.server = server
        self.on_mode = on_mode
        self.min_x, self.max_x, self.min_y, self.max_y = get_screen_bounds()
        self.is_windows = False
        
        # Windows cursor positie (virtueel)
        self.win_x = 960
        self.win_y = 540
        
        # Voor delta berekening
        self.last_x = 0
        self.last_y = 0
        self.edge_y = 0  # Y positie waar we naar Windows gingen
        
        print(f"Scherm: {self.min_x} tot {self.max_x}")
        
    def start(self):
        threading.Thread(target=self._poll_mouse, daemon=True).start()
        
    def _poll_mouse(self):
        """Poll muis positie - trap muis in Windows mode"""
        # Trap positie (waar we de muis vasthouden in Windows mode)
        trap_x = (self.min_x + self.max_x) / 2
        trap_y = (self.min_y + self.max_y) / 2
        warp_distance = 200  # Warp pas als muis 200px van midden is
        
        while True:
            try:
                loc = NSEvent.mouseLocation()
                x = loc.x
                y = loc.y
                
                if not self.is_windows:
                    # MAC MODE: check of we naar rechter rand gaan
                    if self.server.connected and x >= self.max_x - 3:
                        self._to_windows(y)
                        # Warp naar midden en reset tracking
                        CGWarpMouseCursorPosition(CGPoint(trap_x, trap_y))
                        time.sleep(0.05)
                        self.last_x = trap_x
                        self.last_y = trap_y
                else:
                    # WINDOWS MODE: bereken delta en stuur naar Windows
                    dx = x - self.last_x
                    dy = self.last_y - y  # Y is omgekeerd
                    
                    self.last_x = x
                    self.last_y = y
                    
                    # Update Windows positie
                    if abs(dx) > 0.5 or abs(dy) > 0.5:
                        self.win_x += int(dx * 1.5)
                        self.win_y += int(dy * 1.5)
                        
                        # Clamp
                        self.win_x = max(0, min(self.win_x, 3840))
                        self.win_y = max(0, min(self.win_y, 2160))
                        
                        self.server.send_event({"type": "mouse_move", "x": self.win_x, "y": self.win_y})
                        
                        # Terug naar Mac als virtuele muis naar links gaat
                        if self.win_x <= 0:
                            self._to_mac()
                            continue
                    
                    # Warp alleen als muis te ver van midden is
                    dist_from_center = ((x - trap_x)**2 + (y - trap_y)**2)**0.5
                    if dist_from_center > warp_distance:
                        CGWarpMouseCursorPosition(CGPoint(trap_x, trap_y))
                        time.sleep(0.02)
                        self.last_x = trap_x
                        self.last_y = trap_y
                        
            except Exception as e:
                print(f"Error: {e}")
                
            time.sleep(0.008)
            
    def _to_windows(self, y):
        if self.is_windows:
            return
        print("-> WINDOWS")
        self.is_windows = True
        self.edge_y = y
        self.win_x = 50  # Start links op Windows scherm
        self.win_y = int(y)
        self.on_mode("🖥️ WINDOWS")
        self.server.send_event({"type": "mode_switch", "active": True, "x": self.win_x, "y": self.win_y})
        
    def _to_mac(self):
        if not self.is_windows:
            return
        print("-> MAC")
        self.is_windows = False
        self.on_mode("🍎 MAC")
        self.server.send_event({"type": "mode_switch", "active": False})


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MacWinControl")
        self.root.geometry("320x220")
        self.root.configure(bg='#1a1a2e')
        
        tk.Label(self.root, text="🖥️ MacWinControl", font=('Helvetica', 18, 'bold'),
                fg='white', bg='#1a1a2e').pack(pady=10)
        
        ip = get_ip()
        tk.Label(self.root, text=f"IP: {ip}", font=('Menlo', 22, 'bold'),
                fg='#00ff88', bg='#1a1a2e').pack(pady=5)
        tk.Label(self.root, text="Poort: 52525", font=('Helvetica', 11),
                fg='#666', bg='#1a1a2e').pack()
        
        self.status = tk.Label(self.root, text="⏳ Wacht op Windows...", font=('Helvetica', 12),
                              fg='#ffaa00', bg='#1a1a2e')
        self.status.pack(pady=10)
        
        self.mode = tk.Label(self.root, text="🍎 MAC", font=('Helvetica', 16, 'bold'),
                            fg='#888', bg='#1a1a2e')
        self.mode.pack()
        
        tk.Label(self.root, text="→ Rechts = Windows | ← Links = Mac",
                font=('Helvetica', 10), fg='#555', bg='#1a1a2e').pack(pady=10)
        
        self.server = Server(self._set_status)
        self.bridge = Bridge(self.server, self._set_mode)
        
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        
    def _set_status(self, t):
        self.root.after(0, lambda: self.status.config(text=t))
        
    def _set_mode(self, t):
        color = '#00aaff' if 'WINDOWS' in t else '#888'
        self.root.after(0, lambda: self.mode.config(text=t, fg=color))
        
    def run(self):
        self.server.start()
        self.bridge.start()
        print(f"Server: {get_ip()}:52525")
        self.root.mainloop()
        
    def _quit(self):
        if self.bridge.is_windows:
            self.bridge._to_mac()
        self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = App()
    app.run()
