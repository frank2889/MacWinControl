"""
MacWinControl - Clipboard Manager
Cross-platform clipboard synchronization between Mac and Windows
"""

import subprocess
import threading
import time
from typing import Callable, Optional

class ClipboardManager:
    """
    Manages clipboard synchronization between Mac and Windows
    Uses pbcopy/pbpaste on Mac
    """
    
    def __init__(self):
        self._last_content: str = ""
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._on_change_callback: Optional[Callable[[str], None]] = None
        self._poll_interval = 0.5  # Check every 500ms
    
    def get_clipboard(self) -> str:
        """Get current clipboard content"""
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.stdout
        except Exception as e:
            print(f"[Clipboard] Error reading: {e}")
            return ""
    
    def set_clipboard(self, content: str) -> bool:
        """Set clipboard content"""
        try:
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                text=True
            )
            process.communicate(input=content, timeout=2)
            self._last_content = content
            return True
        except Exception as e:
            print(f"[Clipboard] Error writing: {e}")
            return False
    
    def start_monitoring(self, on_change: Callable[[str], None]):
        """Start monitoring clipboard for changes"""
        if self._monitoring:
            return
        
        self._on_change_callback = on_change
        self._monitoring = True
        self._last_content = self.get_clipboard()
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        print("[Clipboard] Monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring clipboard"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
        print("[Clipboard] Monitoring stopped")
    
    def _monitor_loop(self):
        """Background loop to check for clipboard changes"""
        while self._monitoring:
            try:
                current = self.get_clipboard()
                if current and current != self._last_content:
                    self._last_content = current
                    if self._on_change_callback:
                        self._on_change_callback(current)
            except Exception as e:
                print(f"[Clipboard] Monitor error: {e}")
            
            time.sleep(self._poll_interval)


class ClipboardHistory:
    """
    Maintains a history of clipboard items
    """
    
    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self._history: list[dict] = []
    
    def add(self, content: str, source: str = "local"):
        """Add item to history"""
        item = {
            "content": content,
            "source": source,
            "timestamp": time.time(),
            "preview": content[:100] + "..." if len(content) > 100 else content
        }
        
        # Remove duplicates
        self._history = [h for h in self._history if h["content"] != content]
        
        # Add to front
        self._history.insert(0, item)
        
        # Trim to max
        if len(self._history) > self.max_items:
            self._history = self._history[:self.max_items]
    
    def get_history(self) -> list[dict]:
        """Get clipboard history"""
        return self._history.copy()
    
    def clear(self):
        """Clear history"""
        self._history.clear()
    
    def get_item(self, index: int) -> Optional[str]:
        """Get item by index"""
        if 0 <= index < len(self._history):
            return self._history[index]["content"]
        return None


# Singleton instance
_clipboard_manager: Optional[ClipboardManager] = None
_clipboard_history: Optional[ClipboardHistory] = None

def get_clipboard_manager() -> ClipboardManager:
    """Get or create clipboard manager singleton"""
    global _clipboard_manager
    if _clipboard_manager is None:
        _clipboard_manager = ClipboardManager()
    return _clipboard_manager

def get_clipboard_history() -> ClipboardHistory:
    """Get or create clipboard history singleton"""
    global _clipboard_history
    if _clipboard_history is None:
        _clipboard_history = ClipboardHistory()
    return _clipboard_history
