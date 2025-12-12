// Network module - TCP server and client for input sharing
// Auto-discovery via UDP broadcast - no manual IP needed!

use tokio::net::{TcpListener, TcpStream, UdpSocket};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;
use once_cell::sync::Lazy;
use std::sync::RwLock;
use std::net::SocketAddr;

const TCP_PORT: u16 = 52525;
const UDP_PORT: u16 = 52526;
const DISCOVERY_MAGIC: &str = "MACWINCTRL";

// Global storage for received remote screens
pub static REMOTE_SCREENS: Lazy<RwLock<Vec<ReceivedScreen>>> = Lazy::new(|| RwLock::new(Vec::new()));

// Global storage for discovered peers
pub static DISCOVERED_PEERS: Lazy<RwLock<Vec<DiscoveredPeer>>> = Lazy::new(|| RwLock::new(Vec::new()));

// Connection state
pub static IS_CONNECTED: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));
pub static CONNECTED_TO: Lazy<RwLock<Option<String>>> = Lazy::new(|| RwLock::new(None));

// Global client for sending messages
pub static ACTIVE_CLIENT: Lazy<RwLock<Option<Arc<Mutex<TcpStream>>>>> = Lazy::new(|| RwLock::new(None));

// Control state - which computer has mouse/keyboard control
pub static CONTROL_ACTIVE: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));  // true = we're controlling remote
pub static BEING_CONTROLLED: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));  // true = remote is controlling us

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct DiscoveredPeer {
    pub name: String,
    pub ip: String,
    pub computer_type: String,
    pub last_seen: u64,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ReceivedScreen {
    pub computer_name: String,
    pub computer_type: String,
    pub name: String,
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub is_primary: bool,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ScreenData {
    pub name: String,
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub is_primary: bool,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct Message {
    #[serde(rename = "type")]
    pub msg_type: String,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<i32>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub y: Option<i32>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub button: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key_code: Option<u32>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub screens: Option<Vec<ScreenData>>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub computer_type: Option<String>,
}

impl Message {
    pub fn hello_with_screens(name: &str, screens: Vec<ScreenData>, computer_type: &str) -> Self {
        Message {
            msg_type: "hello".to_string(),
            name: Some(name.to_string()),
            version: Some("1.0".to_string()),
            screens: Some(screens),
            computer_type: Some(computer_type.to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None,
        }
    }
    
    pub fn hello(name: &str) -> Self {
        Message {
            msg_type: "hello".to_string(),
            name: Some(name.to_string()),
            version: Some("1.0".to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, screens: None, computer_type: None,
        }
    }
    
    pub fn mouse_move(x: i32, y: i32) -> Self {
        Message {
            msg_type: "mouse_move".to_string(),
            x: Some(x),
            y: Some(y),
            button: None, action: None, key_code: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
    
    pub fn mouse_click(button: &str, action: &str) -> Self {
        Message {
            msg_type: "mouse_click".to_string(),
            button: Some(button.to_string()),
            action: Some(action.to_string()),
            x: None, y: None, key_code: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
    
    pub fn key_event(key_code: u32, action: &str) -> Self {
        Message {
            msg_type: "key_event".to_string(),
            key_code: Some(key_code),
            action: Some(action.to_string()),
            x: None, y: None, button: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
    
    pub fn clipboard(text: &str) -> Self {
        Message {
            msg_type: "clipboard".to_string(),
            text: Some(text.to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
    
    pub fn ping() -> Self {
        Message {
            msg_type: "ping".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
    
    pub fn pong() -> Self {
        Message {
            msg_type: "pong".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
            screens: None, computer_type: None,
        }
    }
}

pub type ClientList = Arc<Mutex<Vec<Arc<Mutex<TcpStream>>>>>;

pub async fn start_server(port: u16) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await?;
    println!("Server listening on port {}", port);
    
    let clients: ClientList = Arc::new(Mutex::new(Vec::new()));
    
    loop {
        let (stream, addr) = listener.accept().await?;
        println!("New connection from: {}", addr);
        
        let client = Arc::new(Mutex::new(stream));
        clients.lock().await.push(client.clone());
        
        // Store as active client for sending messages
        *ACTIVE_CLIENT.write().unwrap() = Some(client.clone());
        *IS_CONNECTED.write().unwrap() = true;
        *CONNECTED_TO.write().unwrap() = Some(addr.ip().to_string());
        
        let clients_clone = clients.clone();
        tokio::spawn(async move {
            if let Err(e) = handle_client(client, clients_clone).await {
                eprintln!("Client error: {}", e);
            }
        });
    }
}

async fn handle_client(
    client: Arc<Mutex<TcpStream>>,
    _clients: ClientList,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut buffer = vec![0u8; 4096];
    
    // Send hello message with screen info
    {
        let computer_name = get_computer_name();
        let screens = crate::input::get_all_screens();
        let screen_data: Vec<ScreenData> = screens.iter().map(|s| ScreenData {
            name: s.name.clone(),
            x: s.x,
            y: s.y,
            width: s.width,
            height: s.height,
            is_primary: s.is_primary,
        }).collect();
        
        #[cfg(target_os = "macos")]
        let computer_type = "mac";
        #[cfg(target_os = "windows")]
        let computer_type = "windows";
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        let computer_type = "other";
        
        let hello = Message::hello_with_screens(&computer_name, screen_data, computer_type);
        let json = serde_json::to_string(&hello)? + "\n";
        
        let mut stream = client.lock().await;
        stream.write_all(json.as_bytes()).await?;
    }
    
    loop {
        let n = {
            let mut stream = client.lock().await;
            stream.read(&mut buffer).await?
        };
        
        if n == 0 {
            println!("Client disconnected");
            break;
        }
        
        let data = String::from_utf8_lossy(&buffer[..n]);
        for line in data.lines() {
            if let Ok(msg) = serde_json::from_str::<Message>(line) {
                handle_message(&msg, &client).await?;
            }
        }
    }
    
    Ok(())
}

async fn handle_message(
    msg: &Message, 
    client: &Arc<Mutex<TcpStream>>
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    match msg.msg_type.as_str() {
        "ping" => {
            let pong = Message::pong();
            let json = serde_json::to_string(&pong)? + "\n";
            let mut stream = client.lock().await;
            stream.write_all(json.as_bytes()).await?;
        }
        "mouse_move" => {
            if let (Some(x), Some(y)) = (msg.x, msg.y) {
                crate::input::move_mouse(x, y);
            }
        }
        "mouse_click" => {
            if let (Some(button), Some(action)) = (&msg.button, &msg.action) {
                crate::input::mouse_click(button, action);
            }
        }
        "key_event" => {
            if let (Some(key_code), Some(action)) = (msg.key_code, &msg.action) {
                crate::input::key_event(key_code, action);
            }
        }
        "clipboard" => {
            if let Some(text) = &msg.text {
                let _ = crate::clipboard_sync::set_text(text);
            }
        }
        "hello" => {
            let name = msg.name.clone().unwrap_or_else(|| "Unknown".to_string());
            let comp_type = msg.computer_type.clone().unwrap_or_else(|| "unknown".to_string());
            println!("Received hello from: {} ({})", name, comp_type);
            
            // Store received screens
            if let Some(screens) = &msg.screens {
                let mut remote = REMOTE_SCREENS.write().unwrap();
                // Remove old screens from this computer
                remote.retain(|s| s.computer_name != name);
                // Add new screens
                for s in screens {
                    remote.push(ReceivedScreen {
                        computer_name: name.clone(),
                        computer_type: comp_type.clone(),
                        name: s.name.clone(),
                        x: s.x,
                        y: s.y,
                        width: s.width,
                        height: s.height,
                        is_primary: s.is_primary,
                    });
                }
                println!("Stored {} remote screens from {}", screens.len(), name);
            }
        }
        "control_start" => {
            // Remote is taking control of our mouse/keyboard
            println!("🎮 Remote is taking control!");
            *BEING_CONTROLLED.write().unwrap() = true;
            
            // Move mouse to the specified position
            if let (Some(x), Some(y)) = (msg.x, msg.y) {
                crate::input::move_mouse(x, y);
            }
        }
        "control_end" => {
            // Remote is releasing control
            println!("🔓 Remote released control");
            *BEING_CONTROLLED.write().unwrap() = false;
        }
        _ => {
            println!("Unknown message type: {}", msg.msg_type);
        }
    }
    Ok(())
}

pub async fn connect_to_server(ip: &str, port: u16) -> Result<Arc<Mutex<TcpStream>>, Box<dyn std::error::Error + Send + Sync>> {
    let stream = TcpStream::connect(format!("{}:{}", ip, port)).await?;
    println!("Connected to {}:{}", ip, port);
    
    let client = Arc::new(Mutex::new(stream));
    
    // Send hello with screen info
    {
        let computer_name = get_computer_name();
        let screens = crate::input::get_all_screens();
        let screen_data: Vec<ScreenData> = screens.iter().map(|s| ScreenData {
            name: s.name.clone(),
            x: s.x,
            y: s.y,
            width: s.width,
            height: s.height,
            is_primary: s.is_primary,
        }).collect();
        
        #[cfg(target_os = "macos")]
        let computer_type = "mac";
        #[cfg(target_os = "windows")]
        let computer_type = "windows";
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        let computer_type = "other";
        
        let hello = Message::hello_with_screens(&computer_name, screen_data, computer_type);
        let json = serde_json::to_string(&hello)? + "\n";
        
        let mut stream = client.lock().await;
        stream.write_all(json.as_bytes()).await?;
    }
    
    // Store active client for sending messages
    *ACTIVE_CLIENT.write().unwrap() = Some(client.clone());
    
    // Start client read loop to receive messages from server
    let client_clone = client.clone();
    tokio::spawn(async move {
        let mut buffer = vec![0u8; 4096];
        loop {
            let n = {
                let mut stream = client_clone.lock().await;
                match stream.read(&mut buffer).await {
                    Ok(n) => n,
                    Err(_) => break,
                }
            };
            
            if n == 0 {
                println!("Disconnected from server");
                break;
            }
            
            let data = String::from_utf8_lossy(&buffer[..n]);
            for line in data.lines() {
                if let Ok(msg) = serde_json::from_str::<Message>(line) {
                    if let Err(e) = handle_message(&msg, &client_clone).await {
                        eprintln!("Error handling message: {}", e);
                    }
                }
            }
        }
    });
    
    Ok(client)
}

pub async fn send_message(client: &Arc<Mutex<TcpStream>>, msg: &Message) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let json = serde_json::to_string(msg)? + "\n";
    let mut stream = client.lock().await;
    stream.write_all(json.as_bytes()).await?;
    Ok(())
}

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

fn get_computer_type() -> &'static str {
    #[cfg(target_os = "macos")]
    { "mac" }
    #[cfg(target_os = "windows")]
    { "windows" }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    { "other" }
}

// ============= AUTO-DISCOVERY =============

/// Start everything: TCP server + UDP broadcast + UDP listener + mouse tracking
/// When a peer is discovered, automatically connect
pub async fn start_auto_discovery() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let local_ip = local_ip_address::local_ip()
        .map(|ip| ip.to_string())
        .unwrap_or_else(|_| "0.0.0.0".to_string());
    
    println!("🚀 Starting MacWinControl auto-discovery...");
    println!("📍 Local IP: {}", local_ip);
    
    // Start TCP server
    tokio::spawn(async {
        if let Err(e) = start_server(TCP_PORT).await {
            eprintln!("TCP server error: {}", e);
        }
    });
    
    // Start UDP broadcaster (announce our presence)
    let local_ip_clone = local_ip.clone();
    tokio::spawn(async move {
        if let Err(e) = start_udp_broadcaster(&local_ip_clone).await {
            eprintln!("UDP broadcaster error: {}", e);
        }
    });
    
    // Start UDP listener (discover peers)
    let local_ip_clone2 = local_ip.clone();
    tokio::spawn(async move {
        if let Err(e) = start_udp_listener(&local_ip_clone2).await {
            eprintln!("UDP listener error: {}", e);
        }
    });
    
    // Start mouse tracking for edge detection
    tokio::spawn(async {
        start_mouse_tracking().await;
    });
    
    Ok(())
}

/// Broadcast our presence every 2 seconds
async fn start_udp_broadcaster(local_ip: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let socket = UdpSocket::bind("0.0.0.0:0").await?;
    socket.set_broadcast(true)?;
    
    let computer_name = get_computer_name();
    let computer_type = get_computer_type();
    
    // Broadcast message format: MACWINCTRL|name|ip|type
    let message = format!("{}|{}|{}|{}", DISCOVERY_MAGIC, computer_name, local_ip, computer_type);
    
    println!("📢 Broadcasting presence: {}", message);
    
    loop {
        // Broadcast to 255.255.255.255
        let _ = socket.send_to(message.as_bytes(), format!("255.255.255.255:{}", UDP_PORT)).await;
        
        // Also try common subnet broadcasts
        if let Some(subnet) = local_ip.rsplit_once('.') {
            let broadcast_ip = format!("{}.255", subnet.0);
            let _ = socket.send_to(message.as_bytes(), format!("{}:{}", broadcast_ip, UDP_PORT)).await;
        }
        
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    }
}

/// Listen for UDP broadcasts from other peers
async fn start_udp_listener(local_ip: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let socket = UdpSocket::bind(format!("0.0.0.0:{}", UDP_PORT)).await?;
    println!("👂 Listening for peers on UDP port {}", UDP_PORT);
    
    let mut buffer = [0u8; 1024];
    
    loop {
        let (len, addr) = socket.recv_from(&mut buffer).await?;
        let message = String::from_utf8_lossy(&buffer[..len]);
        
        // Parse: MACWINCTRL|name|ip|type
        let parts: Vec<&str> = message.split('|').collect();
        if parts.len() >= 4 && parts[0] == DISCOVERY_MAGIC {
            let peer_name = parts[1].to_string();
            let peer_ip = parts[2].to_string();
            let peer_type = parts[3].to_string();
            
            // Ignore our own broadcasts
            if peer_ip == local_ip {
                continue;
            }
            
            println!("🔍 Discovered peer: {} ({}) at {}", peer_name, peer_type, peer_ip);
            
            // Update discovered peers list
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            
            {
                let mut peers = DISCOVERED_PEERS.write().unwrap();
                if let Some(existing) = peers.iter_mut().find(|p| p.ip == peer_ip) {
                    existing.last_seen = now;
                } else {
                    peers.push(DiscoveredPeer {
                        name: peer_name.clone(),
                        ip: peer_ip.clone(),
                        computer_type: peer_type.clone(),
                        last_seen: now,
                    });
                }
            }
            
            // Auto-connect if not already connected
            let is_connected = *IS_CONNECTED.read().unwrap();
            if !is_connected {
                println!("🔗 Auto-connecting to {}...", peer_ip);
                
                let peer_ip_clone = peer_ip.clone();
                tokio::spawn(async move {
                    match connect_to_server(&peer_ip_clone, TCP_PORT).await {
                        Ok(_) => {
                            println!("✅ Connected to {}", peer_ip_clone);
                            *IS_CONNECTED.write().unwrap() = true;
                            *CONNECTED_TO.write().unwrap() = Some(peer_ip_clone);
                        }
                        Err(e) => {
                            println!("❌ Failed to connect: {}", e);
                        }
                    }
                });
            }
        }
    }
}

/// Get list of discovered peers
pub fn get_discovered_peers() -> Vec<DiscoveredPeer> {
    DISCOVERED_PEERS.read().unwrap().clone()
}

/// Check if connected
pub fn is_connected() -> bool {
    *IS_CONNECTED.read().unwrap()
}

/// Get connected peer IP
pub fn get_connected_to() -> Option<String> {
    CONNECTED_TO.read().unwrap().clone()
}

// ============= MOUSE TRACKING & EDGE DETECTION =============

/// Start mouse tracking - monitors mouse position and handles edge transitions
pub async fn start_mouse_tracking() {
    println!("🖱️ Starting mouse tracking...");
    
    let mut last_pos = (0i32, 0i32);
    let edge_threshold = 2;  // pixels from edge to trigger transition
    
    loop {
        tokio::time::sleep(tokio::time::Duration::from_millis(8)).await;  // ~120 Hz
        
        // Read all state upfront to avoid holding locks across await
        let is_connected = *IS_CONNECTED.read().unwrap();
        let being_controlled = *BEING_CONTROLLED.read().unwrap();
        let control_active = *CONTROL_ACTIVE.read().unwrap();
        
        // Skip if not connected
        if !is_connected {
            continue;
        }
        
        // Skip if we're being controlled (remote has our mouse)
        if being_controlled {
            continue;
        }
        
        let (mx, my) = crate::input::get_mouse_position();
        
        // If position changed
        if mx != last_pos.0 || my != last_pos.1 {
            last_pos = (mx, my);
            
            // If we're controlling remote, send mouse position
            if control_active {
                send_mouse_to_remote(mx, my).await;
            } else {
                // Check for edge transition
                check_edge_transition(mx, my, edge_threshold).await;
            }
        }
    }
}

async fn check_edge_transition(mx: i32, my: i32, threshold: i32) {
    let screens = crate::input::get_all_screens();
    if screens.is_empty() { return; }
    
    // Find current screen bounds
    let total_min_x = screens.iter().map(|s| s.x).min().unwrap_or(0);
    let total_max_x = screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
    let total_min_y = screens.iter().map(|s| s.y).min().unwrap_or(0);
    let total_max_y = screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
    
    // Get remote screens
    let remote_screens = REMOTE_SCREENS.read().unwrap().clone();
    if remote_screens.is_empty() { return; }
    
    // Check edges
    let at_right_edge = mx >= total_max_x - threshold;
    let at_left_edge = mx <= total_min_x + threshold;
    let at_top_edge = my <= total_min_y + threshold;
    let at_bottom_edge = my >= total_max_y - threshold;
    
    if at_right_edge || at_left_edge || at_top_edge || at_bottom_edge {
        println!("🎯 Edge detected! Transitioning control to remote...");
        
        // Calculate starting position on remote
        let (remote_x, remote_y) = if at_right_edge {
            // Enter remote from left side
            let remote_min_x = remote_screens.iter().map(|s| s.x).min().unwrap_or(0);
            (remote_min_x + 10, my)
        } else if at_left_edge {
            // Enter remote from right side  
            let remote_max_x = remote_screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
            (remote_max_x - 10, my)
        } else if at_top_edge {
            (mx, 10)
        } else {
            let remote_max_y = remote_screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
            (mx, remote_max_y - 10)
        };
        
        // Take control of remote
        *CONTROL_ACTIVE.write().unwrap() = true;
        
        // Send control_start message
        send_control_message("control_start", remote_x, remote_y).await;
        
        // Move local mouse to edge (so it stays there)
        let edge_x = if at_right_edge { total_max_x - 1 } else if at_left_edge { total_min_x + 1 } else { mx };
        let edge_y = if at_top_edge { total_min_y + 1 } else if at_bottom_edge { total_max_y - 1 } else { my };
        crate::input::move_mouse(edge_x, edge_y);
    }
}

async fn send_mouse_to_remote(x: i32, y: i32) {
    // Clone the client outside of async context to avoid Send issues
    let client = {
        ACTIVE_CLIENT.read().unwrap().clone()
    };
    
    if let Some(client) = client {
        let msg = Message::mouse_move(x, y);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = client.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

async fn send_control_message(msg_type: &str, x: i32, y: i32) {
    // Clone the client outside of async context
    let client = {
        ACTIVE_CLIENT.read().unwrap().clone()
    };
    
    if let Some(client) = client {
        let msg = Message {
            msg_type: msg_type.to_string(),
            x: Some(x),
            y: Some(y),
            button: None, action: None, key_code: None,
            text: None, name: None, version: None,
            screens: None, computer_type: None,
        };
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = client.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

/// Send keyboard event to remote
pub async fn send_key_to_remote(key_code: u32, action: &str) {
    let is_active = *CONTROL_ACTIVE.read().unwrap();
    if !is_active { return; }
    
    let client = {
        ACTIVE_CLIENT.read().unwrap().clone()
    };
    
    if let Some(client) = client {
        let msg = Message::key_event(key_code, action);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = client.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

/// Send mouse click to remote
pub async fn send_click_to_remote(button: &str, action: &str) {
    let is_active = *CONTROL_ACTIVE.read().unwrap();
    if !is_active { return; }
    
    let client = {
        ACTIVE_CLIENT.read().unwrap().clone()
    };
    
    if let Some(client) = client {
        let msg = Message::mouse_click(button, action);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = client.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

/// Release control back to local
pub fn release_control() {
    *CONTROL_ACTIVE.write().unwrap() = false;
    println!("🔓 Control released back to local");
}
