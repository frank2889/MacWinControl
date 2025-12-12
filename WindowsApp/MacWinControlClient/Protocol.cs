using System;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MacWinControlClient
{
    /// <summary>
    /// Message types matching Python protocol.py
    /// </summary>
    public enum MessageType
    {
        Hello,
        ModeSwitch,
        MouseMove,
        MouseClick,
        MouseScroll,
        KeyDown,
        KeyUp,
        ClipboardSync,
        ClipboardRequest,
        ScreenInfo,
        Heartbeat,
        Error
    }

    /// <summary>
    /// Base message class for all protocol messages
    /// </summary>
    public class ProtocolMessage
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "";
        
        [JsonPropertyName("timestamp")]
        public double Timestamp { get; set; }
        
        [JsonPropertyName("source")]
        public string Source { get; set; } = "windows";
        
        [JsonExtensionData]
        public Dictionary<string, JsonElement>? ExtensionData { get; set; }
    }

    /// <summary>
    /// Hello message for handshake
    /// </summary>
    public class HelloMessage : ProtocolMessage
    {
        [JsonPropertyName("client_name")]
        public string ClientName { get; set; } = "";
        
        [JsonPropertyName("version")]
        public string Version { get; set; } = "2.0.0";
        
        [JsonPropertyName("capabilities")]
        public List<string> Capabilities { get; set; } = new();
        
        public HelloMessage()
        {
            Type = "hello";
        }
    }

    /// <summary>
    /// Mode switch message
    /// </summary>
    public class ModeSwitchMessage : ProtocolMessage
    {
        [JsonPropertyName("active_device")]
        public string ActiveDevice { get; set; } = "";
        
        [JsonPropertyName("edge")]
        public string Edge { get; set; } = "";
        
        public ModeSwitchMessage()
        {
            Type = "mode_switch";
        }
    }

    /// <summary>
    /// Mouse move message
    /// </summary>
    public class MouseMoveMessage : ProtocolMessage
    {
        [JsonPropertyName("x")]
        public double X { get; set; }
        
        [JsonPropertyName("y")]
        public double Y { get; set; }
        
        [JsonPropertyName("dx")]
        public double Dx { get; set; }
        
        [JsonPropertyName("dy")]
        public double Dy { get; set; }
        
        [JsonPropertyName("relative")]
        public bool Relative { get; set; }
        
        public MouseMoveMessage()
        {
            Type = "mouse_move";
        }
    }

    /// <summary>
    /// Mouse click message
    /// </summary>
    public class MouseClickMessage : ProtocolMessage
    {
        [JsonPropertyName("button")]
        public string Button { get; set; } = "left";
        
        [JsonPropertyName("pressed")]
        public bool Pressed { get; set; }
        
        public MouseClickMessage()
        {
            Type = "mouse_click";
        }
    }

    /// <summary>
    /// Mouse scroll message
    /// </summary>
    public class MouseScrollMessage : ProtocolMessage
    {
        [JsonPropertyName("dx")]
        public double Dx { get; set; }
        
        [JsonPropertyName("dy")]
        public double Dy { get; set; }
        
        public MouseScrollMessage()
        {
            Type = "mouse_scroll";
        }
    }

    /// <summary>
    /// Key event message
    /// </summary>
    public class KeyMessage : ProtocolMessage
    {
        [JsonPropertyName("key_code")]
        public int KeyCode { get; set; }
        
        [JsonPropertyName("key_name")]
        public string KeyName { get; set; } = "";
        
        [JsonPropertyName("modifiers")]
        public List<string> Modifiers { get; set; } = new();
        
        public KeyMessage(bool isDown = true)
        {
            Type = isDown ? "key_down" : "key_up";
        }
    }

    /// <summary>
    /// Clipboard sync message
    /// </summary>
    public class ClipboardMessage : ProtocolMessage
    {
        [JsonPropertyName("content_type")]
        public string ContentType { get; set; } = "text";
        
        [JsonPropertyName("content")]
        public string Content { get; set; } = "";
        
        public ClipboardMessage()
        {
            Type = "clipboard_sync";
        }
    }

    /// <summary>
    /// Screen information message
    /// </summary>
    public class ScreenInfoMessage : ProtocolMessage
    {
        [JsonPropertyName("screens")]
        public List<ScreenInfo> Screens { get; set; } = new();
        
        [JsonPropertyName("primary_index")]
        public int PrimaryIndex { get; set; }
        
        public ScreenInfoMessage()
        {
            Type = "screen_info";
        }
    }

    /// <summary>
    /// Screen information structure
    /// </summary>
    public class ScreenInfo
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = "";
        
        [JsonPropertyName("x")]
        public int X { get; set; }
        
        [JsonPropertyName("y")]
        public int Y { get; set; }
        
        [JsonPropertyName("width")]
        public int Width { get; set; }
        
        [JsonPropertyName("height")]
        public int Height { get; set; }
        
        [JsonPropertyName("is_primary")]
        public bool IsPrimary { get; set; }
    }

    /// <summary>
    /// Protocol helper class for message serialization
    /// </summary>
    public static class Protocol
    {
        public const string VERSION = "2.0.0";
        
        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            WriteIndented = false
        };

        public static string ToJson(ProtocolMessage message)
        {
            message.Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
            return JsonSerializer.Serialize(message, message.GetType(), JsonOptions);
        }

        public static ProtocolMessage? FromJson(string json)
        {
            try
            {
                // First parse to get the type
                var doc = JsonDocument.Parse(json);
                var type = doc.RootElement.GetProperty("type").GetString();

                return type switch
                {
                    "hello" => JsonSerializer.Deserialize<HelloMessage>(json, JsonOptions),
                    "mode_switch" => JsonSerializer.Deserialize<ModeSwitchMessage>(json, JsonOptions),
                    "mouse_move" => JsonSerializer.Deserialize<MouseMoveMessage>(json, JsonOptions),
                    "mouse_click" => JsonSerializer.Deserialize<MouseClickMessage>(json, JsonOptions),
                    "mouse_scroll" => JsonSerializer.Deserialize<MouseScrollMessage>(json, JsonOptions),
                    "key_down" or "key_up" => JsonSerializer.Deserialize<KeyMessage>(json, JsonOptions),
                    "clipboard_sync" => JsonSerializer.Deserialize<ClipboardMessage>(json, JsonOptions),
                    "screen_info" => JsonSerializer.Deserialize<ScreenInfoMessage>(json, JsonOptions),
                    _ => JsonSerializer.Deserialize<ProtocolMessage>(json, JsonOptions)
                };
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[Protocol] Parse error: {ex.Message}");
                return null;
            }
        }

        public static HelloMessage CreateHello(string clientName, List<string>? capabilities = null)
        {
            return new HelloMessage
            {
                ClientName = clientName,
                Version = VERSION,
                Capabilities = capabilities ?? new List<string> { "mouse", "keyboard", "clipboard" }
            };
        }

        public static ModeSwitchMessage CreateModeSwitch(string activeDevice, string edge = "")
        {
            return new ModeSwitchMessage
            {
                ActiveDevice = activeDevice,
                Edge = edge
            };
        }

        public static MouseMoveMessage CreateMouseMove(double x, double y, double dx = 0, double dy = 0, bool relative = false)
        {
            return new MouseMoveMessage
            {
                X = x,
                Y = y,
                Dx = dx,
                Dy = dy,
                Relative = relative
            };
        }

        public static ClipboardMessage CreateClipboardSync(string content, string contentType = "text")
        {
            return new ClipboardMessage
            {
                Content = content,
                ContentType = contentType
            };
        }

        public static ScreenInfoMessage CreateScreenInfo(List<ScreenInfo> screens, int primaryIndex = 0)
        {
            return new ScreenInfoMessage
            {
                Screens = screens,
                PrimaryIndex = primaryIndex
            };
        }
    }
}
