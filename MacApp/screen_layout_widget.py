#!/usr/bin/env python3
"""
MacWinControl - Screen Layout Widget
Visualizes Mac and Windows screen arrangement
"""

import tkinter as tk
from typing import Optional, Dict, List, Callable

# Colors from design system
COLORS = {
    "primary": "#6366f1",
    "secondary": "#8b5cf6",
    "surface": "#ffffff",
    "surface_hover": "#f1f5f9",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "text_muted": "#64748b",
    "success": "#10b981",
    "mac_screen": "#6366f1",      # Indigo for Mac
    "windows_screen": "#8b5cf6",   # Purple for Windows
}


class ScreenLayoutWidget(tk.Frame):
    """
    Visual representation of Mac and Windows screen layout.
    Shows where screens are positioned relative to each other.
    """
    
    def __init__(self, parent, width=400, height=200, **kwargs):
        super().__init__(parent, bg=COLORS["surface"], **kwargs)
        
        self.canvas_width = width
        self.canvas_height = height
        
        # Screen data
        self.mac_screens: List[Dict] = []
        self.windows_screens: List[Dict] = []
        self.windows_position = "right"  # right, left, top, bottom
        
        # Callbacks
        self.on_layout_change: Optional[Callable[[str], None]] = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the widget UI"""
        # Title
        title_frame = tk.Frame(self, bg=COLORS["surface"])
        title_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(
            title_frame,
            text="🖥️ Screen Layout",
            font=("SF Pro Text", 13, "bold"),
            fg=COLORS["text"],
            bg=COLORS["surface"]
        ).pack(side=tk.LEFT)
        
        # Legend
        legend_frame = tk.Frame(title_frame, bg=COLORS["surface"])
        legend_frame.pack(side=tk.RIGHT)
        
        # Mac legend
        mac_dot = tk.Canvas(legend_frame, width=10, height=10, bg=COLORS["surface"], highlightthickness=0)
        mac_dot.pack(side=tk.LEFT, padx=(0, 4))
        mac_dot.create_oval(0, 0, 10, 10, fill=COLORS["mac_screen"], outline="")
        
        tk.Label(
            legend_frame, text="Mac", font=("SF Pro Text", 10),
            fg=COLORS["text_muted"], bg=COLORS["surface"]
        ).pack(side=tk.LEFT, padx=(0, 12))
        
        # Windows legend
        win_dot = tk.Canvas(legend_frame, width=10, height=10, bg=COLORS["surface"], highlightthickness=0)
        win_dot.pack(side=tk.LEFT, padx=(0, 4))
        win_dot.create_oval(0, 0, 10, 10, fill=COLORS["windows_screen"], outline="")
        
        tk.Label(
            legend_frame, text="Windows", font=("SF Pro Text", 10),
            fg=COLORS["text_muted"], bg=COLORS["surface"]
        ).pack(side=tk.LEFT)
        
        # Canvas for drawing screens
        self.canvas = tk.Canvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            bg=COLORS["surface_hover"],
            highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Position buttons
        btn_frame = tk.Frame(self, bg=COLORS["surface"])
        btn_frame.pack(fill=tk.X)
        
        tk.Label(
            btn_frame, text="Windows position:", font=("SF Pro Text", 11),
            fg=COLORS["text_muted"], bg=COLORS["surface"]
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        positions = [("← Left", "left"), ("→ Right", "right"), ("↑ Top", "top"), ("↓ Bottom", "bottom")]
        for label, pos in positions:
            btn = tk.Button(
                btn_frame,
                text=label,
                font=("SF Pro Text", 10),
                bg=COLORS["primary"] if pos == self.windows_position else COLORS["surface_hover"],
                fg="white" if pos == self.windows_position else COLORS["text"],
                relief="flat",
                padx=8,
                pady=4,
                cursor="hand2",
                command=lambda p=pos: self._set_position(p)
            )
            btn.pack(side=tk.LEFT, padx=2)
            setattr(self, f"btn_{pos}", btn)
        
        # Info label
        self.info_label = tk.Label(
            self,
            text="Drag Windows screens or click buttons to rearrange",
            font=("SF Pro Text", 10),
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        )
        self.info_label.pack(pady=(8, 0))
        
        self._draw_placeholder()
    
    def _draw_placeholder(self):
        """Draw placeholder when no screens are set"""
        self.canvas.delete("all")
        self.canvas.create_text(
            self.canvas_width // 2,
            self.canvas_height // 2,
            text="Connect to see screen layout",
            font=("SF Pro Text", 12),
            fill=COLORS["text_muted"]
        )
    
    def set_mac_screens(self, screens: List[Dict]):
        """Set Mac screen data"""
        self.mac_screens = screens
        self._draw_layout()
    
    def set_windows_screens(self, screens: List[Dict]):
        """Set Windows screen data"""
        self.windows_screens = screens
        self._draw_layout()
    
    def _set_position(self, position: str):
        """Set Windows position relative to Mac"""
        old_position = self.windows_position
        self.windows_position = position
        
        # Update button styles
        for pos in ["left", "right", "top", "bottom"]:
            btn = getattr(self, f"btn_{pos}", None)
            if btn:
                if pos == position:
                    btn.config(bg=COLORS["primary"], fg="white")
                else:
                    btn.config(bg=COLORS["surface_hover"], fg=COLORS["text"])
        
        self._draw_layout()
        
        if self.on_layout_change and position != old_position:
            self.on_layout_change(position)
    
    def _draw_layout(self):
        """Draw the screen layout"""
        self.canvas.delete("all")
        
        if not self.mac_screens and not self.windows_screens:
            self._draw_placeholder()
            return
        
        # Calculate bounds
        all_screens = []
        
        # Mac screens at origin
        mac_offset_x = 0
        mac_offset_y = 0
        mac_total_width = 0
        mac_total_height = 0
        
        for s in self.mac_screens:
            mac_total_width = max(mac_total_width, s.get("x", 0) + s.get("width", 1920))
            mac_total_height = max(mac_total_height, s.get("y", 0) + s.get("height", 1080))
        
        # Windows screens offset based on position
        win_total_width = 0
        win_total_height = 0
        for s in self.windows_screens:
            win_total_width = max(win_total_width, s.get("x", 0) + s.get("width", 1920))
            win_total_height = max(win_total_height, s.get("y", 0) + s.get("height", 1080))
        
        win_offset_x = 0
        win_offset_y = 0
        
        if self.windows_position == "right":
            win_offset_x = mac_total_width + 50
            win_offset_y = 0
        elif self.windows_position == "left":
            win_offset_x = -win_total_width - 50
            win_offset_y = 0
        elif self.windows_position == "top":
            win_offset_x = 0
            win_offset_y = -win_total_height - 50
        elif self.windows_position == "bottom":
            win_offset_x = 0
            win_offset_y = mac_total_height + 50
        
        # Calculate total bounds
        total_min_x = min(0, win_offset_x)
        total_max_x = max(mac_total_width, win_offset_x + win_total_width)
        total_min_y = min(0, win_offset_y)
        total_max_y = max(mac_total_height, win_offset_y + win_total_height)
        
        total_width = total_max_x - total_min_x
        total_height = total_max_y - total_min_y
        
        # Scale to fit canvas
        padding = 20
        scale_x = (self.canvas_width - padding * 2) / max(total_width, 1)
        scale_y = (self.canvas_height - padding * 2) / max(total_height, 1)
        scale = min(scale_x, scale_y, 0.15)  # Cap scale
        
        # Center offset
        center_offset_x = (self.canvas_width - total_width * scale) / 2 - total_min_x * scale
        center_offset_y = (self.canvas_height - total_height * scale) / 2 - total_min_y * scale
        
        # Draw Mac screens
        for i, s in enumerate(self.mac_screens):
            x = s.get("x", 0) * scale + center_offset_x
            y = s.get("y", 0) * scale + center_offset_y
            w = s.get("width", 1920) * scale
            h = s.get("height", 1080) * scale
            
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                fill=COLORS["mac_screen"],
                outline=COLORS["border"],
                width=2
            )
            
            label = "🍎 Primary" if s.get("is_primary") else f"🍎 {i + 1}"
            self.canvas.create_text(
                x + w / 2, y + h / 2,
                text=label,
                font=("SF Pro Text", 10, "bold"),
                fill="white"
            )
        
        # Draw Windows screens
        for i, s in enumerate(self.windows_screens):
            x = (s.get("x", 0) + win_offset_x) * scale + center_offset_x
            y = (s.get("y", 0) + win_offset_y) * scale + center_offset_y
            w = s.get("width", 1920) * scale
            h = s.get("height", 1080) * scale
            
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                fill=COLORS["windows_screen"],
                outline=COLORS["border"],
                width=2
            )
            
            label = "🪟 Primary" if s.get("is_primary") else f"🪟 {i + 1}"
            self.canvas.create_text(
                x + w / 2, y + h / 2,
                text=label,
                font=("SF Pro Text", 10, "bold"),
                fill="white"
            )
        
        # Draw connection indicator (arrow)
        self._draw_connection_arrow(
            mac_total_width, mac_total_height,
            win_offset_x, win_offset_y, win_total_width, win_total_height,
            scale, center_offset_x, center_offset_y
        )
    
    def _draw_connection_arrow(self, mac_w, mac_h, win_x, win_y, win_w, win_h, scale, cx, cy):
        """Draw arrow showing connection between screens"""
        if self.windows_position == "right":
            # Arrow from right edge of Mac to left edge of Windows
            x1 = mac_w * scale + cx
            y1 = mac_h / 2 * scale + cy
            x2 = win_x * scale + cx
            y2 = (win_y + win_h / 2) * scale + cy
        elif self.windows_position == "left":
            x1 = cx
            y1 = mac_h / 2 * scale + cy
            x2 = (win_x + win_w) * scale + cx
            y2 = (win_y + win_h / 2) * scale + cy
        elif self.windows_position == "top":
            x1 = mac_w / 2 * scale + cx
            y1 = cy
            x2 = (win_x + win_w / 2) * scale + cx
            y2 = (win_y + win_h) * scale + cy
        else:  # bottom
            x1 = mac_w / 2 * scale + cx
            y1 = mac_h * scale + cy
            x2 = (win_x + win_w / 2) * scale + cx
            y2 = win_y * scale + cy
        
        # Draw dashed line with arrow
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill=COLORS["success"],
            width=2,
            dash=(4, 4),
            arrow=tk.LAST
        )
    
    def get_edge(self) -> str:
        """Get the edge where Windows is positioned (for edge detection)"""
        return self.windows_position


class ScreenLayoutCard(tk.Frame):
    """
    Card wrapper for ScreenLayoutWidget
    """
    
    def __init__(self, parent, on_layout_change: Optional[Callable] = None, **kwargs):
        super().__init__(parent, bg=COLORS["surface"], **kwargs)
        
        self.configure(
            highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        
        inner = tk.Frame(self, bg=COLORS["surface"], padx=16, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)
        
        self.layout_widget = ScreenLayoutWidget(inner)
        self.layout_widget.pack(fill=tk.BOTH, expand=True)
        
        if on_layout_change:
            self.layout_widget.on_layout_change = on_layout_change
    
    def set_mac_screens(self, screens: List[Dict]):
        self.layout_widget.set_mac_screens(screens)
    
    def set_windows_screens(self, screens: List[Dict]):
        self.layout_widget.set_windows_screens(screens)
    
    def get_edge(self) -> str:
        return self.layout_widget.get_edge()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Screen Layout Test")
    root.geometry("500x400")
    root.configure(bg="#f8fafc")
    
    def on_change(pos):
        print(f"Layout changed: Windows is now on {pos}")
    
    card = ScreenLayoutCard(root, on_layout_change=on_change)
    card.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Simulate Mac screens
    card.set_mac_screens([
        {"id": "0", "name": "Built-in", "width": 1920, "height": 1200, "x": 0, "y": 0, "is_primary": True},
        {"id": "1", "name": "External", "width": 1920, "height": 1080, "x": -155, "y": 0, "is_primary": False}
    ])
    
    # Simulate Windows screens  
    card.set_windows_screens([
        {"id": "0", "name": "Primary", "width": 1920, "height": 1080, "x": 0, "y": 0, "is_primary": True}
    ])
    
    root.mainloop()
