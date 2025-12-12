using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace MacWinControlClient
{
    /// <summary>
    /// Main bridge controller that coordinates all components
    /// for bidirectional Mac-Windows control
    /// </summary>
    public class BridgeController : IDisposable
    {
        #region Fields

        private TcpClient? _client;
        private NetworkStream? _stream;
        private StreamReader? _reader;
        private StreamWriter? _writer;
        private CancellationTokenSource? _cts;

        private readonly InputHookManager _inputHook;
        private readonly EdgeDetector _edgeDetector;
        private readonly ClipboardManager _clipboardManager;
        private readonly ClipboardHistory _clipboardHistory;

        private bool _isConnected = false;
        private bool _isControllingMac = false;
        private string _macIp = "";
        private int _port = 52525;

        // Settings
        public bool SwapCmdWin { get; set; } = true;
        public bool SwapAltOpt { get; set; } = false;
        public bool RelativeMouseMode { get; set; } = false;
        public bool ClipboardSync { get; set; } = true;
        public double MouseSensitivity { get; set; } = 1.0;
        public string ActiveEdge { get; set; } = "left";

        #endregion

        #region Events

        public event EventHandler<string>? StatusChanged;
        public event EventHandler<string>? LogMessage;
        public event EventHandler<bool>? ConnectionChanged;
        public event EventHandler<bool>? ModeChanged;

        #endregion

        #region Constructor

        public BridgeController()
        {
            _inputHook = new InputHookManager();
            _edgeDetector = new EdgeDetector();
            _clipboardManager = new ClipboardManager();
            _clipboardHistory = new ClipboardHistory();

            // Wire up events
            _inputHook.MouseMoved += OnMouseMoved;
            _inputHook.MouseClicked += OnMouseClicked;
            _inputHook.MouseScrolled += OnMouseScrolled;
            _inputHook.KeyPressed += OnKeyPressed;

            _edgeDetector.EdgeHit += OnEdgeHit;

            _clipboardManager.ClipboardChanged += OnClipboardChanged;
        }

        #endregion

        #region Connection

        public async Task<bool> ConnectAsync(string ip, int port)
        {
            if (_isConnected) return true;

            _macIp = ip;
            _port = port;

            try
            {
                Log($"Connecting to {ip}:{port}...");
                StatusChanged?.Invoke(this, "Connecting...");

                _client = new TcpClient();
                await _client.ConnectAsync(ip, port);

                _stream = _client.GetStream();
                _reader = new StreamReader(_stream, Encoding.UTF8);
                _writer = new StreamWriter(_stream, Encoding.UTF8) { AutoFlush = true };

                _cts = new CancellationTokenSource();
                _isConnected = true;

                // Send hello
                var hello = Protocol.CreateHello(Environment.MachineName, 
                    new List<string> { "mouse", "keyboard", "clipboard", "bidirectional" });
                await SendAsync(hello);

                // Send screen info
                var screenInfo = GetScreenInfoMessage();
                await SendAsync(screenInfo);

                // Start receive loop
                _ = Task.Run(() => ReceiveLoopAsync(_cts.Token));

                // Start input hook (but don't suppress yet)
                _inputHook.Start(suppressInput: false);

                // Start edge detection
                _edgeDetector.SetEdge(ActiveEdge);
                _edgeDetector.Start();

                // Start clipboard monitoring
                if (ClipboardSync)
                {
                    _clipboardManager.StartMonitoring();
                }

                Log($"Connected to Mac at {ip}:{port}");
                StatusChanged?.Invoke(this, "Connected");
                ConnectionChanged?.Invoke(this, true);

                return true;
            }
            catch (Exception ex)
            {
                Log($"Connection failed: {ex.Message}");
                StatusChanged?.Invoke(this, $"Error: {ex.Message}");
                Disconnect();
                return false;
            }
        }

        public void Disconnect()
        {
            _cts?.Cancel();

            _inputHook.Stop();
            _edgeDetector.Stop();
            _clipboardManager.StopMonitoring();

            _writer?.Dispose();
            _reader?.Dispose();
            _stream?.Dispose();
            _client?.Dispose();

            _isConnected = false;
            _isControllingMac = false;

            Log("Disconnected");
            StatusChanged?.Invoke(this, "Disconnected");
            ConnectionChanged?.Invoke(this, false);
            ModeChanged?.Invoke(this, false);
        }

        public bool IsConnected => _isConnected;
        public bool IsControllingMac => _isControllingMac;

        #endregion

        #region Messaging

        private async Task SendAsync(ProtocolMessage message)
        {
            if (_writer == null || !_isConnected) return;

            try
            {
                string json = Protocol.ToJson(message);
                await _writer.WriteLineAsync(json);
            }
            catch (Exception ex)
            {
                Log($"Send error: {ex.Message}");
            }
        }

        private async Task ReceiveLoopAsync(CancellationToken ct)
        {
            try
            {
                while (!ct.IsCancellationRequested && _reader != null)
                {
                    string? line = await _reader.ReadLineAsync();
                    if (line == null) break;

                    var message = Protocol.FromJson(line);
                    if (message != null)
                    {
                        HandleMessage(message);
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Receive error: {ex.Message}");
            }
            finally
            {
                Disconnect();
            }
        }

        private void HandleMessage(ProtocolMessage message)
        {
            switch (message.Type)
            {
                case "mode_switch":
                    HandleModeSwitch(message as ModeSwitchMessage);
                    break;

                case "mouse_move":
                    HandleMouseMove(message as MouseMoveMessage);
                    break;

                case "mouse_click":
                    HandleMouseClick(message as MouseClickMessage);
                    break;

                case "mouse_scroll":
                    HandleMouseScroll(message as MouseScrollMessage);
                    break;

                case "key_down":
                case "key_up":
                    HandleKeyEvent(message as KeyMessage);
                    break;

                case "clipboard_sync":
                    HandleClipboardSync(message as ClipboardMessage);
                    break;

                case "clipboard_request":
                    SendClipboardContent();
                    break;
            }
        }

        #endregion

        #region Mode Switching

        private void HandleModeSwitch(ModeSwitchMessage? msg)
        {
            if (msg == null) return;

            bool wasControllingMac = _isControllingMac;
            _isControllingMac = msg.ActiveDevice == "windows";

            if (_isControllingMac != wasControllingMac)
            {
                // Switch mode - suppress input when controlling Mac
                _inputHook.SetSuppressInput(_isControllingMac);

                Log(_isControllingMac ? "Now controlling Mac" : "Back to local Windows");
                StatusChanged?.Invoke(this, _isControllingMac ? "Controlling Mac" : "Local Mode");
                ModeChanged?.Invoke(this, _isControllingMac);
            }
        }

        private async void OnEdgeHit(object? sender, EdgeHitEventArgs e)
        {
            if (!_isConnected || _isControllingMac) return;

            Log($"Edge hit: {e.Edge} - requesting switch to Mac");

            // Request mode switch to Mac
            var msg = Protocol.CreateModeSwitch("mac", e.Edge.ToString().ToLower());
            await SendAsync(msg);
        }

        /// <summary>
        /// Request switch back to Windows (from Mac)
        /// </summary>
        public async Task RequestSwitchToWindows(string edge = "")
        {
            if (!_isConnected) return;

            var msg = Protocol.CreateModeSwitch("windows", edge);
            await SendAsync(msg);
        }

        #endregion

        #region Input Handling (Windows -> Mac)

        private async void OnMouseMoved(object? sender, MouseMoveEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            var msg = Protocol.CreateMouseMove(
                e.X * MouseSensitivity,
                e.Y * MouseSensitivity,
                e.DX * MouseSensitivity,
                e.DY * MouseSensitivity,
                RelativeMouseMode
            );
            await SendAsync(msg);
        }

        private async void OnMouseClicked(object? sender, MouseClickEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            var msg = new MouseClickMessage
            {
                Button = e.Button,
                Pressed = e.Pressed
            };
            await SendAsync(msg);
        }

        private async void OnMouseScrolled(object? sender, MouseScrollEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            var msg = new MouseScrollMessage
            {
                Dx = e.DX,
                Dy = e.DY
            };
            await SendAsync(msg);
        }

        private async void OnKeyPressed(object? sender, KeyEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            int keyCode = e.KeyCode;

            // Key swapping
            if (SwapCmdWin)
            {
                // Windows key (91/92) -> Cmd (55 on Mac)
                if (keyCode == 91 || keyCode == 92)
                {
                    keyCode = 55;
                }
            }

            if (SwapAltOpt)
            {
                // Alt (164/165) -> Option (58/61 on Mac)
                if (keyCode == 164 || keyCode == 165)
                {
                    keyCode = keyCode == 164 ? 58 : 61;
                }
            }

            var msg = new KeyMessage(e.IsDown)
            {
                KeyCode = keyCode,
                KeyName = e.KeyName,
                Modifiers = e.Modifiers
            };
            await SendAsync(msg);
        }

        #endregion

        #region Input Handling (Mac -> Windows)

        private void HandleMouseMove(MouseMoveMessage? msg)
        {
            if (msg == null || _isControllingMac) return;

            // Move cursor on Windows
            Cursor.Position = new Point((int)msg.X, (int)msg.Y);
        }

        private void HandleMouseClick(MouseClickMessage? msg)
        {
            if (msg == null || _isControllingMac) return;

            uint flags = msg.Button switch
            {
                "left" => msg.Pressed ? 0x0002u : 0x0004u,
                "right" => msg.Pressed ? 0x0008u : 0x0010u,
                "middle" => msg.Pressed ? 0x0020u : 0x0040u,
                _ => 0
            };

            if (flags != 0)
            {
                NativeMethods.mouse_event(flags, 0, 0, 0, 0);
            }
        }

        private void HandleMouseScroll(MouseScrollMessage? msg)
        {
            if (msg == null || _isControllingMac) return;

            if (msg.DY != 0)
            {
                NativeMethods.mouse_event(0x0800, 0, 0, (uint)(msg.DY * 120), 0);
            }
            if (msg.DX != 0)
            {
                NativeMethods.mouse_event(0x01000, 0, 0, (uint)(msg.DX * 120), 0);
            }
        }

        private void HandleKeyEvent(KeyMessage? msg)
        {
            if (msg == null || _isControllingMac) return;

            int keyCode = msg.KeyCode;

            // Reverse key swapping
            if (SwapCmdWin && keyCode == 55)
            {
                keyCode = 91; // Cmd -> Windows key
            }

            uint flags = msg.Type == "key_down" ? 0u : 0x0002u;
            NativeMethods.keybd_event((byte)keyCode, 0, flags, 0);
        }

        #endregion

        #region Clipboard

        private async void OnClipboardChanged(object? sender, ClipboardChangedEventArgs e)
        {
            if (!_isConnected || !ClipboardSync) return;

            _clipboardHistory.Add(e.Content, "local");

            var msg = Protocol.CreateClipboardSync(e.Content);
            await SendAsync(msg);

            Log("Clipboard synced to Mac");
        }

        private void HandleClipboardSync(ClipboardMessage? msg)
        {
            if (msg == null || !ClipboardSync) return;

            _clipboardHistory.Add(msg.Content, "mac");
            _clipboardManager.SetClipboard(msg.Content);

            Log("Clipboard received from Mac");
        }

        private async void SendClipboardContent()
        {
            if (!_isConnected) return;

            string content = _clipboardManager.GetClipboard();
            var msg = Protocol.CreateClipboardSync(content);
            await SendAsync(msg);
        }

        public ClipboardHistory GetClipboardHistory() => _clipboardHistory;

        #endregion

        #region Screen Info

        private ScreenInfoMessage GetScreenInfoMessage()
        {
            var layout = EdgeDetector.GetScreenLayout();
            var screens = new List<ScreenInfo>();

            foreach (var s in layout.Screens)
            {
                screens.Add(new ScreenInfo
                {
                    Name = s.Name,
                    X = s.X,
                    Y = s.Y,
                    Width = s.Width,
                    Height = s.Height,
                    IsPrimary = s.IsPrimary
                });
            }

            return Protocol.CreateScreenInfo(screens, layout.PrimaryIndex);
        }

        #endregion

        #region Helpers

        private void Log(string message)
        {
            Console.WriteLine($"[Bridge] {message}");
            LogMessage?.Invoke(this, message);
        }

        public void Dispose()
        {
            Disconnect();
            _inputHook.Dispose();
            _edgeDetector.Dispose();
            _clipboardManager.Dispose();
        }

        #endregion
    }
}
