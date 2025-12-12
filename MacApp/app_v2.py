#!/usr/bin/env python3
"""
MacWinControl 2.0 - Modern Mac App
Unified design with bidirectional support
"""

import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Callable
from enum import Enum

# Import screen layout widget
try:
    from screen_layout_widget import ScreenLayoutCard
    HAS_LAYOUT_WIDGET = True
except ImportError:
    HAS_LAYOUT_WIDGET = False

# Try to import Mac-specific modules
try:
    from AppKit import NSScreen, NSEvent, NSPasteboard, NSStringPboardType
    from Quartz import CGWarpMouseCursorPosition, CGPoint
    HAS_MAC_MODULES = True
except ImportError:
    HAS_MAC_MODULES = False
    print("Warning: Mac modules not available")

# Design System Colors
COLORS = {
    "primary": "#6366f1",
    "primary_hover": "#4f46e5",
    "secondary": "#8b5cf6",
    "accent": "#06b6d4",
    "bg": "#f8fafc",
    "surface": "#ffffff",
    "surface_hover": "#f1f5f9",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "text_muted": "#64748b",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
}

# ============================================================================
# Utilities
# ============================================================================

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_computer_id():
    return str(uuid.uuid4())[:8]

def get_computer_name():
    return socket.gethostname()

def get_screens():
    """Get all connected screens"""
    screens = []
    if HAS_MAC_MODULES:
        for i, screen in enumerate(NSScreen.screens()):
            frame = screen.frame()
            screens.append({
                "id": f"screen_{i}",
                "name": f"Display {i + 1}",
                "width": int(frame.size.width),
                "height": int(frame.size.height),
                "x": int(frame.origin.x),
                "y": int(frame.origin.y),
                "is_primary": i == 0,
            })
    else:
        # Fallback
        screens.append({
            "id": "screen_0",
            "name": "Display 1",
            "width": 1920,
            "height": 1080,
            "x": 0,
            "y": 0,
            "is_primary": True,
        })
    return screens

def get_screen_bounds():
    """Get total screen bounds"""
    if HAS_MAC_MODULES:
        screens = NSScreen.screens()
        if screens:
            min_x = min(s.frame().origin.x for s in screens)
            max_x = max(s.frame().origin.x + s.frame().size.width for s in screens)
            min_y = min(s.frame().origin.y for s in screens)
            max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
            return int(min_x), int(max_x), int(min_y), int(max_y)
    return 0, 1920, 0, 1080


