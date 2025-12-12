"""
MacWinControl - Shared Protocol
Defines message types for bidirectional communication
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import json


class MessageType(Enum):
    # Connection
    HELLO = "hello"
    CONNECTED = "connected"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    
    # Discovery
    DISCOVER = "discover"
    ANNOUNCE = "announce"
    
    # Mode switching
    MODE_SWITCH = "mode_switch"
    
    # Input events
    MOUSE_MOVE = "mouse_move"
    MOUSE_BUTTON = "mouse_button"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    
    # Clipboard
    CLIPBOARD_SYNC = "clipboard_sync"
    CLIPBOARD_REQUEST = "clipboard_request"
    
    # Screen config
    SCREEN_INFO = "screen_info"
    SCREEN_LAYOUT = "screen_layout"
    
    # Settings
    SETTINGS_UPDATE = "settings_update"


@dataclass
class ScreenInfo:
    """Information about a screen/monitor"""
    id: str
    name: str
    width: int
    height: int
    x: int  # Position in virtual desktop
    y: int
    is_primary: bool = False
    scale: float = 1.0


@dataclass
class ComputerInfo:
    """Information about a computer"""
    id: str
    name: str
    platform: str  # "mac", "windows", "linux"
    ip: str
    port: int
    screens: List[ScreenInfo]
    is_server: bool = False


@dataclass
class MouseMoveEvent:
    """Mouse movement event"""
    x: int
    y: int
    absolute: bool = True  # False for relative/delta movement


@dataclass
class MouseButtonEvent:
    """Mouse button event"""
    button: str  # "left", "right", "middle"
    action: str  # "down", "up", "click", "double_click"
    x: int = 0
    y: int = 0


@dataclass
class MouseScrollEvent:
    """Mouse scroll event"""
    delta_x: int
    delta_y: int


@dataclass
class KeyEvent:
    """Keyboard event"""
    key_code: int  # Virtual key code
    action: str  # "down", "up"
    modifiers: Dict[str, bool] = None  # shift, ctrl, alt, cmd/win
    
    def __post_init__(self):
        if self.modifiers is None:
            self.modifiers = {"shift": False, "ctrl": False, "alt": False, "meta": False}


@dataclass
class ClipboardData:
    """Clipboard content"""
    content_type: str  # "text", "image", "files"
    data: str  # For text: the string, for others: base64 encoded
    source: str  # Computer ID that originated the copy


@dataclass
class ScreenLayout:
    """Layout of screens across all computers"""
    computers: List[ComputerInfo]
    edges: Dict[str, str]  # "computer_id:screen_id:edge" -> "computer_id:screen_id"


class Message:
    """Base message class"""
    
    def __init__(self, msg_type: MessageType, payload: Any = None):
        self.type = msg_type
        self.payload = payload
    
    def to_json(self) -> str:
        data = {
            "type": self.type.value,
            "payload": self._serialize_payload()
        }
        return json.dumps(data) + "\n"
    
    def _serialize_payload(self):
        if self.payload is None:
            return None
        if hasattr(self.payload, '__dataclass_fields__'):
            return asdict(self.payload)
        if isinstance(self.payload, dict):
            return self.payload
        if isinstance(self.payload, list):
            return [asdict(p) if hasattr(p, '__dataclass_fields__') else p for p in self.payload]
        return self.payload
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str.strip())
        msg_type = MessageType(data["type"])
        return cls(msg_type, data.get("payload"))
    
    def __repr__(self):
        return f"Message({self.type.value}, {self.payload})"


# Key mapping between Mac and Windows
KEY_MAP_MAC_TO_WIN = {
    # Modifiers
    55: 91,   # Cmd -> Win
    56: 16,   # Shift
    58: 18,   # Alt/Option
    59: 17,   # Ctrl
    
    # Arrow keys
    123: 37,  # Left
    124: 39,  # Right
    125: 40,  # Down
    126: 38,  # Up
    
    # Function keys
    122: 112,  # F1
    120: 113,  # F2
    99: 114,   # F3
    118: 115,  # F4
    96: 116,   # F5
    97: 117,   # F6
    98: 118,   # F7
    100: 119,  # F8
    101: 120,  # F9
    109: 121,  # F10
    103: 122,  # F11
    111: 123,  # F12
    
    # Special keys
    36: 13,   # Return -> Enter
    48: 9,    # Tab
    51: 8,    # Delete -> Backspace
    53: 27,   # Escape
    49: 32,   # Space
    117: 46,  # Forward Delete -> Delete
}

KEY_MAP_WIN_TO_MAC = {v: k for k, v in KEY_MAP_MAC_TO_WIN.items()}


def translate_key(key_code: int, from_platform: str, to_platform: str) -> int:
    """Translate key code between platforms"""
    if from_platform == to_platform:
        return key_code
    
    if from_platform == "mac" and to_platform == "windows":
        return KEY_MAP_MAC_TO_WIN.get(key_code, key_code)
    elif from_platform == "windows" and to_platform == "mac":
        return KEY_MAP_WIN_TO_MAC.get(key_code, key_code)
    
    return key_code
