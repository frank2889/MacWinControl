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
    pub remote_screens: Vec<RemoteScreenInfo>,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct RemoteScreenInfo {
    pub computer_name: String,
    pub computer_type: String,  // "mac" or "windows"
    pub name: String,
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub is_primary: bool,
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
async fn start_server(_state: State<'_, Arc<Mutex<AppState>>>) -> Result<String, String> {
    // Auto-discovery handles everything now
    Ok("Auto-discovery active".to_string())
}

#[tauri::command]
async fn connect_to_server(_ip: String, _state: State<'_, Arc<Mutex<AppState>>>) -> Result<String, String> {
    // Auto-discovery handles everything now
    Ok("Auto-discovery will connect automatically".to_string())
}

#[tauri::command]
fn get_connection_status() -> ConnectionStatus {
    ConnectionStatus {
        is_connected: network::is_connected(),
        connected_to: network::get_connected_to(),
        discovered_peers: network::get_discovered_peers()
            .into_iter()
            .map(|p| PeerInfo {
                name: p.name,
                ip: p.ip,
                computer_type: p.computer_type,
            })
            .collect(),
    }
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ConnectionStatus {
    pub is_connected: bool,
    pub connected_to: Option<String>,
    pub discovered_peers: Vec<PeerInfo>,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct PeerInfo {
    pub name: String,
    pub ip: String,
    pub computer_type: String,
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

#[tauri::command]
fn get_remote_screens(_state: State<'_, Arc<Mutex<AppState>>>) -> Vec<RemoteScreenInfo> {
    // Read from global storage in network module
    let remote = network::REMOTE_SCREENS.read().unwrap();
    remote.iter().map(|s| RemoteScreenInfo {
        computer_name: s.computer_name.clone(),
        computer_type: s.computer_type.clone(),
        name: s.name.clone(),
        x: s.x,
        y: s.y,
        width: s.width,
        height: s.height,
        is_primary: s.is_primary,
    }).collect()
}

#[tauri::command]
fn set_remote_screens(screens: Vec<RemoteScreenInfo>, state: State<'_, Arc<Mutex<AppState>>>) -> Result<(), String> {
    let mut app_state = state.lock().map_err(|e| e.to_string())?;
    app_state.remote_screens = screens;
    Ok(())
}

#[tauri::command]
fn set_screen_layout(remote_edge: String) -> Result<(), String> {
    // Set which edge leads to remote screens
    // Valid values: "right", "left", "top", "bottom"
    let valid_edges = ["right", "left", "top", "bottom"];
    if !valid_edges.contains(&remote_edge.as_str()) {
        return Err(format!("Invalid edge: {}. Must be one of: {:?}", remote_edge, valid_edges));
    }
    *network::REMOTE_EDGE.write().unwrap() = remote_edge.clone();
    println!("📐 Screen layout updated: Windows is to the {} of Mac", remote_edge);
    Ok(())
}

#[tauri::command]
fn get_screen_layout() -> String {
    network::REMOTE_EDGE.read().unwrap().clone()
}

#[tauri::command]
fn get_synced_layout() -> Option<String> {
    network::SYNCED_LAYOUT.read().unwrap().clone()
}

#[tauri::command]
async fn send_layout_sync(layout_json: String) -> Result<(), String> {
    // Send layout to connected peer
    network::send_layout_sync(&layout_json).await.map_err(|e| e.to_string())
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct DebugInfoResponse {
    pub mouse_x: i32,
    pub mouse_y: i32,
    pub screen_bounds: String,
    pub edge_status: String,
    pub remote_screen_count: usize,
    pub last_update: u64,
}

#[tauri::command]
fn get_debug_info() -> DebugInfoResponse {
    let debug = network::get_debug_info();
    DebugInfoResponse {
        mouse_x: debug.mouse_x,
        mouse_y: debug.mouse_y,
        screen_bounds: debug.screen_bounds,
        edge_status: debug.edge_status,
        remote_screen_count: debug.remote_screen_count,
        last_update: debug.last_update,
    }
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
        remote_screens: Vec::new(),
    }));

    // Start auto-discovery in the background
    std::thread::spawn(|| {
        let rt = tokio::runtime::Runtime::new().unwrap();
        rt.block_on(async {
            if let Err(e) = network::start_auto_discovery().await {
                eprintln!("Auto-discovery error: {}", e);
            }
            // Keep runtime alive
            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
            }
        });
    });

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
            get_remote_screens,
            set_remote_screens,
            set_screen_layout,
            get_screen_layout,
            get_synced_layout,
            send_layout_sync,
            get_connection_status,
            get_debug_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