# ============================================================================
# Network Layer
# ============================================================================

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class NetworkManager:
    """Handles both server and client connections"""
    
    def __init__(self, on_state_change: Callable, on_message: Callable, on_peer_found: Callable):
        self.on_state_change = on_state_change
        self.on_message = on_message
        self.on_peer_found = on_peer_found
        
        self.server_socket = None
        self.client_socket = None
        self.peer_socket = None
        self.running = False
        self.state = ConnectionState.DISCONNECTED
        self.peer_info = None
        self.is_server = True
        
        self.computer_id = get_computer_id()
        self.computer_name = get_computer_name()
        
    def start_server(self, port=52525):
        """Start listening for connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(1)
            self.running = True
            self.is_server = True
            
            threading.Thread(target=self._accept_connections, daemon=True).start()
            threading.Thread(target=self._broadcast_presence, daemon=True).start()
            threading.Thread(target=self._listen_for_peers, daemon=True).start()
            
            return True
        except Exception as e:
            print(f"Server start error: {e}")
            return False
    
    def connect_to(self, host: str, port: int = 52525):
        """Connect to another computer"""
        try:
            self._set_state(ConnectionState.CONNECTING)
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.peer_socket = self.client_socket
            self.is_server = False
            self.running = True
            
            threading.Thread(target=self._receive_loop, daemon=True).start()
            self._send_hello()
            
            return True
        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            print(f"Connect error: {e}")
            return False
    
    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client, addr = self.server_socket.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.peer_socket = client
                self.peer_info = {"ip": addr[0], "port": addr[1]}
                
                threading.Thread(target=self._receive_loop, daemon=True).start()
                self._send_hello()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")
                break
    
    def _receive_loop(self):
        """Receive messages from peer"""
        buffer = ""
        while self.running and self.peer_socket:
            try:
                self.peer_socket.settimeout(0.1)
                data = self.peer_socket.recv(65536)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._handle_message(line)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break
        
        self._set_state(ConnectionState.DISCONNECTED)
        self.peer_socket = None
    
    def _handle_message(self, line: str):
        """Process received message"""
        try:
            msg = json.loads(line)
            msg_type = msg.get("type")
            payload = msg.get("payload", {})
            
            if msg_type == "hello":
                self.peer_info = payload
                self._send({"type": "connected", "payload": self._get_info()})
                self._set_state(ConnectionState.CONNECTED)
                
            elif msg_type == "connected":
                self.peer_info = payload
                self._set_state(ConnectionState.CONNECTED)
                
            elif msg_type == "ping":
                self._send({"type": "pong"})
                
            else:
                self.on_message(msg_type, payload)
                
        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")
    
    def _send_hello(self):
        """Send hello message with computer info"""
        self._send({"type": "hello", "payload": self._get_info()})
    
    def _get_info(self):
        """Get this computer's info"""
        return {
            "id": self.computer_id,
            "name": self.computer_name,
            "platform": "mac",
            "ip": get_local_ip(),
            "port": 52525,
            "screens": get_screens(),
        }
    
    def send(self, msg_type: str, payload: dict = None):
        """Send a message to peer"""
        self._send({"type": msg_type, "payload": payload or {}})
    
    def _send(self, msg: dict):
        """Internal send"""
        if self.peer_socket:
            try:
                data = json.dumps(msg) + "\n"
                self.peer_socket.send(data.encode('utf-8'))
            except Exception as e:
                print(f"Send error: {e}")
    
    def _set_state(self, state: ConnectionState):
        """Update connection state"""
        self.state = state
        self.on_state_change(state)
    
    def _broadcast_presence(self):
        """Broadcast presence via UDP for auto-discovery"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            while self.running:
                msg = json.dumps({
                    "type": "announce",
                    "id": self.computer_id,
                    "name": self.computer_name,
                    "ip": get_local_ip(),
                    "port": 52525,
                    "platform": "mac",
                })
                try:
                    sock.sendto(msg.encode(), ('<broadcast>', 52526))
                except:
                    pass
                time.sleep(3)
        except:
            pass
    
    def _listen_for_peers(self):
        """Listen for other computers broadcasting"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', 52526))
            sock.settimeout(1.0)
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    if msg.get("type") == "announce" and msg.get("id") != self.computer_id:
                        self.on_peer_found(msg)
                except socket.timeout:
                    continue
                except:
                    pass
        except:
            pass
    
    def disconnect(self):
        """Disconnect from peer"""
        self.running = False
        if self.peer_socket:
            try:
                self.peer_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self._set_state(ConnectionState.DISCONNECTED)
    
    def stop(self):
        """Stop all network activity"""
        self.disconnect()


# ============================================================================
# Input Handler
# ============================================================================

