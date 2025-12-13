// Network module - TCP server and client for input sharing
// Auto-discovery via UDP broadcast - no manual IP needed!

use tokio::net::{TcpListener, TcpStream, UdpSocket};
use tokio::net::tcp::OwnedWriteHalf;
use tokio::io::{AsyncReadExt, AsyncWriteExt, AsyncBufReadExt, BufReader};
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

// Separate write half for sending messages (avoids deadlock with read loop)
pub static WRITE_STREAM: Lazy<RwLock<Option<Arc<Mutex<OwnedWriteHalf>>>>> = Lazy::new(|| RwLock::new(None));

// Legacy - still used for some things but being phased out
pub static ACTIVE_CLIENT: Lazy<RwLock<Option<Arc<Mutex<TcpStream>>>>> = Lazy::new(|| RwLock::new(None));
// Track if ACTIVE_CLIENT is an outgoing connection (we initiated it)
pub static IS_OUTGOING_CONNECTION: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));

// Control state - which computer has mouse/keyboard control
pub static CONTROL_ACTIVE: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));  // true = we're controlling remote
pub static BEING_CONTROLLED: Lazy<RwLock<bool>> = Lazy::new(|| RwLock::new(false));  // true = remote is controlling us

// Edge lock state - where to keep local mouse pinned while controlling remote
pub static EDGE_LOCK_POS: Lazy<RwLock<(i32, i32)>> = Lazy::new(|| RwLock::new((0, 0)));
// Current remote mouse position (tracked locally)
pub static REMOTE_MOUSE_POS: Lazy<RwLock<(i32, i32)>> = Lazy::new(|| RwLock::new((0, 0)));
// Timestamp when control started (to prevent immediate return)
pub static CONTROL_START_TIME: Lazy<RwLock<u64>> = Lazy::new(|| RwLock::new(0));

// Screen layout configuration - which edge leads to which computer
// Format: "right" means Windows is to the right of Mac
pub static REMOTE_EDGE: Lazy<RwLock<String>> = Lazy::new(|| RwLock::new("right".to_string()));

// Synced layout from remote (JSON string of screen positions)
pub static SYNCED_LAYOUT: Lazy<RwLock<Option<String>>> = Lazy::new(|| RwLock::new(None));

// Debug state for UI
pub static DEBUG_INFO: Lazy<RwLock<DebugInfo>> = Lazy::new(|| RwLock::new(DebugInfo::default()));

