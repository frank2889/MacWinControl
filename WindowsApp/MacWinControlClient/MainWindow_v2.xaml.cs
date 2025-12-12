using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Forms;

namespace MacWinControlClient
{
    /// <summary>
    /// Modern MacWinControl Windows Client v2.0
    /// Matching design with Mac app
    /// </summary>
    public partial class MainWindowV2 : Window
    {
        private TcpClient? _client;
        private NetworkStream? _stream;
        private StreamReader? _reader;
        private StreamWriter? _writer;
        private CancellationTokenSource? _cts;
        private bool _isConnected = false;
        private bool _isControllingMac = false;

        // Low-level input hook
        private InputHook? _inputHook;

        public MainWindowV2()
        {
            InitializeComponent();
            LoadSettings();
            RefreshScreensInternal();
            UpdateClipboardDisplay();
        }

        #region Navigation

        private void NavConnection_Click(object sender, RoutedEventArgs e)
        {
            ShowTab("connection");
        }

        private void NavSettings_Click(object sender, RoutedEventArgs e)
        {
            ShowTab("settings");
        }

        private void NavClipboard_Click(object sender, RoutedEventArgs e)
        {
            ShowTab("clipboard");
        }

        private void NavScreens_Click(object sender, RoutedEventArgs e)
        {
            ShowTab("screens");
        }

        private void ShowTab(string tabName)
        {
            ConnectionTab.Visibility = tabName == "connection" ? Visibility.Visible : Visibility.Collapsed;
            SettingsTab.Visibility = tabName == "settings" ? Visibility.Visible : Visibility.Collapsed;
            ClipboardTab.Visibility = tabName == "clipboard" ? Visibility.Visible : Visibility.Collapsed;
            ScreensTab.Visibility = tabName == "screens" ? Visibility.Visible : Visibility.Collapsed;
        }

        #endregion

        #region Connection

        private async void ConnectButton_Click(object sender, RoutedEventArgs e)
        {
            string ip = IpAddressInput.Text.Trim();
            if (!int.TryParse(PortInput.Text.Trim(), out int port))
            {
                port = 52525;
            }

            await ConnectAsync(ip, port);
        }

        private void DisconnectButton_Click(object sender, RoutedEventArgs e)
        {
            Disconnect();
        }

        private async Task ConnectAsync(string ip, int port)
        {
            try
            {
                UpdateStatus("Connecting...", "warning", $"Connecting to {ip}:{port}...");
                ConnectButton.IsEnabled = false;

                _client = new TcpClient();
                await _client.ConnectAsync(ip, port);
                _stream = _client.GetStream();
                _reader = new StreamReader(_stream, Encoding.UTF8);
                _writer = new StreamWriter(_stream, Encoding.UTF8) { AutoFlush = true };

                // Send hello message
                var hello = Protocol.CreateHello(Environment.MachineName);
                await SendMessageAsync(hello);

                // Send screen info
                var screenInfo = GetScreenInfo();
                await SendMessageAsync(screenInfo);

                _isConnected = true;
                _cts = new CancellationTokenSource();

                // Start listening for messages
                _ = Task.Run(() => ReceiveLoop(_cts.Token));

                // Start input hook
                StartInputHook();

                UpdateStatus("Connected", "success", $"Connected to Mac at {ip}:{port}");
                ConnectButton.IsEnabled = false;
                DisconnectButton.IsEnabled = true;
            }
            catch (Exception ex)
            {
                UpdateStatus("Error", "error", $"Connection failed: {ex.Message}");
                ConnectButton.IsEnabled = true;
                DisconnectButton.IsEnabled = false;
            }
        }

        private void Disconnect()
        {
            _cts?.Cancel();
            StopInputHook();

            _writer?.Dispose();
            _reader?.Dispose();
            _stream?.Dispose();
            _client?.Dispose();

            _isConnected = false;
            _isControllingMac = false;

            UpdateStatus("Disconnected", "muted", "Not connected to Mac");
            ConnectButton.IsEnabled = true;
            DisconnectButton.IsEnabled = false;
        }

        private async Task SendMessageAsync(ProtocolMessage message)
        {
            if (_writer == null) return;
            try
            {
                string json = Protocol.ToJson(message);
                await _writer.WriteLineAsync(json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Send error: {ex.Message}");
            }
        }

        private async Task ReceiveLoop(CancellationToken ct)
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
                        await Dispatcher.InvokeAsync(() => HandleMessage(message));
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Receive error: {ex.Message}");
            }
            finally
            {
                await Dispatcher.InvokeAsync(Disconnect);
            }
        }

