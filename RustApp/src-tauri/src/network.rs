// Network module - TCP server and client for input sharing

use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;

const PORT: u16 = 52525;

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
}

impl Message {
    pub fn hello(name: &str) -> Self {
        Message {
            msg_type: "hello".to_string(),
            name: Some(name.to_string()),
            version: Some("1.0".to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None,
        }
    }
    
    pub fn mouse_move(x: i32, y: i32) -> Self {
        Message {
            msg_type: "mouse_move".to_string(),
            x: Some(x),
            y: Some(y),
            button: None, action: None, key_code: None, 
            text: None, name: None, version: None,
        }
    }
    
    pub fn mouse_click(button: &str, action: &str) -> Self {
        Message {
            msg_type: "mouse_click".to_string(),
            button: Some(button.to_string()),
            action: Some(action.to_string()),
            x: None, y: None, key_code: None, 
            text: None, name: None, version: None,
        }
    }
    
    pub fn key_event(key_code: u32, action: &str) -> Self {
        Message {
            msg_type: "key_event".to_string(),
            key_code: Some(key_code),
            action: Some(action.to_string()),
            x: None, y: None, button: None, 
            text: None, name: None, version: None,
        }
    }
    
    pub fn clipboard(text: &str) -> Self {
        Message {
            msg_type: "clipboard".to_string(),
            text: Some(text.to_string()),
            x: None, y: None, button: None, action: None, 
            key_code: None, name: None, version: None,
        }
    }
    
    pub fn ping() -> Self {
        Message {
            msg_type: "ping".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
        }
    }
    
    pub fn pong() -> Self {
        Message {
            msg_type: "pong".to_string(),
            x: None, y: None, button: None, action: None, 
            key_code: None, text: None, name: None, version: None,
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
    
    // Send hello message
    {
        let computer_name = get_computer_name();
        let hello = Message::hello(&computer_name);
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
            println!("Client hello: {:?}", msg.name);
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
    
    // Send hello
    {
        let computer_name = get_computer_name();
        let hello = Message::hello(&computer_name);
        let json = serde_json::to_string(&hello)? + "\n";
        
        let mut stream = client.lock().await;
        stream.write_all(json.as_bytes()).await?;
    }
    
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
