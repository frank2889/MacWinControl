using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using MacWinControlClient.Models;

namespace MacWinControlClient.Network
{
    public class NetworkClient
    {
        private TcpClient? _client;
        private NetworkStream? _stream;
        private CancellationTokenSource? _cts;
        private readonly string _computerName;

        public event Action<string>? OnConnected;
        public event Action? OnDisconnected;
        public event Action<InputEvent>? OnInputEvent;
        public event Action<string>? OnError;
        public event Action<string>? OnLog;

        public bool IsConnected => _client?.Connected ?? false;

        public NetworkClient()
        {
            _computerName = Environment.MachineName;
        }

        public async Task ConnectAsync(string host, int port = 52525)
        {
            try
            {
                Log($"Connecting to {host}:{port}...");

                _client = new TcpClient();
                await _client.ConnectAsync(host, port);

                _stream = _client.GetStream();
                _cts = new CancellationTokenSource();

                Log("Connected! Waiting for hello...");

                // Start receiving
                _ = Task.Run(() => ReceiveLoop(_cts.Token));
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Connection failed: {ex.Message}");
                Disconnect();
            }
        }

        public void Disconnect()
        {
            _cts?.Cancel();
            _stream?.Close();
            _client?.Close();
            _client = null;
            _stream = null;
            OnDisconnected?.Invoke();
        }

        private async Task ReceiveLoop(CancellationToken ct)
        {
            var buffer = new byte[65536];
            var messageBuffer = new StringBuilder();

            try
            {
                while (!ct.IsCancellationRequested && _stream != null)
                {
                    int bytesRead = await _stream.ReadAsync(buffer, 0, buffer.Length, ct);

                    if (bytesRead == 0)
                    {
                        Log("Server disconnected");
                        break;
                    }

                    string data = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    messageBuffer.Append(data);

                    // Process complete messages (newline separated)
                    string content = messageBuffer.ToString();
                    int newlineIndex;

                    while ((newlineIndex = content.IndexOf('\n')) >= 0)
                    {
                        string message = content.Substring(0, newlineIndex);
                        content = content.Substring(newlineIndex + 1);
                        messageBuffer.Clear();
                        messageBuffer.Append(content);

                        if (!string.IsNullOrWhiteSpace(message))
                        {
                            ProcessMessage(message);
                        }
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Normal cancellation
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Receive error: {ex.Message}");
            }

            Disconnect();
        }

        private void ProcessMessage(string message)
        {
            try
            {
                var inputEvent = JsonSerializer.Deserialize<InputEvent>(message);
                if (inputEvent == null) return;

                switch (inputEvent.Type)
                {
                    case "hello":
                        Log($"Received hello from Mac (v{inputEvent.Version})");
                        SendHello();
                        SendScreenInfo();
                        break;

                    case "connected":
                        Log("Connection established!");
                        OnConnected?.Invoke(inputEvent.Name ?? "Mac");
                        break;

                    case "ping":
                        SendPong();
                        break;

                    case "mouse_move":
                    case "mouse_button":
                    case "mouse_scroll":
                    case "key":
                    case "mode_switch":
                        OnInputEvent?.Invoke(inputEvent);
                        break;

                    default:
                        Log($"Unknown message type: {inputEvent.Type}");
                        break;
                }
            }
            catch (JsonException ex)
            {
                Log($"JSON parse error: {ex.Message}");
            }
        }

        private void SendHello()
        {
            // Get actual screen information
            var screens = GetAllScreens();
            Log($"Sending hello with {screens.Count} screen(s)");
            
            var hello = new HelloMessage
            {
                Version = "1.0",
                Name = _computerName,
                Screens = screens
            };
            Send(hello);
        }

        private List<ScreenRect> GetAllScreens()
        {
            var screens = new List<ScreenRect>();
            
            foreach (var screen in System.Windows.Forms.Screen.AllScreens)
            {
                screens.Add(new ScreenRect
                {
                    Width = screen.Bounds.Width,
                    Height = screen.Bounds.Height,
                    X = screen.Bounds.X,
                    Y = screen.Bounds.Y
                });
                Log($"  Screen: {screen.Bounds.Width}x{screen.Bounds.Height} at ({screen.Bounds.X}, {screen.Bounds.Y})");
            }
            
            return screens;
        }

        private void SendScreenInfo()
        {
            var screenInfo = new ScreenInfo
            {
                Screens = GetAllScreens()
            };
            Send(screenInfo);
        }

        private void SendPong()
        {
            Send(new { type = "pong" });
        }

        private void Send<T>(T obj)
        {
            if (_stream == null || !IsConnected) return;

            try
            {
                string json = JsonSerializer.Serialize(obj);
                byte[] data = Encoding.UTF8.GetBytes(json + "\n");
                _stream.Write(data, 0, data.Length);
            }
            catch (Exception ex)
            {
                OnError?.Invoke($"Send error: {ex.Message}");
            }
        }

        private void Log(string message)
        {
            OnLog?.Invoke($"[{DateTime.Now:HH:mm:ss}] {message}");
        }
    }
}