        private void HandleMessage(ProtocolMessage message)
        {
            switch (message.Type)
            {
                case "mode_switch":
                    if (message is ModeSwitchMessage modeMsg)
                    {
                        _isControllingMac = modeMsg.ActiveDevice == "windows";
                        UpdateStatus(
                            _isControllingMac ? "Controlling Mac" : "Local Mode",
                            _isControllingMac ? "primary" : "success",
                            _isControllingMac ? "Mouse and keyboard controlling Mac" : "Local Windows control active"
                        );
                    }
                    break;

                case "mouse_move":
                    if (message is MouseMoveMessage mouseMsg)
                    {
                        // Move cursor on Windows
                        System.Windows.Forms.Cursor.Position = new System.Drawing.Point((int)mouseMsg.X, (int)mouseMsg.Y);
                    }
                    break;

                case "mouse_click":
                    if (message is MouseClickMessage clickMsg)
                    {
                        SimulateClick(clickMsg.Button, clickMsg.Pressed);
                    }
                    break;

                case "key_down":
                case "key_up":
                    if (message is KeyMessage keyMsg)
                    {
                        SimulateKey(keyMsg.KeyCode, keyMsg.Type == "key_down");
                    }
                    break;

                case "clipboard_sync":
                    if (message is ClipboardMessage clipMsg)
                    {
                        if (AutoSyncClipboard.IsChecked == true)
                        {
                            System.Windows.Clipboard.SetText(clipMsg.Content);
                            ClipboardContent.Text = clipMsg.Content.Length > 100 
                                ? clipMsg.Content.Substring(0, 100) + "..." 
                                : clipMsg.Content;
                        }
                    }
                    break;
            }
        }

        #endregion

        #region Input Hook

        private void StartInputHook()
        {
            _inputHook = new InputHook();
            _inputHook.MouseMoved += OnMouseMoved;
            _inputHook.MouseClicked += OnMouseClicked;
            _inputHook.KeyPressed += OnKeyPressed;
            _inputHook.Start();
        }

        private void StopInputHook()
        {
            _inputHook?.Stop();
            _inputHook = null;
        }

        private async void OnMouseMoved(object? sender, MouseMoveEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            var msg = Protocol.CreateMouseMove(e.X, e.Y, e.DX, e.DY, RelativeMouseCheck.IsChecked == true);
            await SendMessageAsync(msg);
        }

        private async void OnMouseClicked(object? sender, MouseClickEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            var msg = new MouseClickMessage
            {
                Button = e.Button,
                Pressed = e.Pressed
            };
            await SendMessageAsync(msg);
        }

        private async void OnKeyPressed(object? sender, KeyPressEventArgs e)
        {
            if (!_isConnected || !_isControllingMac) return;

            // Apply key swapping if enabled
            int keyCode = e.KeyCode;
            if (SwapCmdWinCheck.IsChecked == true)
            {
                // Swap Windows key ↔ Cmd (on Mac side)
                if (keyCode == 91 || keyCode == 92) // Left/Right Win
                {
                    keyCode = 55; // Mac Command key code
                }
            }

            var msg = new KeyMessage(e.IsDown)
            {
                KeyCode = keyCode,
                KeyName = e.KeyName,
                Modifiers = e.Modifiers
            };
            await SendMessageAsync(msg);
        }

        #endregion

        #region Clipboard

        private void CopyFromMac_Click(object sender, RoutedEventArgs e)
        {
            if (!_isConnected) return;

            var request = new ProtocolMessage { Type = "clipboard_request" };
            _ = SendMessageAsync(request);
        }

        private async void SendToMac_Click(object sender, RoutedEventArgs e)
        {
            if (!_isConnected) return;

            try
            {
                string content = System.Windows.Clipboard.GetText();
                var msg = Protocol.CreateClipboardSync(content);
                await SendMessageAsync(msg);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Clipboard error: {ex.Message}");
            }
        }

        private void UpdateClipboardDisplay()
        {
            try
            {
                if (System.Windows.Clipboard.ContainsText())
                {
                    string content = System.Windows.Clipboard.GetText();
                    ClipboardContent.Text = content.Length > 100 ? content.Substring(0, 100) + "..." : content;
                }
                else
                {
                    ClipboardContent.Text = "(empty)";
                }
            }
            catch
            {
                ClipboardContent.Text = "(unable to read)";
            }
        }

        #endregion

        #region Screens

        private void RefreshScreens_Click(object sender, RoutedEventArgs e)
        {
            RefreshScreensInternal();
        }

