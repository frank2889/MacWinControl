#!/usr/bin/env python3
"""
MacWinControl - Met visuele scherm-arrangement GUI
Sleep je Windows schermen naar de juiste positie, net als in Mac Beeldscherminstellingen!
"""

import json
import socket
import threading
import time
import sys
import subprocess
from dataclasses import dataclass
from typing import Optional, Callable, Tuple, List, Dict

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
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False
    print("⚠️  Tkinter not available")

try:
    import AppKit
    from AppKit import NSScreen
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False
    print("⚠️  AppKit not available")


@dataclass
class VirtualScreen:
    """Represents a screen (Mac or Windows)."""
    name: str
    width: int
    height: int
    x: int  # Position in virtual space
    y: int
    is_mac: bool
    index: int = 0


class ScreenArrangement:
    """Manages the arrangement of all screens."""
    
    def __init__(self):
        self.mac_screens: List[VirtualScreen] = []
        self.windows_screens: List[VirtualScreen] = []
        self.update_mac_screens()
        # Default Windows screens (will be updated when Windows connects)
        self.add_windows_screen(1920, 1080)
        self.add_windows_screen(1920, 1080)
        self._arrange_default()
    
    def update_mac_screens(self):
        """Detect Mac screens."""
        self.mac_screens = []
        
        if HAS_APPKIT:
            for i, screen in enumerate(NSScreen.screens()):
                frame = screen.frame()
                self.mac_screens.append(VirtualScreen(
                    name=f"Mac {i+1}" if i > 0 else "Mac (Main)",
                    width=int(frame.size.width),
                    height=int(frame.size.height),
                    x=int(frame.origin.x),
                    y=int(frame.origin.y),
                    is_mac=True,
                    index=i
                ))
        else:
            self.mac_screens = [VirtualScreen(
                name="Mac (Main)",
                width=1920, height=1080, x=0, y=0,
                is_mac=True, index=0
            )]
    
    def add_windows_screen(self, width: int, height: int):
        """Add a Windows screen."""
        idx = len(self.windows_screens)
        self.windows_screens.append(VirtualScreen(
            name=f"Windows {idx+1}" if idx > 0 else "Windows (Main)",
            width=width,
            height=height,
            x=0, y=0,
            is_mac=False,
            index=idx
        ))
    
    def set_windows_screens(self, screens: List[Dict]):
        """Update Windows screens from connected client."""
        self.windows_screens = []
        for i, s in enumerate(screens):
            self.windows_screens.append(VirtualScreen(
                name=f"Windows {i+1}" if i > 0 else "Windows (Main)",
                width=s.get('width', 1920),
                height=s.get('height', 1080),
                x=s.get('x', 0),
                y=s.get('y', 0),
                is_mac=False,
                index=i
            ))
        self._arrange_default()
    
    def _arrange_default(self):
        """Default arrangement: Windows to the right of Mac."""
        if not self.mac_screens:
            return
        
        # Find rightmost Mac screen
        mac_right = max(s.x + s.width for s in self.mac_screens)
        mac_top = min(s.y for s in self.mac_screens)
        
        # Position Windows screens to the right
        current_x = mac_right
        for ws in self.windows_screens:
            ws.x = current_x
            ws.y = mac_top
            current_x += ws.width
    
    def get_all_screens(self) -> List[VirtualScreen]:
        """Get all screens."""
        return self.mac_screens + self.windows_screens
    
    def get_total_bounds(self) -> Tuple[int, int, int, int]:
        """Get bounds of all screens."""
        all_screens = self.get_all_screens()
        if not all_screens:
            return (0, 0, 1920, 1080)
        
        min_x = min(s.x for s in all_screens)
        min_y = min(s.y for s in all_screens)
        max_x = max(s.x + s.width for s in all_screens)
        max_y = max(s.y + s.height for s in all_screens)
        return (min_x, min_y, max_x, max_y)
    
    def get_mac_bounds(self) -> Tuple[int, int, int, int]:
        """Get bounds of Mac screens only."""
        if not self.mac_screens:
            return (0, 0, 1920, 1080)
        min_x = min(s.x for s in self.mac_screens)
        min_y = min(s.y for s in self.mac_screens)
        max_x = max(s.x + s.width for s in self.mac_screens)
        max_y = max(s.y + s.height for s in self.mac_screens)
        return (min_x, min_y, max_x, max_y)
    
    def point_on_mac(self, x: int, y: int) -> bool:
        """Check if point is on a Mac screen."""
        for s in self.mac_screens:
            if s.x <= x < s.x + s.width and s.y <= y < s.y + s.height:
                return True
        return False
    
    def point_on_windows(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """Check if point is on a Windows screen. Returns (screen_idx, local_x, local_y)."""
        for s in self.windows_screens:
            if s.x <= x < s.x + s.width and s.y <= y < s.y + s.height:
                return (s.index, x - s.x, y - s.y)
        return None
    
    def get_transition_edge(self, x: int, y: int, threshold: int = 5) -> Optional[str]:
        """Check if at edge that transitions to Windows."""
        mac_bounds = self.get_mac_bounds()
        
        # Check if at Mac edge and there's a Windows screen adjacent
        for ws in self.windows_screens:
            # Right edge of Mac -> Left of Windows
            if x >= mac_bounds[2] - threshold:
                if ws.x == mac_bounds[2] and ws.y <= y < ws.y + ws.height:
                    return 'to_windows'
            # Left edge of Mac -> Right of Windows
            if x <= mac_bounds[0] + threshold:
                if ws.x + ws.width == mac_bounds[0] and ws.y <= y < ws.y + ws.height:
                    return 'to_windows'
            # Top edge
            if y <= mac_bounds[1] + threshold:
                if ws.y + ws.height == mac_bounds[1] and ws.x <= x < ws.x + ws.width:
                    return 'to_windows'
            # Bottom edge
            if y >= mac_bounds[3] - threshold:
                if ws.y == mac_bounds[3] and ws.x <= x < ws.x + ws.width:
                    return 'to_windows'
        
        return None
    
    def find_entry_point_to_windows(self, x: int, y: int) -> Tuple[int, int, int]:
        """Find the Windows screen and local coordinates when entering from Mac."""
        for ws in self.windows_screens:
            # Horizontal adjacency
            mac_bounds = self.get_mac_bounds()
            if ws.x == mac_bounds[2]:  # Windows is to the right
                if ws.y <= y < ws.y + ws.height:
                    return (ws.index, 5, y - ws.y)
            if ws.x + ws.width == mac_bounds[0]:  # Windows is to the left
                if ws.y <= y < ws.y + ws.height:
                    return (ws.index, ws.width - 5, y - ws.y)
            # Vertical adjacency
            if ws.y == mac_bounds[3]:  # Windows below
                if ws.x <= x < ws.x + ws.width:
                    return (ws.index, x - ws.x, 5)
            if ws.y + ws.height == mac_bounds[1]:  # Windows above
                if ws.x <= x < ws.x + ws.width:
                    return (ws.index, x - ws.x, ws.height - 5)
        
        # Default: first Windows screen
        if self.windows_screens:
            return (0, 100, y)
        return (0, 100, 540)
    
    def find_return_point_to_mac(self, win_screen: int, local_x: int, local_y: int) -> Tuple[int, int]:
        """Find Mac coordinates when returning from Windows."""
        if win_screen >= len(self.windows_screens):
            win_screen = 0
        ws = self.windows_screens[win_screen]
        mac_bounds = self.get_mac_bounds()
        
        # Check which edge we're returning from
        if local_x <= 5 and ws.x == mac_bounds[2]:  # Left edge, Windows is right of Mac
            return (mac_bounds[2] - 50, ws.y + local_y)
        if local_x >= ws.width - 5 and ws.x + ws.width == mac_bounds[0]:  # Right edge, Windows is left
            return (mac_bounds[0] + 50, ws.y + local_y)
        if local_y <= 5 and ws.y + ws.height == mac_bounds[1]:  # Top edge, Windows above
            return (ws.x + local_x, mac_bounds[1] + 50)
        if local_y >= ws.height - 5 and ws.y == mac_bounds[3]:  # Bottom edge, Windows below
            return (ws.x + local_x, mac_bounds[3] - 50)
        
        # Default: center of primary Mac
        return (self.mac_screens[0].x + self.mac_screens[0].width // 2,
                self.mac_screens[0].y + self.mac_screens[0].height // 2)
    
    def to_dict(self) -> dict:
        """Export arrangement as dict."""
        return {
            'mac_screens': [{'name': s.name, 'width': s.width, 'height': s.height, 'x': s.x, 'y': s.y} 
                          for s in self.mac_screens],
            'windows_screens': [{'name': s.name, 'width': s.width, 'height': s.height, 'x': s.x, 'y': s.y}
                               for s in self.windows_screens]
        }
    
    def from_dict(self, data: dict):
        """Import arrangement from dict."""
        for i, ws_data in enumerate(data.get('windows_screens', [])):
            if i < len(self.windows_screens):
                self.windows_screens[i].x = ws_data.get('x', self.windows_screens[i].x)
                self.windows_screens[i].y = ws_data.get('y', self.windows_screens[i].y)


class ScreenArrangementGUI:
    """Visual GUI for arranging screens."""
    
    def __init__(self, arrangement: ScreenArrangement, on_save: Callable):
        self.arrangement = arrangement
        self.on_save = on_save
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.scale = 0.1  # Scale factor for display
        self.dragging: Optional[VirtualScreen] = None
        self.drag_offset = (0, 0)
        self.screen_items: Dict[int, VirtualScreen] = {}
    
    def show(self):
        """Show the arrangement window."""
        if not HAS_TK:
            print("❌ Tkinter niet beschikbaar voor GUI")
            return
        
        self.root = tk.Tk()
        self.root.title("Scherm Arrangement - MacWinControl")
        self.root.geometry("800x600")
        self.root.configure(bg='#2d2d2d')
        
        # Header
        header = tk.Frame(self.root, bg='#1a1a1a', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="🖥️ Sleep de Windows schermen naar de juiste positie", 
                font=('Helvetica', 16, 'bold'), fg='white', bg='#1a1a1a').pack(pady=15)
        
        # Canvas for screens
        canvas_frame = tk.Frame(self.root, bg='#2d2d2d')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.canvas = tk.Canvas(canvas_frame, bg='#3d3d3d', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = tk.Frame(self.root, bg='#2d2d2d', height=60)
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.pack_propagate(False)
        
        style = {'font': ('Helvetica', 12), 'width': 15, 'height': 2}
        
        tk.Button(button_frame, text="Opslaan", command=self._save, 
                 bg='#007AFF', fg='white', **style).pack(side=tk.RIGHT, padx=20)
        tk.Button(button_frame, text="Reset", command=self._reset,
                 bg='#555555', fg='white', **style).pack(side=tk.RIGHT, padx=5)
        
        # Info label
        self.info_label = tk.Label(self.root, text="", font=('Helvetica', 11), 
                                   fg='#888888', bg='#2d2d2d')
        self.info_label.pack(pady=5)
        
        # Bind events
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.canvas.bind('<Configure>', lambda e: self._draw_screens())
        
        self._draw_screens()
        self.root.mainloop()
    
    def _calculate_scale(self):
        """Calculate scale to fit all screens in canvas."""
        if not self.canvas:
            return
        
        canvas_w = self.canvas.winfo_width() - 40
        canvas_h = self.canvas.winfo_height() - 40
        
        if canvas_w < 100 or canvas_h < 100:
            return
        
        bounds = self.arrangement.get_total_bounds()
        total_w = bounds[2] - bounds[0]
        total_h = bounds[3] - bounds[1]
        
        if total_w > 0 and total_h > 0:
            self.scale = min(canvas_w / total_w, canvas_h / total_h) * 0.8
    
    def _draw_screens(self):
        """Draw all screens on canvas."""
        if not self.canvas:
            return
        
        self.canvas.delete('all')
        self._calculate_scale()
        
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        bounds = self.arrangement.get_total_bounds()
        
        # Center offset
        total_w = (bounds[2] - bounds[0]) * self.scale
        total_h = (bounds[3] - bounds[1]) * self.scale
        offset_x = (canvas_w - total_w) / 2 - bounds[0] * self.scale
        offset_y = (canvas_h - total_h) / 2 - bounds[1] * self.scale
        
        self.screen_items.clear()
        
        # Draw Mac screens (gray, not draggable)
        for screen in self.arrangement.mac_screens:
            x1 = screen.x * self.scale + offset_x
            y1 = screen.y * self.scale + offset_y
            x2 = (screen.x + screen.width) * self.scale + offset_x
            y2 = (screen.y + screen.height) * self.scale + offset_y
            
            rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, 
                fill='#4a4a4a', outline='#888888', width=2)
            
            # Label
            self.canvas.create_text((x1+x2)/2, (y1+y2)/2 - 10,
                text=screen.name, fill='white', font=('Helvetica', 11, 'bold'))
            self.canvas.create_text((x1+x2)/2, (y1+y2)/2 + 10,
                text=f"{screen.width}×{screen.height}", fill='#aaaaaa', font=('Helvetica', 9))
        
        # Draw Windows screens (blue, draggable)
        for screen in self.arrangement.windows_screens:
            x1 = screen.x * self.scale + offset_x
            y1 = screen.y * self.scale + offset_y
            x2 = (screen.x + screen.width) * self.scale + offset_x
            y2 = (screen.y + screen.height) * self.scale + offset_y
            
            color = '#0066CC' if self.dragging != screen else '#0088FF'
            rect_id = self.canvas.create_rectangle(x1, y1, x2, y2,
                fill=color, outline='#00AAFF', width=3)
            
            self.screen_items[rect_id] = screen
            
            # Label
            self.canvas.create_text((x1+x2)/2, (y1+y2)/2 - 10,
                text=screen.name, fill='white', font=('Helvetica', 11, 'bold'))
            self.canvas.create_text((x1+x2)/2, (y1+y2)/2 + 10,
                text=f"{screen.width}×{screen.height}", fill='#aaddff', font=('Helvetica', 9))
            
            # Drag hint
            self.canvas.create_text((x1+x2)/2, y2 - 15,
                text="⋮⋮ sleep mij ⋮⋮", fill='#88ccff', font=('Helvetica', 8))
        
        self._update_info()
    
    def _update_info(self):
        """Update info label."""
        if not self.info_label:
            return
        
        mac_bounds = self.arrangement.get_mac_bounds()
        win_positions = []
        for ws in self.arrangement.windows_screens:
            if ws.x >= mac_bounds[2]:
                win_positions.append(f"{ws.name} → rechts")
            elif ws.x + ws.width <= mac_bounds[0]:
                win_positions.append(f"{ws.name} → links")
            elif ws.y >= mac_bounds[3]:
                win_positions.append(f"{ws.name} → onder")
            elif ws.y + ws.height <= mac_bounds[1]:
                win_positions.append(f"{ws.name} → boven")
            else:
                win_positions.append(f"{ws.name} → overlappend")
        
        self.info_label.config(text=" | ".join(win_positions))
    
    def _on_click(self, event):
        """Handle mouse click."""
        item = self.canvas.find_closest(event.x, event.y)
        if item and item[0] in self.screen_items:
            self.dragging = self.screen_items[item[0]]
            # Calculate offset
            bounds = self.arrangement.get_total_bounds()
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            total_w = (bounds[2] - bounds[0]) * self.scale
            total_h = (bounds[3] - bounds[1]) * self.scale
            offset_x = (canvas_w - total_w) / 2 - bounds[0] * self.scale
            offset_y = (canvas_h - total_h) / 2 - bounds[1] * self.scale
            
            screen_x = self.dragging.x * self.scale + offset_x
            screen_y = self.dragging.y * self.scale + offset_y
            self.drag_offset = (event.x - screen_x, event.y - screen_y)
    
    def _on_drag(self, event):
        """Handle mouse drag."""
        if not self.dragging:
            return
        
        bounds = self.arrangement.get_total_bounds()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        total_w = (bounds[2] - bounds[0]) * self.scale
        total_h = (bounds[3] - bounds[1]) * self.scale
        offset_x = (canvas_w - total_w) / 2 - bounds[0] * self.scale
        offset_y = (canvas_h - total_h) / 2 - bounds[1] * self.scale
        
        # Calculate new position
        new_x = (event.x - self.drag_offset[0] - offset_x) / self.scale
        new_y = (event.y - self.drag_offset[1] - offset_y) / self.scale
        
        # Snap to edges of Mac screens
        snap_threshold = 50
        mac_bounds = self.arrangement.get_mac_bounds()
        
        # Snap right edge of Windows to left edge of Mac
        if abs(new_x + self.dragging.width - mac_bounds[0]) < snap_threshold:
            new_x = mac_bounds[0] - self.dragging.width
        # Snap left edge of Windows to right edge of Mac
        if abs(new_x - mac_bounds[2]) < snap_threshold:
            new_x = mac_bounds[2]
        # Snap bottom of Windows to top of Mac
        if abs(new_y + self.dragging.height - mac_bounds[1]) < snap_threshold:
            new_y = mac_bounds[1] - self.dragging.height
        # Snap top of Windows to bottom of Mac
        if abs(new_y - mac_bounds[3]) < snap_threshold:
            new_y = mac_bounds[3]
        
        # Vertical alignment with Mac screens
        for ms in self.arrangement.mac_screens:
            if abs(new_y - ms.y) < snap_threshold:
                new_y = ms.y
            if abs(new_y + self.dragging.height - ms.y - ms.height) < snap_threshold:
                new_y = ms.y + ms.height - self.dragging.height
        
        self.dragging.x = int(new_x)
        self.dragging.y = int(new_y)
        self._draw_screens()
    
    def _on_release(self, event):
        """Handle mouse release."""
        self.dragging = None
        self._draw_screens()
    
    def _reset(self):
        """Reset to default arrangement."""
        self.arrangement._arrange_default()
        self._draw_screens()
    
    def _save(self):
        """Save and close."""
        if self.on_save:
            self.on_save(self.arrangement)
        if self.root:
            self.root.destroy()
            self.root = None


class NetworkServer:
    """TCP Server for Windows client communication."""
    
    def __init__(self, port: int = 52525):
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_name: str = ""
        self.running = False
        self.connected = False
        self.on_client_connected: Optional[Callable[[str, List[Dict]], None]] = None
        self.on_client_disconnected: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()
        self.client_screens: List[Dict] = []
        
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
            self.client_screens = []
            print("📴 Verbinding verbroken - wacht op herverbinding...")
    
    def _process_message(self, message: str):
        """Process incoming message."""
        try:
            msg = json.loads(message)
            msg_type = msg.get("type", "")
            
            if msg_type == "hello":
                self.client_name = msg.get("name", "Windows PC")
                self.client_screens = msg.get("screens", [
                    {"width": 1920, "height": 1080, "x": 0, "y": 0},
                    {"width": 1920, "height": 1080, "x": 1920, "y": 0}
                ])
                print(f"👋 Verbonden met: {self.client_name}")
                print(f"📺 Windows schermen: {len(self.client_screens)}")
                self._send({"type": "connected"})
                self.connected = True
                if self.on_client_connected:
                    self.on_client_connected(self.client_name, self.client_screens)
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
    """Capture and forward mouse/keyboard input with edge detection."""
    
    def __init__(self, server: NetworkServer, arrangement: ScreenArrangement):
        self.server = server
        self.arrangement = arrangement
        
        self.is_windows_mode = False
        self.mouse_controller = MouseController()
        
        self.current_win_screen = 0
        self.win_local_x = 0
        self.win_local_y = 0
        
        self.mouse_listener: Optional[mouse.Listener] = None
        self.keyboard_listener: Optional[keyboard.Listener] = None
        
        self.ctrl_pressed = False
        self.alt_pressed = False
        
        self.last_mac_x = 0
        self.last_mac_y = 0
        
    def start_edge_detection(self):
        """Start monitoring for edge hits."""
        print(f"🖱️  Edge detection actief")
        threading.Thread(target=self._edge_poll_loop, daemon=True).start()
    
    def _edge_poll_loop(self):
        """Poll mouse position for edge detection."""
        while True:
            if not self.is_windows_mode and self.server.connected:
                try:
                    pos = self.mouse_controller.position
                    x, y = int(pos[0]), int(pos[1])
                    
                    transition = self.arrangement.get_transition_edge(x, y)
                    if transition == 'to_windows':
                        self._switch_to_windows(x, y)
                except:
                    pass
            time.sleep(0.01)
    
    def _switch_to_windows(self, mac_x: int, mac_y: int):
        """Switch to Windows mode."""
        if self.is_windows_mode:
            return
        
        self.is_windows_mode = True
        self.last_mac_x = mac_x
        self.last_mac_y = mac_y
        
        # Find entry point
        screen_idx, local_x, local_y = self.arrangement.find_entry_point_to_windows(mac_x, mac_y)
        self.current_win_screen = screen_idx
        self.win_local_x = local_x
        self.win_local_y = local_y
        
        print()
        print("🖥️  ══════════════════════════════════════")
        print(f"🖥️  WINDOWS MODE - Scherm {screen_idx + 1}")
        print("🖥️  Ctrl+Alt+M om terug te gaan")
        print("🖥️  ══════════════════════════════════════")
        
        self.server.send_event({
            "type": "mode_switch", 
            "active": True,
            "screen": screen_idx,
            "x": local_x,
            "y": local_y
        })
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
        mac_x, mac_y = self.arrangement.find_return_point_to_mac(
            self.current_win_screen, self.win_local_x, self.win_local_y
        )
        self.mouse_controller.position = (mac_x, mac_y)
    
    def _start_capture(self):
        """Start capturing input."""
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
        
        # Get current Windows screen info
        if self.current_win_screen >= len(self.arrangement.windows_screens):
            self.current_win_screen = 0
        ws = self.arrangement.windows_screens[self.current_win_screen]
        
        # Calculate delta from last Mac position
        dx = x - self.last_mac_x
        dy = y - self.last_mac_y
        self.last_mac_x = x
        self.last_mac_y = y
        
        # Update Windows position
        self.win_local_x += int(dx)
        self.win_local_y += int(dy)
        
        # Check boundaries
        if self.win_local_x < 0:
            # Check if there's a screen to the left
            left_screen = self._find_adjacent_screen('left')
            if left_screen is not None:
                self.current_win_screen = left_screen
                ws = self.arrangement.windows_screens[left_screen]
                self.win_local_x = ws.width + self.win_local_x
            else:
                # Return to Mac
                self._switch_to_mac()
                return
        elif self.win_local_x >= ws.width:
            right_screen = self._find_adjacent_screen('right')
            if right_screen is not None:
                self.current_win_screen = right_screen
                self.win_local_x = self.win_local_x - ws.width
            else:
                self._switch_to_mac()
                return
        
        # Clamp Y
        self.win_local_y = max(0, min(self.win_local_y, ws.height - 1))
        
        self.server.send_event({
            "type": "mouse_move",
            "screen": self.current_win_screen,
            "x": self.win_local_x,
            "y": self.win_local_y,
            "timestamp": int(time.time() * 1000)
        })
    
    def _find_adjacent_screen(self, direction: str) -> Optional[int]:
        """Find adjacent Windows screen."""
        if self.current_win_screen >= len(self.arrangement.windows_screens):
            return None
        
        current = self.arrangement.windows_screens[self.current_win_screen]
        
        for i, ws in enumerate(self.arrangement.windows_screens):
            if i == self.current_win_screen:
                continue
            if direction == 'left' and ws.x + ws.width == current.x:
                return i
            if direction == 'right' and ws.x == current.x + current.width:
                return i
        
        return None
    
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
            "screen": self.current_win_screen,
            "x": self.win_local_x,
            "y": self.win_local_y,
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


class MacWinControl:
    """Main application with GUI."""
    
    def __init__(self):
        self.arrangement = ScreenArrangement()
        self.server = NetworkServer()
        self.input_capture = InputCapture(self.server, self.arrangement)
        self.gui: Optional[ScreenArrangementGUI] = None
        
        self.server.on_client_connected = self._on_connected
        self.server.on_client_disconnected = self._on_disconnected
    
    def _on_connected(self, name: str, screens: List[Dict]):
        # Update Windows screens
        self.arrangement.set_windows_screens(screens)
        
        print()
        print("╔══════════════════════════════════════════════════╗")
        print(f"║  ✅ VERBONDEN MET {name.upper():^30} ║")
        print("╚══════════════════════════════════════════════════╝")
        print()
        
        # Show GUI to arrange screens
        print("🖥️  Opening scherm arrangement venster...")
        self._show_arrangement_gui()
    
    def _show_arrangement_gui(self):
        """Show the arrangement GUI."""
        def on_save(arr):
            print("✅ Scherm arrangement opgeslagen!")
            self._print_arrangement()
        
        self.gui = ScreenArrangementGUI(self.arrangement, on_save)
        # Run in separate thread to not block
        threading.Thread(target=self.gui.show, daemon=True).start()
    
    def _print_arrangement(self):
        """Print current arrangement."""
        print()
        print("📐 Huidige scherm opstelling:")
        mac_bounds = self.arrangement.get_mac_bounds()
        for ws in self.arrangement.windows_screens:
            if ws.x >= mac_bounds[2]:
                pos = "RECHTS"
            elif ws.x + ws.width <= mac_bounds[0]:
                pos = "LINKS"
            elif ws.y >= mac_bounds[3]:
                pos = "ONDER"
            else:
                pos = "BOVEN"
            print(f"   {ws.name}: {pos} van Mac schermen")
        print()
        print("🖱️  Beweeg je muis naar de rand om te wisselen!")
        print("⌨️  Ctrl+Alt+M om terug naar Mac te gaan")
        print()
    
    def _on_disconnected(self):
        if self.input_capture.is_windows_mode:
            self.input_capture._switch_to_mac()
    
    def run(self):
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║     MacWinControl - Visuele Scherm Setup         ║")
        print("║  Sleep je Windows schermen naar de juiste plek!  ║")
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
        print("Commando's:  a=arrangement  q=stoppen")
        print()
        
        try:
            while True:
                cmd = input().strip().lower()
                if cmd == 'q':
                    break
                elif cmd == 'a':
                    self._show_arrangement_gui()
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
