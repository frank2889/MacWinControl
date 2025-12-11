using System.Text.Json.Serialization;

namespace MacWinControlClient.Models
{
    public class InputEvent
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "";

        [JsonPropertyName("x")]
        public int? X { get; set; }

        [JsonPropertyName("y")]
        public int? Y { get; set; }

        [JsonPropertyName("button")]
        public string? Button { get; set; }

        [JsonPropertyName("action")]
        public string? Action { get; set; }

        [JsonPropertyName("deltaX")]
        public int? DeltaX { get; set; }

        [JsonPropertyName("deltaY")]
        public int? DeltaY { get; set; }

        [JsonPropertyName("keyCode")]
        public int? KeyCode { get; set; }

        [JsonPropertyName("modifiers")]
        public KeyModifiers? Modifiers { get; set; }

        [JsonPropertyName("active")]
        public bool? Active { get; set; }

        [JsonPropertyName("timestamp")]
        public long? Timestamp { get; set; }

        [JsonPropertyName("version")]
        public string? Version { get; set; }

        [JsonPropertyName("name")]
        public string? Name { get; set; }

        [JsonPropertyName("message")]
        public string? Message { get; set; }
    }

    public class KeyModifiers
    {
        [JsonPropertyName("shift")]
        public bool Shift { get; set; }

        [JsonPropertyName("control")]
        public bool Control { get; set; }

        [JsonPropertyName("alt")]
        public bool Alt { get; set; }

        [JsonPropertyName("meta")]
        public bool Meta { get; set; }
    }

    public class HelloMessage
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "hello";

        [JsonPropertyName("version")]
        public string Version { get; set; } = "1.0";

        [JsonPropertyName("name")]
        public string Name { get; set; } = "";

        [JsonPropertyName("screens")]
        public List<ScreenRect> Screens { get; set; } = new();
    }

    public class ScreenInfo
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "screen_info";

        [JsonPropertyName("screens")]
        public List<ScreenRect> Screens { get; set; } = new();
    }

    public class ScreenRect
    {
        [JsonPropertyName("width")]
        public int Width { get; set; }

        [JsonPropertyName("height")]
        public int Height { get; set; }

        [JsonPropertyName("x")]
        public int X { get; set; }

        [JsonPropertyName("y")]
        public int Y { get; set; }
    }

    public class PingMessage
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "ping";
    }
}
