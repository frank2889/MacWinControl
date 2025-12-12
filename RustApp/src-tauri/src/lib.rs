// MacWinControl - Cross-platform mouse/keyboard sharing
// Works on both macOS and Windows from a single codebase

mod network;
mod input;
mod clipboard_sync;

use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use tauri::State;

// Shared application state
pub struct AppState {
    pub is_server: bool,
    pub is_connected: bool,
    pub active_computer: Option<String>,
    pub computers: Vec<ComputerInfo>,
    pub local_ip: String,
    pub clipboard_sync_enabled: bool,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ComputerInfo {
    pub name: String,
    pub ip: String,
    pub position: String,  // "left", "right", "top", "bottom"
    pub is_connected: bool,
    pub screen_width: i32,
    pub screen_height: i32,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct InputEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub x: Option<i32>,
    pub y: Option<i32>,
    pub button: Option<String>,
    pub key_code: Option<u32>,
    pub modifiers: Option<Modifiers>,
}

#[derive(Clone, Serialize, Deserialize, Debug, Default)]
pub struct Modifiers {
    pub shift: bool,
    pub control: bool,
    pub alt: bool,
    pub meta: bool,
}

// Tauri commands

#[tauri::command]
fn get_local_ip() -> String {
    local_ip_address::local_ip()
        .map(|ip| ip.to_string())
        .unwrap_or_else(|_| "Unknown".to_string())
}

#[tauri::command]
fn get_computer_name() -> String {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("scutil")
            .args(["--get", "ComputerName"])
            .output()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
            .unwrap_or_else(|_| "Mac".to_string())
    }
    #[cfg(target_os = "windows")]
    {
        std::env::var("COMPUTERNAME").unwrap_or_else(|_| "Windows PC".to_string())
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        "Unknown".to_string()
    }
}

#[tauri::command]
async fn start_server(state: State<'_, Arc<Mutex<AppState>>>) -> Result<String, String> {
    {
        let mut app_state = state.lock().map_err(|e| e.to_string())?;
        app_state.is_server = true;
    }
    
    tokio::spawn(async {
        if let Err(e) = network::start_server(52525).await {
            eprintln!("Server error: {}", e);
        }
    });
    
    Ok("Server started on port 52525".to_string())
}

#[tauri::command]
async fn connect_to_server(ip: String, state: State<'_, Arc<Mutex<AppState>>>) -> Result<String, String> {
    match network::connect_to_server(&ip, 52525).await {
        Ok(_) => {
            let mut app_state = state.lock().map_err(|e| e.to_string())?;
            app_state.is_connected = true;
            Ok(format!("Connected to {}", ip))
        }
        Err(e) => Err(format!("Connection failed: {}", e))
    }
}

#[tauri::command]
fn add_computer(name: String, ip: String, position: String, state: State<'_, Arc<Mutex<AppState>>>) -> Result<(), String> {
    let mut app_state = state.lock().map_err(|e| e.to_string())?;
    
    app_state.computers.push(ComputerInfo {
        name,
        ip,
        position,
        is_connected: false,
        screen_width: 1920,
        screen_height: 1080,
    });
    Ok(())
}

#[tauri::command]
fn get_computers(state: State<'_, Arc<Mutex<AppState>>>) -> Result<Vec<ComputerInfo>, String> {
    let app_state = state.lock().map_err(|e| e.to_string())?;
    Ok(app_state.computers.clone())
}

#[tauri::command]
fn remove_computer(ip: String, state: State<'_, Arc<Mutex<AppState>>>) -> Result<(), String> {
    let mut app_state = state.lock().map_err(|e| e.to_string())?;
    app_state.computers.retain(|c| c.ip != ip);
    Ok(())
}

#[tauri::command]
fn set_clipboard_sync(enabled: bool, state: State<'_, Arc<Mutex<AppState>>>) -> Result<(), String> {
    let mut app_state = state.lock().map_err(|e| e.to_string())?;
    app_state.clipboard_sync_enabled = enabled;
    Ok(())
}

#[tauri::command]
fn get_clipboard_text() -> Result<String, String> {
    clipboard_sync::get_text().map_err(|e| e.to_string())
}

#[tauri::command]
fn set_clipboard_text(text: String) -> Result<(), String> {
    clipboard_sync::set_text(&text).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_screen_info() -> (i32, i32) {
    input::get_screen_size()
}

#[tauri::command]
fn get_all_screens() -> Vec<input::ScreenInfo> {
    input::get_all_screens()
}

#[tauri::command]
fn get_mouse_position() -> (i32, i32) {
    input::get_mouse_position()
}

#[tauri::command]
fn is_connected(state: State<'_, Arc<Mutex<AppState>>>) -> bool {
    state.lock().map(|s| s.is_connected).unwrap_or(false)
}

#[tauri::command]
fn is_server(state: State<'_, Arc<Mutex<AppState>>>) -> bool {
    state.lock().map(|s| s.is_server).unwrap_or(false)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app_state = Arc::new(Mutex::new(AppState {
        is_server: false,
        is_connected: false,
        active_computer: None,
        computers: Vec::new(),
        local_ip: get_local_ip(),
        clipboard_sync_enabled: true,
    }));

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_local_ip,
            get_computer_name,
            start_server,
            connect_to_server,
            add_computer,
            get_computers,
            remove_computer,
            set_clipboard_sync,
            get_clipboard_text,
            set_clipboard_text,
            get_screen_info,
            get_all_screens,
            get_mouse_position,
            is_connected,
            is_server,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