        private void RefreshScreensInternal()
        {
            ScreenCanvas.Children.Clear();
            var screens = Screen.AllScreens;

            // Find bounds
            int minX = int.MaxValue, maxX = int.MinValue;
            int minY = int.MaxValue, maxY = int.MinValue;
            foreach (var screen in screens)
            {
                minX = Math.Min(minX, screen.Bounds.X);
                maxX = Math.Max(maxX, screen.Bounds.X + screen.Bounds.Width);
                minY = Math.Min(minY, screen.Bounds.Y);
                maxY = Math.Max(maxY, screen.Bounds.Y + screen.Bounds.Height);
            }

            double totalWidth = maxX - minX;
            double totalHeight = maxY - minY;
            double scale = Math.Min(380.0 / totalWidth, 180.0 / totalHeight);

            StringBuilder info = new();
            int index = 0;

            foreach (var screen in screens)
            {
                double x = (screen.Bounds.X - minX) * scale + 10;
                double y = (screen.Bounds.Y - minY) * scale + 10;
                double w = screen.Bounds.Width * scale;
                double h = screen.Bounds.Height * scale;

                var rect = new Rectangle
                {
                    Width = w,
                    Height = h,
                    Fill = screen.Primary ? new SolidColorBrush(Color.FromRgb(99, 102, 241)) : new SolidColorBrush(Color.FromRgb(139, 92, 246)),
                    Stroke = new SolidColorBrush(Color.FromRgb(226, 232, 240)),
                    StrokeThickness = 2,
                    RadiusX = 4,
                    RadiusY = 4
                };

                Canvas.SetLeft(rect, x);
                Canvas.SetTop(rect, y);
                ScreenCanvas.Children.Add(rect);

                var label = new TextBlock
                {
                    Text = screen.Primary ? "🖥️ Primary" : $"🖥️ {index + 1}",
                    Foreground = Brushes.White,
                    FontSize = 11,
                    FontWeight = FontWeights.SemiBold
                };
                Canvas.SetLeft(label, x + 8);
                Canvas.SetTop(label, y + 8);
                ScreenCanvas.Children.Add(label);

                info.AppendLine($"• Screen {index + 1}: {screen.Bounds.Width}x{screen.Bounds.Height} at ({screen.Bounds.X}, {screen.Bounds.Y}){(screen.Primary ? " (Primary)" : "")}");
                index++;
            }

            ScreenInfoText.Text = info.ToString();
        }

        private ScreenInfoMessage GetScreenInfo()
        {
            var screens = new List<ScreenInfo>();
            int primaryIndex = 0;
            int index = 0;

            foreach (var screen in Screen.AllScreens)
            {
                screens.Add(new ScreenInfo
                {
                    Name = screen.DeviceName,
                    X = screen.Bounds.X,
                    Y = screen.Bounds.Y,
                    Width = screen.Bounds.Width,
                    Height = screen.Bounds.Height,
                    IsPrimary = screen.Primary
                });

                if (screen.Primary) primaryIndex = index;
                index++;
            }

            return Protocol.CreateScreenInfo(screens, primaryIndex);
        }

        #endregion

        #region UI Helpers

        private void UpdateStatus(string status, string type, string detail)
        {
            StatusText.Text = status;
            StatusDetail.Text = detail;

            Color color = type switch
            {
                "success" => Color.FromRgb(16, 185, 129),
                "warning" => Color.FromRgb(245, 158, 11),
                "error" => Color.FromRgb(239, 68, 68),
                "primary" => Color.FromRgb(99, 102, 241),
                _ => Color.FromRgb(100, 116, 139)
            };

            StatusDot.Fill = new SolidColorBrush(color);
        }

        private void LoadSettings()
        {
            // Load from app settings (simplified for now)
            SwapCmdWinCheck.IsChecked = true;
            SmoothScrollCheck.IsChecked = true;
            EdgeLeftRadio.IsChecked = true;
        }

        #endregion

        #region Input Simulation

        private void SimulateClick(string button, bool pressed)
        {
            // Use SendInput API (similar to existing implementation)
            uint flags = button switch
            {
                "left" => pressed ? 0x0002u : 0x0004u,  // MOUSEEVENTF_LEFTDOWN/UP
                "right" => pressed ? 0x0008u : 0x0010u, // MOUSEEVENTF_RIGHTDOWN/UP
                "middle" => pressed ? 0x0020u : 0x0040u, // MOUSEEVENTF_MIDDLEDOWN/UP
                _ => 0
            };

            if (flags != 0)
            {
                NativeMethods.mouse_event(flags, 0, 0, 0, 0);
            }
        }

        private void SimulateKey(int keyCode, bool pressed)
        {
            // Use SendInput API
            uint flags = pressed ? 0u : 0x0002u; // KEYEVENTF_KEYUP
            NativeMethods.keybd_event((byte)keyCode, 0, flags, 0);
        }

        #endregion

        protected override void OnClosed(EventArgs e)
        {
            Disconnect();
            base.OnClosed(e);
        }
    }

    #region Native Methods

    internal static class NativeMethods
    {
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, int dwExtraInfo);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    }

    #endregion

    #region Input Hook (Stub - needs full implementation)

    public class MouseMoveEventArgs : EventArgs
    {
        public double X { get; set; }
        public double Y { get; set; }
        public double DX { get; set; }
        public double DY { get; set; }
    }

    public class MouseClickEventArgs : EventArgs
    {
        public string Button { get; set; } = "left";
        public bool Pressed { get; set; }
    }

    public class KeyPressEventArgs : EventArgs
    {
        public int KeyCode { get; set; }
        public string KeyName { get; set; } = "";
        public bool IsDown { get; set; }
        public List<string> Modifiers { get; set; } = new();
    }

    public class InputHook
    {
        public event EventHandler<MouseMoveEventArgs>? MouseMoved;
        public event EventHandler<MouseClickEventArgs>? MouseClicked;
        public event EventHandler<KeyPressEventArgs>? KeyPressed;

        public void Start() { /* TODO: Implement low-level hooks */ }
        public void Stop() { /* TODO: Unhook */ }
    }

    #endregion
}