class InputHandler:
    """Handles mouse and keyboard input"""
    
    def __init__(self, network: NetworkManager, on_mode_change: Callable):
        self.network = network
        self.on_mode_change = on_mode_change
        
        self.min_x, self.max_x, self.min_y, self.max_y = get_screen_bounds()
        self.is_controlling_remote = False
        self.is_being_controlled = False
        
        self.remote_x = 960
        self.remote_y = 540
        self.last_x = 0
        self.last_y = 0
        
        self.running = False
        self.active_edge = "right"  # Which edge triggers switch to remote
        
    def set_edge(self, edge: str):
        """Set which edge triggers switch to remote"""
        self.active_edge = edge
        print(f"[InputHandler] Active edge set to: {edge}")
        
    def start(self):
        """Start input handling"""
        self.running = True
        threading.Thread(target=self._poll_loop, daemon=True).start()
    
    def stop(self):
        """Stop input handling"""
        self.running = False
    
    def _check_edge(self, x: float, y: float) -> bool:
        """Check if mouse is at the active edge"""
        threshold = 3
        if self.active_edge == "right":
            return x >= self.max_x - threshold
        elif self.active_edge == "left":
            return x <= self.min_x + threshold
        elif self.active_edge == "top":
            return y >= self.max_y - threshold  # Y is flipped on Mac
        elif self.active_edge == "bottom":
            return y <= self.min_y + threshold
        return False
    
    def _get_opposite_edge_check(self) -> str:
        """Get the opposite edge for returning to local"""
        opposites = {"right": "left", "left": "right", "top": "bottom", "bottom": "top"}
        return opposites.get(self.active_edge, "left")
    
    def _poll_loop(self):
        """Main polling loop for edge detection"""
        trap_x = (self.min_x + self.max_x) / 2
        trap_y = (self.min_y + self.max_y) / 2
        
        while self.running:
            try:
                if not HAS_MAC_MODULES:
                    time.sleep(0.1)
                    continue
                
                loc = NSEvent.mouseLocation()
                x, y = loc.x, loc.y
                
                if not self.is_controlling_remote and not self.is_being_controlled:
                    # Check for edge transition using dynamic edge
                    if self.network.state == ConnectionState.CONNECTED:
                        if self._check_edge(x, y):
                            self._switch_to_remote(x, y)
                            CGWarpMouseCursorPosition(CGPoint(trap_x, trap_y))
                            time.sleep(0.05)
                            self.last_x = trap_x
                            self.last_y = trap_y
                            
                elif self.is_controlling_remote:
                    # Calculate delta and send to remote
                    dx = x - self.last_x
                    dy = self.last_y - y  # Flip Y
                    
                    self.last_x = x
                    self.last_y = y
                    
                    if abs(dx) > 0.5 or abs(dy) > 0.5:
                        self.remote_x += int(dx * 1.5)
                        self.remote_y += int(dy * 1.5)
                        
                        self.remote_x = max(0, min(self.remote_x, 3840))
                        self.remote_y = max(0, min(self.remote_y, 2160))
                        
                        self.network.send("mouse_move", {
                            "x": self.remote_x,
                            "y": self.remote_y,
                            "absolute": True
                        })
                        
                        # Return to local if remote mouse reaches opposite edge
                        opposite = self._get_opposite_edge_check()
                        should_return = False
                        if opposite == "left" and self.remote_x <= 0:
                            should_return = True
                        elif opposite == "right" and self.remote_x >= 3840:
                            should_return = True
                        elif opposite == "top" and self.remote_y <= 0:
                            should_return = True
                        elif opposite == "bottom" and self.remote_y >= 2160:
                            should_return = True
                        
                        if should_return:
                            self._switch_to_local()
                            continue
                    
                    # Keep mouse in center area
                    dist = ((x - trap_x)**2 + (y - trap_y)**2)**0.5
                    if dist > 200:
                        CGWarpMouseCursorPosition(CGPoint(trap_x, trap_y))
                        time.sleep(0.02)
                        self.last_x = trap_x
                        self.last_y = trap_y
                        
            except Exception as e:
                print(f"Poll error: {e}")
            
            time.sleep(0.008)
    
    def _switch_to_remote(self, x: float, y: float):
        """Switch to controlling remote computer"""
        if self.is_controlling_remote:
            return
        
        self.is_controlling_remote = True
        
        # Set initial remote position based on active edge
        if self.active_edge == "right":
            self.remote_x = 50
            self.remote_y = int(y)
        elif self.active_edge == "left":
            self.remote_x = 3840 - 50
            self.remote_y = int(y)
        elif self.active_edge == "top":
            self.remote_x = int(x)
            self.remote_y = 2160 - 50
        elif self.active_edge == "bottom":
            self.remote_x = int(x)
            self.remote_y = 50
        else:
            self.remote_x = 50
            self.remote_y = int(y)
        
        self.network.send("mode_switch", {
            "active": True, 
            "x": self.remote_x, 
            "y": self.remote_y,
            "edge": self.active_edge
        })
        self.on_mode_change("remote")
    
    def _switch_to_local(self):
        """Switch back to local control"""
        if not self.is_controlling_remote:
            return
        
        self.is_controlling_remote = False
        self.network.send("mode_switch", {"active": False, "edge": self.active_edge})
        self.on_mode_change("local")
        
        # Move mouse to the edge where Windows is
        if HAS_MAC_MODULES:
            if self.active_edge == "right":
                CGWarpMouseCursorPosition(CGPoint(self.max_x - 50, self.remote_y))
            elif self.active_edge == "left":
                CGWarpMouseCursorPosition(CGPoint(self.min_x + 50, self.remote_y))
            elif self.active_edge == "top":
                CGWarpMouseCursorPosition(CGPoint(self.remote_x, self.max_y - 50))
            elif self.active_edge == "bottom":
                CGWarpMouseCursorPosition(CGPoint(self.remote_x, self.min_y + 50))
    
    def handle_incoming_input(self, msg_type: str, payload: dict):
        """Handle input from remote computer"""
        if msg_type == "mode_switch":
            self.is_being_controlled = payload.get("active", False)
            if self.is_being_controlled:
                # Move mouse to incoming position
                x = payload.get("x", 960)
                y = payload.get("y", 540)
                if HAS_MAC_MODULES:
                    CGWarpMouseCursorPosition(CGPoint(x, y))
            self.on_mode_change("controlled" if self.is_being_controlled else "local")
            
        elif msg_type == "mouse_move" and self.is_being_controlled:
            x = payload.get("x", 0)
            y = payload.get("y", 0)
            if HAS_MAC_MODULES:
                CGWarpMouseCursorPosition(CGPoint(x, y))


