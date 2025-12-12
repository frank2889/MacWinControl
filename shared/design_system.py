"""
MacWinControl - Unified Design System
Based on demo.css premium palette
"""

# Color Palette - Premium
COLORS = {
    # Primary
    "primary": "#6366f1",
    "primary_hover": "#4f46e5",
    "primary_light": "#eef2ff",  # Light indigo (no rgba for Tkinter)
    
    # Secondary
    "secondary": "#8b5cf6",
    "secondary_hover": "#7c3aed",
    
    # Accent
    "accent": "#06b6d4",
    
    # Backgrounds
    "bg": "#f8fafc",
    "surface": "#ffffff",
    "surface_hover": "#f1f5f9",
    
    # Borders
    "border": "#e2e8f0",
    "border_hover": "#cbd5e1",
    
    # Text
    "text": "#0f172a",
    "text_muted": "#64748b",
    
    # Status
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
    
    # Dark mode variants
    "dark_bg": "#0f172a",
    "dark_surface": "#1e293b",
    "dark_border": "#334155",
    "dark_text": "#f8fafc",
    "dark_text_muted": "#94a3b8",
}

# Spacing
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "2xl": 48,
}

# Border Radius
RADIUS = {
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "full": 9999,
}

# Font Sizes
FONTS = {
    "xs": 11,
    "sm": 12,
    "base": 14,
    "lg": 16,
    "xl": 18,
    "2xl": 20,
    "3xl": 24,
    "4xl": 30,
}

# Icon paths (SF Symbols for Mac, Segoe MDL2 for Windows)
ICONS = {
    "computer": "💻",
    "connected": "🔗",
    "disconnected": "⛓️‍💥",
    "mouse": "🖱️",
    "keyboard": "⌨️",
    "clipboard": "📋",
    "settings": "⚙️",
    "screen": "🖥️",
    "arrow_right": "→",
    "arrow_left": "←",
    "check": "✓",
    "close": "✕",
    "warning": "⚠️",
    "info": "ℹ️",
    "lock": "🔒",
    "unlock": "🔓",
}

# App Configuration
APP_CONFIG = {
    "name": "MacWinControl",
    "version": "2.0.0",
    "port": 52525,
    "discovery_port": 52526,
    "window_width": 480,
    "window_height": 640,
}
