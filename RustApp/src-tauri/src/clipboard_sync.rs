// Clipboard module - Cross-platform clipboard access using arboard

use arboard::Clipboard;
use std::sync::Mutex;

lazy_static::lazy_static! {
    static ref CLIPBOARD: Mutex<Option<Clipboard>> = Mutex::new(Clipboard::new().ok());
}

pub fn get_text() -> Result<String, String> {
    let mut guard = CLIPBOARD.lock().map_err(|e| e.to_string())?;
    
    if guard.is_none() {
        *guard = Clipboard::new().ok();
    }
    
    match guard.as_mut() {
        Some(clipboard) => clipboard.get_text().map_err(|e| e.to_string()),
        None => Err("Clipboard not available".to_string()),
    }
}

pub fn set_text(text: &str) -> Result<(), String> {
    let mut guard = CLIPBOARD.lock().map_err(|e| e.to_string())?;
    
    if guard.is_none() {
        *guard = Clipboard::new().ok();
    }
    
    match guard.as_mut() {
        Some(clipboard) => clipboard.set_text(text.to_string()).map_err(|e| e.to_string()),
        None => Err("Clipboard not available".to_string()),
    }
}

// Watch for clipboard changes (polling-based) - will be used for clipboard sync feature
#[allow(dead_code)]
pub fn watch_clipboard<F>(mut callback: F)
where
    F: FnMut(String) + Send + 'static,
{
    std::thread::spawn(move || {
        let mut last_text = String::new();
        
        loop {
            if let Ok(text) = get_text() {
                if text != last_text {
                    last_text = text.clone();
                    callback(text);
                }
            }
            std::thread::sleep(std::time::Duration::from_millis(500));
        }
    });
}