# ============================================================================
# Clipboard Manager
# ============================================================================

class ClipboardManager:
    """Handles clipboard synchronization"""
    
    def __init__(self, network: NetworkManager):
        self.network = network
        self.last_content = ""
        self.running = False
    
    def start(self):
        """Start clipboard monitoring"""
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def stop(self):
        """Stop clipboard monitoring"""
        self.running = False
    
    def _monitor_loop(self):
        """Monitor clipboard for changes"""
        while self.running:
            try:
                content = self._get_clipboard()
                if content and content != self.last_content:
                    self.last_content = content
                    if self.network.state == ConnectionState.CONNECTED:
                        self.network.send("clipboard_sync", {
                            "content_type": "text",
                            "data": content
                        })
            except:
                pass
            time.sleep(0.5)
    
    def _get_clipboard(self) -> str:
        """Get clipboard content"""
        if HAS_MAC_MODULES:
            try:
                pb = NSPasteboard.generalPasteboard()
                return pb.stringForType_(NSStringPboardType) or ""
            except:
                return ""
        return ""
    
    def set_clipboard(self, content: str):
        """Set clipboard content"""
        if HAS_MAC_MODULES:
            try:
                pb = NSPasteboard.generalPasteboard()
                pb.clearContents()
                pb.setString_forType_(content, NSStringPboardType)
                self.last_content = content
            except:
                pass
    
    def handle_incoming(self, payload: dict):
        """Handle incoming clipboard data"""
        if payload.get("content_type") == "text":
            self.set_clipboard(payload.get("data", ""))


# ============================================================================
# Modern GUI
# ============================================================================