#[derive(Clone, Serialize, Debug, Default)]
pub struct DebugInfo {
    pub mouse_x: i32,
    pub mouse_y: i32,
    pub screen_bounds: String,
    pub edge_status: String,
    pub remote_screen_count: usize,
    pub last_update: u64,
}

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
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub layout: Option<String>,  // JSON string of saved layout positions
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
            key_code: None, text: None, layout: None,
        }
    }
    
    pub fn hello(name: &str) -> Self {
        Message {
            msg_type: "hello".to_string(),
            name: Some(name.to_string()),
            version: Some("1.0".to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn mouse_move(x: i32, y: i32) -> Self {
        Message {
            msg_type: "mouse_move".to_string(),
            x: Some(x),
            y: Some(y),
            button: None, action: None, key_code: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn mouse_click(button: &str, action: &str) -> Self {
        Message {
            msg_type: "mouse_click".to_string(),
            button: Some(button.to_string()),
            action: Some(action.to_string()),
            x: None, y: None, key_code: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn key_event(key_code: u32, action: &str) -> Self {
        Message {
            msg_type: "key_event".to_string(),
            key_code: Some(key_code),
            action: Some(action.to_string()),
            x: None, y: None, button: None, 
            text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn clipboard(text: &str) -> Self {
        Message {
            msg_type: "clipboard".to_string(),
            text: Some(text.to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn ping() -> Self {
        Message {
            msg_type: "ping".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn pong() -> Self {
        Message {
            msg_type: "pong".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        }
    }
    
    pub fn layout_sync(layout_json: &str) -> Self {
        Message {
            msg_type: "layout_sync".to_string(),
            layout: Some(layout_json.to_string()),
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
        
        // Only set as ACTIVE_CLIENT if we don't already have an outgoing connection
        // This prevents overwriting our outgoing connection with incoming ones
        let has_outgoing = *IS_OUTGOING_CONNECTION.read().unwrap();
        if !has_outgoing {
            println!("📝 Using incoming connection as ACTIVE_CLIENT (no outgoing yet)");
            *ACTIVE_CLIENT.write().unwrap() = Some(client.clone());
        } else {
            println!("📝 Keeping existing outgoing connection as ACTIVE_CLIENT");
        }
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
                // Only move if we're being controlled by remote
                let being_controlled = *BEING_CONTROLLED.read().unwrap();
                if being_controlled {
                    crate::input::move_mouse(x, y);
                }
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
            println!("📩 Received hello from: {} ({})", name, comp_type);
            
            // Store received screens
            if let Some(screens) = &msg.screens {
                println!("   📺 Received {} screens", screens.len());
                for s in screens {
                    println!("      - {} {}x{} at ({},{})", s.name, s.width, s.height, s.x, s.y);
                }
                
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
                println!("   ✅ Now have {} total remote screens", remote.len());
            } else {
                println!("   ⚠️ No screens in hello message!");
            }
        }
        "control_start" => {
            // Remote is taking control of our mouse/keyboard
            println!("🎮 Remote is taking control!");
            *BEING_CONTROLLED.write().unwrap() = true;
            
            // Move mouse to the specified position
            if let (Some(x), Some(y)) = (msg.x, msg.y) {
                println!("🖱️ Moving mouse to ({}, {})", x, y);
                // Clamp to valid screen coordinates
                let screens = crate::input::get_all_screens();
                let min_x = screens.iter().map(|s| s.x).min().unwrap_or(0);
                let max_x = screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
                let min_y = screens.iter().map(|s| s.y).min().unwrap_or(0);
                let max_y = screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
                
                let clamped_x = x.clamp(min_x, max_x - 1);
                let clamped_y = y.clamp(min_y, max_y - 1);
                
                println!("   Screen bounds: x={}-{}, y={}-{}", min_x, max_x, min_y, max_y);
                println!("   Clamped position: ({}, {})", clamped_x, clamped_y);
                
                crate::input::move_mouse(clamped_x, clamped_y);
                
                // Verify the move worked
                let (actual_x, actual_y) = crate::input::get_mouse_position();
                println!("   Actual position after move: ({}, {})", actual_x, actual_y);
            }
        }
        "control_end" => {
            // Remote is releasing control
            println!("🔓 Remote released control");
            *BEING_CONTROLLED.write().unwrap() = false;
        }
        "layout_sync" => {
            // Remote is sending their screen layout
            if let Some(layout) = &msg.layout {
                println!("📐 Received layout sync: {}", layout);
                *SYNCED_LAYOUT.write().unwrap() = Some(layout.clone());
            }
        }
        _ => {
            println!("Unknown message type: {}", msg.msg_type);
        }
    }
    Ok(())
}

/// Simplified message handler for client read loop (doesn't need stream reference)
async fn handle_message_simple(msg: &Message) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    match msg.msg_type.as_str() {
        "hello" => {
            if let Some(ref name) = msg.name {
                let comp_type = msg.computer_type.clone().unwrap_or_else(|| "unknown".to_string());
                println!("📩 Received hello from: {} ({})", name, comp_type);
                
                if let Some(ref screens) = msg.screens {
                    println!("   📺 Received {} screens", screens.len());
                    let mut remote = REMOTE_SCREENS.write().unwrap();
                    remote.retain(|s| s.computer_name != *name);
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
                    println!("   ✅ Now have {} total remote screens", remote.len());
                }
            }
        }
        "control_start" => {
            println!("🎮 Remote is taking control!");
            *BEING_CONTROLLED.write().unwrap() = true;
            if let (Some(x), Some(y)) = (msg.x, msg.y) {
                println!("🖱️ Moving mouse to ({}, {})", x, y);
                crate::input::move_mouse(x, y);
            }
        }
        "control_end" => {
            println!("🔓 Remote released control");
            *BEING_CONTROLLED.write().unwrap() = false;
        }
        "layout_sync" => {
            if let Some(layout) = &msg.layout {
                println!("📐 Received layout sync: {}", layout);
                *SYNCED_LAYOUT.write().unwrap() = Some(layout.clone());
            }
        }
        "mouse_move" => {
            if let (Some(x), Some(y)) = (msg.x, msg.y) {
                // Only move if we're being controlled by remote
                let being_controlled = *BEING_CONTROLLED.read().unwrap();
                if being_controlled {
                    crate::input::move_mouse(x, y);
                }
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
        _ => {
            println!("Unknown message type: {}", msg.msg_type);
        }
    }
    Ok(())
}

pub async fn connect_to_server(ip: &str, port: u16) -> Result<Arc<Mutex<TcpStream>>, Box<dyn std::error::Error + Send + Sync>> {
    let stream = TcpStream::connect(format!("{}:{}", ip, port)).await?;
    println!("Connected to {}:{}", ip, port);
    
    // Split the stream into read and write halves
    let (read_half, write_half) = stream.into_split();
    
    // Store write half for sending messages (non-blocking!)
    let write_arc = Arc::new(Mutex::new(write_half));
    println!("📤 Setting WRITE_STREAM for sending messages");
    *WRITE_STREAM.write().unwrap() = Some(write_arc.clone());
    *IS_OUTGOING_CONNECTION.write().unwrap() = true;
    
    // Send hello with screen info using the write half
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
        
        let mut writer = write_arc.lock().await;
        writer.write_all(json.as_bytes()).await?;
    }
    
    // Start client read loop to receive messages from server (uses read half only)
    tokio::spawn(async move {
        let mut reader = BufReader::new(read_half);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line).await {
                Ok(0) => {
                    println!("Disconnected from server");
                    break;
                }
                Ok(_) => {
                    if let Ok(msg) = serde_json::from_str::<Message>(&line) {
                        // Create a dummy client for handle_message (not used for control_start)
                        let dummy = Arc::new(Mutex::new(TcpStream::connect("127.0.0.1:1").await.ok()));
                        // We can't easily pass the stream here, but handle_message for received messages
                        // doesn't need to write back for control_start - it just calls move_mouse
                        if let Err(e) = handle_message_simple(&msg).await {
                            eprintln!("Error handling message: {}", e);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Read error: {}", e);
                    break;
                }
            }
        }
    });
    
    // Return a dummy Arc for compatibility (not used anymore)
    let dummy_stream = TcpStream::connect(format!("{}:{}", ip, port)).await?;
    Ok(Arc::new(Mutex::new(dummy_stream)))
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
            
            // Auto-connect if we don't have a write stream yet
            // (incoming connections don't give us a write stream for sending)
            let has_write_stream = WRITE_STREAM.read().unwrap().is_some();
            if !has_write_stream {
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

/// Get debug info for UI
pub fn get_debug_info() -> DebugInfo {
    DEBUG_INFO.read().unwrap().clone()
}

// ============= MOUSE TRACKING & EDGE DETECTION =============

/// Start mouse tracking - monitors mouse position and handles edge transitions
pub async fn start_mouse_tracking() {
    println!("🖱️ Starting mouse tracking...");
    
    let mut last_pos = (0i32, 0i32);
    let edge_threshold = 10;  // pixels from edge to trigger transition (increased for macOS)
    let mut debug_counter = 0u32;
    let mut loop_counter = 0u64;
    
    loop {
        tokio::time::sleep(tokio::time::Duration::from_millis(8)).await;  // ~125 Hz for lower latency
        
        loop_counter += 1;
        
        // Read all state upfront to avoid holding locks across await
        let is_connected = *IS_CONNECTED.read().unwrap();
        let being_controlled = *BEING_CONTROLLED.read().unwrap();
        let control_active = *CONTROL_ACTIVE.read().unwrap();
        
        let (mx, my) = crate::input::get_mouse_position();
        
        // Log every 5 seconds to verify loop is running
        if loop_counter % 300 == 0 {
            println!("🔄 Mouse tracking alive: pos=({},{}) connected={}", mx, my, is_connected);
        }
        
        // Update debug info every ~0.5 seconds (every 30 iterations at 60Hz)
        debug_counter += 1;
        if debug_counter >= 30 {
            debug_counter = 0;
            let screens = crate::input::get_all_screens();
            let total_min_x = screens.iter().map(|s| s.x).min().unwrap_or(0);
            let total_max_x = screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
            let total_min_y = screens.iter().map(|s| s.y).min().unwrap_or(0);
            let total_max_y = screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
            
            let edge_status = if !is_connected {
                "Not connected".to_string()
            } else if being_controlled {
                "Being controlled by remote".to_string()
            } else if control_active {
                "Controlling remote".to_string()
            } else {
                format!("Watching edges (R:{}, L:{}, T:{}, B:{})",
                    mx >= total_max_x - edge_threshold,
                    mx <= total_min_x + edge_threshold,
                    my <= total_min_y + edge_threshold,
                    my >= total_max_y - edge_threshold
                )
            };
            
            let remote_count = REMOTE_SCREENS.read().unwrap().len();
            
            let mut debug = DEBUG_INFO.write().unwrap();
            debug.mouse_x = mx;
            debug.mouse_y = my;
            debug.screen_bounds = format!("x:[{},{}] y:[{},{}]", total_min_x, total_max_x, total_min_y, total_max_y);
            debug.edge_status = edge_status;
            debug.remote_screen_count = remote_count;
            debug.last_update = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
        }
        
        // Skip if not connected
        if !is_connected {
            continue;
        }
        
        // Skip if we're being controlled (remote has our mouse)
        if being_controlled {
            continue;
        }
        
        // If we're controlling remote, capture mouse movement and send to remote
        if control_active {
            let edge_pos = *EDGE_LOCK_POS.read().unwrap();
            let (remote_x, remote_y) = *REMOTE_MOUSE_POS.read().unwrap();
            
            // Calculate delta from edge position (mouse always gets reset to edge)
            // So delta = current position - edge position
            let raw_delta_x = mx - edge_pos.0;
            let raw_delta_y = my - edge_pos.1;
            
            // Apply sensitivity multiplier for more responsive feel
            let sensitivity = 1.5;
            let delta_x = (raw_delta_x as f64 * sensitivity) as i32;
            let delta_y = (raw_delta_y as f64 * sensitivity) as i32;
            
            // Only send if there's actual movement
            if raw_delta_x != 0 || raw_delta_y != 0 {
                // Debug: show delta calculation
                println!("🎯 Delta: raw({},{}) -> scaled({},{}) | edge({},{}) mouse({},{})", 
                    raw_delta_x, raw_delta_y, delta_x, delta_y, edge_pos.0, edge_pos.1, mx, my);
                
                // Update remote mouse position with the delta
                let new_remote_x = remote_x + delta_x;
                let new_remote_y = remote_y + delta_y;
                
                // Get remote screen bounds
                let remote_screens = REMOTE_SCREENS.read().unwrap().clone();
                let remote_min_x = remote_screens.iter().map(|s| s.x).min().unwrap_or(0);
                let remote_max_x = remote_screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
                let remote_min_y = remote_screens.iter().map(|s| s.y).min().unwrap_or(0);
                let remote_max_y = remote_screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
                
                // Check if remote mouse would go past the "return" edge
                let now = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as u64;
                let start_time = *CONTROL_START_TIME.read().unwrap();
                let elapsed = now - start_time;
                
                // Get local screen info
                let screens = crate::input::get_all_screens();
                let total_min_x = screens.iter().map(|s| s.x).min().unwrap_or(0);
                let total_max_x = screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
                let total_min_y = screens.iter().map(|s| s.y).min().unwrap_or(0);
                let total_max_y = screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
                
                // Check for return to local (after cooldown)
                let should_return = if elapsed > 500 {
                    // At right edge of local (went to Windows on the right) and remote going left past edge
                    if edge_pos.0 >= total_max_x - 20 && new_remote_x < remote_min_x {
                        true
                    }
                    // At left edge of local (went to Windows on the left) and remote going right past edge
                    else if edge_pos.0 <= total_min_x + 20 && new_remote_x > remote_max_x {
                        true
                    }
                    else { false }
                } else { false };
                
                if should_return {
                    println!("🔙 Returning control to local");
                    *CONTROL_ACTIVE.write().unwrap() = false;
                    send_control_message("control_end", 0, 0).await;
                    
                    // Move local mouse back into the screen
                    let return_x = if edge_pos.0 >= total_max_x - 20 { total_max_x - 50 } else { total_min_x + 50 };
                    crate::input::move_mouse(return_x, edge_pos.1);
                } else {
                    // Clamp to remote screen bounds
                    let clamped_x = new_remote_x.clamp(remote_min_x, remote_max_x - 1);
                    let clamped_y = new_remote_y.clamp(remote_min_y, remote_max_y - 1);
                    
                    // Store new remote position
                    *REMOTE_MOUSE_POS.write().unwrap() = (clamped_x, clamped_y);
                    
                    // Send to remote
                    send_mouse_to_remote(clamped_x, clamped_y).await;
                }
                
                // Always move local mouse back to edge position (keeps it hidden at edge)
                crate::input::move_mouse(edge_pos.0, edge_pos.1);
            }
            
            // Update last_pos to edge position (since we keep resetting there)
            last_pos = (edge_pos.0, edge_pos.1);
        } else {
            // Not controlling - check for edge transition
            if mx != last_pos.0 || my != last_pos.1 {
                last_pos = (mx, my);
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
    
    // Calculate remote screen bounds
    let remote_min_x = remote_screens.iter().map(|s| s.x).min().unwrap_or(0);
    let remote_max_x = remote_screens.iter().map(|s| s.x + s.width).max().unwrap_or(1920);
    let remote_min_y = remote_screens.iter().map(|s| s.y).min().unwrap_or(0);
    let remote_max_y = remote_screens.iter().map(|s| s.y + s.height).max().unwrap_or(1080);
    
    // Get configured edge direction (which edge leads to Windows)
    let remote_edge = REMOTE_EDGE.read().unwrap().clone();
    
    // Check edges - but only the configured one
    let at_right_edge = mx >= total_max_x - threshold;
    let at_left_edge = mx <= total_min_x + threshold;
    let at_top_edge = my <= total_min_y + threshold;
    let at_bottom_edge = my >= total_max_y - threshold;
    
    // Only trigger on the correct edge based on layout
    let should_transition = match remote_edge.as_str() {
        "right" => at_right_edge,
        "left" => at_left_edge,
        "top" => at_top_edge,
        "bottom" => at_bottom_edge,
        _ => at_right_edge  // Default to right
    };
    
    if !should_transition {
        return;
    }
    
    println!("🎯 Edge detected ({})! Local bounds: x={}-{}, y={}-{}", remote_edge, total_min_x, total_max_x, total_min_y, total_max_y);
    println!("   Remote bounds: x={}-{}, y={}-{}", remote_min_x, remote_max_x, remote_min_y, remote_max_y);
    
    // Calculate relative position (0.0 to 1.0) on local screens
    let local_height = (total_max_y - total_min_y) as f64;
    let local_width = (total_max_x - total_min_x) as f64;
    let relative_y = if local_height > 0.0 { (my - total_min_y) as f64 / local_height } else { 0.5 };
    let relative_x = if local_width > 0.0 { (mx - total_min_x) as f64 / local_width } else { 0.5 };
    
    // Convert to remote coordinates based on which edge we're crossing
    let remote_height = (remote_max_y - remote_min_y) as f64;
    let remote_width = (remote_max_x - remote_min_x) as f64;
    
    let (remote_x, remote_y) = match remote_edge.as_str() {
        "right" => {
            // Enter remote from left side, map Y proportionally
            let mapped_y = remote_min_y + (relative_y * remote_height) as i32;
            (remote_min_x + 10, mapped_y.clamp(remote_min_y, remote_max_y - 1))
        },
        "left" => {
            // Enter remote from right side, map Y proportionally
            let mapped_y = remote_min_y + (relative_y * remote_height) as i32;
            (remote_max_x - 10, mapped_y.clamp(remote_min_y, remote_max_y - 1))
        },
        "top" => {
            // Enter remote from bottom, map X proportionally
            let mapped_x = remote_min_x + (relative_x * remote_width) as i32;
            (mapped_x.clamp(remote_min_x, remote_max_x - 1), remote_max_y - 10)
        },
        "bottom" => {
            // Enter remote from top, map X proportionally
            let mapped_x = remote_min_x + (relative_x * remote_width) as i32;
            (mapped_x.clamp(remote_min_x, remote_max_x - 1), remote_min_y + 10)
        },
        _ => {
            // Default: right edge
            let mapped_y = remote_min_y + (relative_y * remote_height) as i32;
            (remote_min_x + 10, mapped_y.clamp(remote_min_y, remote_max_y - 1))
        }
    };
    
    println!("   Mapping local ({}, {}) -> remote ({}, {})", mx, my, remote_x, remote_y);
    
    // Calculate edge lock position (where to keep local mouse pinned)
    let edge_x = match remote_edge.as_str() {
        "right" => total_max_x - 1,
        "left" => total_min_x + 1,
        _ => mx
    };
    let edge_y = match remote_edge.as_str() {
        "top" => total_min_y + 1,
        "bottom" => total_max_y - 1,
        _ => my
    };
    
    // Store edge lock position and initial remote mouse position
    *EDGE_LOCK_POS.write().unwrap() = (edge_x, edge_y);
    *REMOTE_MOUSE_POS.write().unwrap() = (remote_x, remote_y);
    
    // Record start time for cooldown
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    *CONTROL_START_TIME.write().unwrap() = now;
    
    println!("   Edge lock at ({}, {}), remote starts at ({}, {})", edge_x, edge_y, remote_x, remote_y);
    
    // Take control of remote
    *CONTROL_ACTIVE.write().unwrap() = true;
    
    // Send control_start message
    send_control_message("control_start", remote_x, remote_y).await;
    
    // Move local mouse to edge position
    crate::input::move_mouse(edge_x, edge_y);
}

async fn send_mouse_to_remote(x: i32, y: i32) {
    // Clone the client outside of async context to avoid Send issues
    let client = {
        ACTIVE_CLIENT.read().unwrap().clone()
    };
    
    let writer = { WRITE_STREAM.read().unwrap().clone() };
    
    if let Some(writer) = writer {
        let msg = Message::mouse_move(x, y);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = writer.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

async fn send_control_message(msg_type: &str, x: i32, y: i32) {
    println!("📤 Sending {} message at ({}, {})", msg_type, x, y);
    
    // Use the dedicated write stream (doesn't conflict with read loop)
    let writer = { WRITE_STREAM.read().unwrap().clone() };
    
    if let Some(writer) = writer {
        let msg = Message {
            msg_type: msg_type.to_string(),
            x: Some(x),
            y: Some(y),
            button: None, action: None, key_code: None,
            text: None, name: None, version: None,
            screens: None, computer_type: None, layout: None,
        };
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        println!("📤 Sending JSON: {}", json.trim());
        let mut stream = writer.lock().await;
        println!("📤 Got write lock, sending...");
        match stream.write_all(json.as_bytes()).await {
            Ok(_) => {
                println!("✅ Message sent successfully");
                // Flush to ensure it's sent immediately
                let _ = stream.flush().await;
            }
            Err(e) => println!("❌ Failed to send message: {}", e),
        }
    } else {
        println!("❌ No write stream available!");
    }
}

/// Send keyboard event to remote
pub async fn send_key_to_remote(key_code: u32, action: &str) {
    let is_active = *CONTROL_ACTIVE.read().unwrap();
    if !is_active { return; }
    
    let writer = { WRITE_STREAM.read().unwrap().clone() };
    
    if let Some(writer) = writer {
        let msg = Message::key_event(key_code, action);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = writer.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

/// Send mouse click to remote
pub async fn send_click_to_remote(button: &str, action: &str) {
    let is_active = *CONTROL_ACTIVE.read().unwrap();
    if !is_active { return; }
    
    let writer = { WRITE_STREAM.read().unwrap().clone() };
    
    if let Some(writer) = writer {
        let msg = Message::mouse_click(button, action);
        let json = serde_json::to_string(&msg).unwrap_or_default() + "\n";
        let mut stream = writer.lock().await;
        let _ = stream.write_all(json.as_bytes()).await;
    }
}

/// Release control back to local
pub fn release_control() {
    *CONTROL_ACTIVE.write().unwrap() = false;
    println!("🔓 Control released back to local");
}

/// Send layout sync to remote
pub async fn send_layout_sync(layout_json: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    println!("📐 Sending layout sync: {}", layout_json);
    
    let writer = { WRITE_STREAM.read().unwrap().clone() };
    
    if let Some(writer) = writer {
        let msg = Message::layout_sync(layout_json);
        let json = serde_json::to_string(&msg)? + "\n";
        let mut stream = writer.lock().await;
        stream.write_all(json.as_bytes()).await?;
        stream.flush().await?;
        println!("✅ Layout sync sent successfully");
        Ok(())
    } else {
        Err("No write stream available".into())
    }
}