class ModernApp:
    """Main application with modern UI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MacWinControl")
        self.root.geometry("480x780")
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(False, False)
        
        # Network and handlers
        self.network = NetworkManager(
            on_state_change=self._on_connection_state,
            on_message=self._on_message,
            on_peer_found=self._on_peer_found
        )
        self.input_handler = InputHandler(self.network, self._on_mode_change)
        self.clipboard = ClipboardManager(self.network)
        
        self.discovered_peers = {}
        self.current_mode = "local"
        
        self._build_ui()
        self._start_services()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _build_ui(self):
        """Build the user interface"""
        # Header
        header = tk.Frame(self.root, bg=COLORS["primary"], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg=COLORS["primary"])
        header_content.pack(expand=True)
        
        tk.Label(
            header_content,
            text="🔗 MacWinControl",
            font=("SF Pro Display", 24, "bold"),
            fg="white",
            bg=COLORS["primary"]
        ).pack(pady=(15, 5))
        
        tk.Label(
            header_content,
            text="Seamless mouse & keyboard sharing",
            font=("SF Pro Text", 12),
            fg="#e0e7ff",  # Light indigo instead of rgba
            bg=COLORS["primary"]
        ).pack()
        
        # Main content
        content = tk.Frame(self.root, bg=COLORS["bg"], padx=24, pady=24)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Connection card
        conn_card = self._create_card(content, "Connection")
        
        # This computer info
        info_frame = tk.Frame(conn_card, bg=COLORS["surface"])
        info_frame.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(
            info_frame,
            text="This Computer",
            font=("SF Pro Text", 11),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(anchor="w")
        
        self.ip_label = tk.Label(
            info_frame,
            text=get_local_ip(),
            font=("SF Mono", 28, "bold"),
            fg=COLORS["primary"],
            bg=COLORS["surface"]
        )
        self.ip_label.pack(anchor="w")
        
        tk.Label(
            info_frame,
            text=f"{get_computer_name()} • Port 52525",
            font=("SF Pro Text", 11),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(anchor="w")
        
        # Status
        status_frame = tk.Frame(conn_card, bg=COLORS["surface"])
        status_frame.pack(fill=tk.X, pady=(0, 16))
        
        self.status_indicator = tk.Canvas(
            status_frame, width=12, height=12,
            bg=COLORS["surface"], highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self.status_indicator.create_oval(2, 2, 10, 10, fill=COLORS["text_muted"], outline="")
        
        self.status_label = tk.Label(
            status_frame,
            text="Starting...",
            font=("SF Pro Text", 13),
            fg=COLORS["text"],
            bg=COLORS["surface"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Manual connect
        connect_frame = tk.Frame(conn_card, bg=COLORS["surface"])
        connect_frame.pack(fill=tk.X, pady=(8, 0))
        
        tk.Label(
            connect_frame,
            text="Connect to:",
            font=("SF Pro Text", 11),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(anchor="w", pady=(0, 4))
        
        input_row = tk.Frame(connect_frame, bg=COLORS["surface"])
        input_row.pack(fill=tk.X)
        
        self.host_entry = tk.Entry(
            input_row,
            font=("SF Mono", 14),
            bg=COLORS["surface_hover"],
            fg=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["primary"]
        )
        self.host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        self.host_entry.insert(0, "192.168.1.")
        
        self.connect_btn = tk.Button(
            input_row,
            text="Connect",
            font=("SF Pro Text", 12, "bold"),
            bg=COLORS["primary"],
            fg="white",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._on_connect_click
        )
        self.connect_btn.pack(side=tk.RIGHT)
        
        # Discovered peers card
        peers_card = self._create_card(content, "Discovered Computers")
        
        self.peers_frame = tk.Frame(peers_card, bg=COLORS["surface"])
        self.peers_frame.pack(fill=tk.X)
        
        self.no_peers_label = tk.Label(
            self.peers_frame,
            text="🔍 Searching for computers on your network...",
            font=("SF Pro Text", 12),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        )
        self.no_peers_label.pack(pady=8)
        
        # Mode card
        mode_card = self._create_card(content, "Control Mode")
        
        self.mode_label = tk.Label(
            mode_card,
            text="🖥️ Local Control",
            font=("SF Pro Display", 18, "bold"),
            fg=COLORS["text"],
            bg=COLORS["surface"]
        )
        self.mode_label.pack(pady=(0, 8))
        
        self.mode_hint = tk.Label(
            mode_card,
            text="Move mouse to right edge to control connected computer",
            font=("SF Pro Text", 11),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        )
        self.mode_hint.pack()
        
        # Screen Layout Card
        if HAS_LAYOUT_WIDGET:
            self.screen_layout = ScreenLayoutCard(
                content,
                on_layout_change=self._on_layout_change
            )
            self.screen_layout.pack(fill=tk.X, pady=(0, 16))
            
            # Set Mac screens immediately
            self.screen_layout.set_mac_screens(get_screens())
        else:
            self.screen_layout = None
        
        # Settings bar
        settings_bar = tk.Frame(self.root, bg=COLORS["surface"], height=60)
        settings_bar.pack(fill=tk.X, side=tk.BOTTOM)
        settings_bar.pack_propagate(False)
        
        settings_content = tk.Frame(settings_bar, bg=COLORS["surface"])
        settings_content.pack(expand=True, fill=tk.X, padx=24)
        
        # Clipboard toggle
        self.clipboard_var = tk.BooleanVar(value=True)
        clipboard_check = tk.Checkbutton(
            settings_content,
            text="📋 Share Clipboard",
            font=("SF Pro Text", 11),
            fg=COLORS["text"],
            bg=COLORS["surface"],
            variable=self.clipboard_var,
            selectcolor=COLORS["surface"],
            activebackground=COLORS["surface"]
        )
        clipboard_check.pack(side=tk.LEFT)
        
        # Version
        tk.Label(
            settings_content,
            text="v2.0.0",
            font=("SF Pro Text", 10),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(side=tk.RIGHT)
    
    def _create_card(self, parent, title: str) -> tk.Frame:
        """Create a card with title"""
        card = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        card.pack(fill=tk.X, pady=(0, 16))
        
        inner = tk.Frame(card, bg=COLORS["surface"], padx=16, pady=16)
        inner.pack(fill=tk.X)
        
        tk.Label(
            inner,
            text=title,
            font=("SF Pro Text", 11, "bold"),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(anchor="w", pady=(0, 12))
        
        return inner
    
    def _start_services(self):
        """Start network and input services"""
        if self.network.start_server():
            self._update_status("Waiting for connection...", COLORS["warning"])
        else:
            self._update_status("Failed to start server", COLORS["error"])
        
        self.input_handler.start()
        self.clipboard.start()
    
    def _update_status(self, text: str, color: str):
        """Update status display"""
        self.status_label.config(text=text)
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")
    
    def _on_connection_state(self, state: ConnectionState):
        """Handle connection state changes"""
        self.root.after(0, lambda: self._update_connection_ui(state))
    
    def _update_connection_ui(self, state: ConnectionState):
        """Update UI for connection state"""
        if state == ConnectionState.CONNECTED:
            peer_name = self.network.peer_info.get("name", "Unknown") if self.network.peer_info else "Unknown"
            self._update_status(f"Connected to {peer_name}", COLORS["success"])
            self.connect_btn.config(text="Disconnect", bg=COLORS["error"])
        elif state == ConnectionState.CONNECTING:
            self._update_status("Connecting...", COLORS["warning"])
        elif state == ConnectionState.DISCONNECTED:
            self._update_status("Waiting for connection...", COLORS["warning"])
            self.connect_btn.config(text="Connect", bg=COLORS["primary"])
        else:
            self._update_status("Connection error", COLORS["error"])
    
    def _on_message(self, msg_type: str, payload: dict):
        """Handle incoming messages"""
        if msg_type in ("mouse_move", "mouse_button", "mouse_scroll", "key_down", "key_up", "mode_switch"):
            self.input_handler.handle_incoming_input(msg_type, payload)
        elif msg_type == "clipboard_sync":
            if self.clipboard_var.get():
                self.clipboard.handle_incoming(payload)
        elif msg_type == "screen_info":
            # Received Windows screen info - update layout
            self.root.after(0, lambda: self._update_windows_screens(payload))
    
    def _update_windows_screens(self, payload: dict):
        """Update Windows screens in layout widget"""
        if self.screen_layout and "screens" in payload:
            screens = payload["screens"]
            self.screen_layout.set_windows_screens(screens)
            print(f"[UI] Updated Windows screens: {len(screens)} display(s)")
    
    def _on_layout_change(self, position: str):
        """Handle screen layout position change"""
        print(f"[UI] Windows position changed to: {position}")
        
        # Update edge detection in input handler
        if self.input_handler:
            self.input_handler.set_edge(position)
        
        # Update mode hint
        edge_text = {
            "left": "left",
            "right": "right", 
            "top": "top",
            "bottom": "bottom"
        }.get(position, "right")
        
        self.mode_hint.config(
            text=f"Move mouse to {edge_text} edge to control connected computer"
        )
    
    def _on_peer_found(self, peer_info: dict):
        """Handle discovered peer"""
        peer_id = peer_info.get("id")
        if peer_id and peer_id not in self.discovered_peers:
            self.discovered_peers[peer_id] = peer_info
            self.root.after(0, self._update_peers_ui)
    
    def _update_peers_ui(self):
        """Update discovered peers display"""
        for widget in self.peers_frame.winfo_children():
            widget.destroy()
        
        if not self.discovered_peers:
            self.no_peers_label = tk.Label(
                self.peers_frame,
                text="🔍 Searching for computers on your network...",
                font=("SF Pro Text", 12),
                fg=COLORS["text_muted"],
                bg=COLORS["surface"]
            )
            self.no_peers_label.pack(pady=8)
            return
        
        for peer_id, peer in self.discovered_peers.items():
            peer_frame = tk.Frame(self.peers_frame, bg=COLORS["surface_hover"], padx=12, pady=8)
            peer_frame.pack(fill=tk.X, pady=2)
            
            icon = "🖥️" if peer.get("platform") == "windows" else "🍎"
            tk.Label(
                peer_frame,
                text=f"{icon} {peer.get('name', 'Unknown')}",
                font=("SF Pro Text", 12, "bold"),
                fg=COLORS["text"],
                bg=COLORS["surface_hover"]
            ).pack(side=tk.LEFT)
            
            tk.Label(
                peer_frame,
                text=peer.get("ip", ""),
                font=("SF Mono", 11),
                fg=COLORS["text_muted"],
                bg=COLORS["surface_hover"]
            ).pack(side=tk.LEFT, padx=(8, 0))
            
            connect_btn = tk.Button(
                peer_frame,
                text="Connect",
                font=("SF Pro Text", 10),
                bg=COLORS["primary"],
                fg="white",
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda ip=peer.get("ip"): self._connect_to_peer(ip)
            )
            connect_btn.pack(side=tk.RIGHT)
    
    def _connect_to_peer(self, ip: str):
        """Connect to a discovered peer"""
        self.host_entry.delete(0, tk.END)
        self.host_entry.insert(0, ip)
        self._on_connect_click()
    
    def _on_connect_click(self):
        """Handle connect button click"""
        if self.network.state == ConnectionState.CONNECTED:
            self.network.disconnect()
        else:
            host = self.host_entry.get().strip()
            if host:
                self.network.connect_to(host)
    
    def _on_mode_change(self, mode: str):
        """Handle mode changes"""
        self.current_mode = mode
        self.root.after(0, lambda: self._update_mode_ui(mode))
    
    def _update_mode_ui(self, mode: str):
        """Update mode display"""
        if mode == "remote":
            self.mode_label.config(text="🌐 Controlling Remote", fg=COLORS["primary"])
            self.mode_hint.config(text="Move mouse left to return • Press Ctrl+Alt+M to force return")
        elif mode == "controlled":
            self.mode_label.config(text="👆 Being Controlled", fg=COLORS["secondary"])
            self.mode_hint.config(text="Remote computer is controlling this Mac")
        else:
            self.mode_label.config(text="🖥️ Local Control", fg=COLORS["text"])
            self.mode_hint.config(text="Move mouse to right edge to control connected computer")
    
    def _on_close(self):
        """Handle window close"""
        self.input_handler.stop()
        self.clipboard.stop()
        self.network.stop()
        self.root.destroy()
    
    def run(self):
        """Run the application"""
        print(f"MacWinControl 2.0 started on {get_local_ip()}:52525")
        self.root.mainloop()


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    app = ModernApp()
    app.run()
