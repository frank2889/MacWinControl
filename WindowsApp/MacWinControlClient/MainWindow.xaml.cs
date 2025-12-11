using System.Net;
using System.Net.Sockets;
using System.Windows;
using System.Windows.Media;
using MacWinControlClient.Input;
using MacWinControlClient.Models;
using MacWinControlClient.Network;

namespace MacWinControlClient
{
    public partial class MainWindow : Window
    {
        private readonly NetworkClient _networkClient;
        private readonly InputInjector _inputInjector;
        private bool _isReceivingInput = false;

        public MainWindow()
        {
            InitializeComponent();

            _networkClient = new NetworkClient();
            _inputInjector = new InputInjector();

            SetupEventHandlers();
            UpdateLocalInfo();
        }

        private void SetupEventHandlers()
        {
            _networkClient.OnConnected += (name) => Dispatcher.Invoke(() =>
            {
                StatusIndicator.Fill = new SolidColorBrush(Color.FromRgb(16, 124, 16)); // Green
                StatusText.Text = $"Verbonden met {name}";
                ConnectButton.Content = "Verbreek";
                Log($"✅ Verbonden met {name}");
            });

            _networkClient.OnDisconnected += () => Dispatcher.Invoke(() =>
            {
                StatusIndicator.Fill = new SolidColorBrush(Colors.Gray);
                StatusText.Text = "Niet verbonden";
                ConnectButton.Content = "Verbinden";
                ModeIndicator.Visibility = Visibility.Collapsed;
                _isReceivingInput = false;
                Log("⏹ Verbinding verbroken");
            });

            _networkClient.OnInputEvent += (inputEvent) => Dispatcher.Invoke(() =>
            {
                ProcessInputEvent(inputEvent);
            });

            _networkClient.OnError += (error) => Dispatcher.Invoke(() =>
            {
                Log($"❌ {error}");
            });

            _networkClient.OnLog += (message) => Dispatcher.Invoke(() =>
            {
                Log(message);
            });
        }

        private void UpdateLocalInfo()
        {
            ComputerNameText.Text = Environment.MachineName;
            LocalIPText.Text = GetLocalIP() ?? "Unknown";
        }

        private string? GetLocalIP()
        {
            try
            {
                using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, 0);
                socket.Connect("8.8.8.8", 65530);
                var endPoint = socket.LocalEndPoint as IPEndPoint;
                return endPoint?.Address.ToString();
            }
            catch
            {
                return null;
            }
        }

        private void ConnectButton_Click(object sender, RoutedEventArgs e)
        {
            if (_networkClient.IsConnected)
            {
                _networkClient.Disconnect();
            }
            else
            {
                string host = HostInput.Text.Trim();
                if (string.IsNullOrEmpty(host))
                {
                    Log("❌ Voer een IP adres in");
                    return;
                }

                StatusIndicator.Fill = new SolidColorBrush(Color.FromRgb(255, 140, 0)); // Orange
                StatusText.Text = "Verbinden...";
                
                _ = _networkClient.ConnectAsync(host);
            }
        }

        private void ProcessInputEvent(InputEvent evt)
        {
            try
            {
                switch (evt.Type)
                {
                    case "mode_switch":
                        _isReceivingInput = evt.Active ?? false;
                        ModeIndicator.Visibility = _isReceivingInput ? Visibility.Visible : Visibility.Collapsed;
                        Log(_isReceivingInput ? "🖱️ Mac controleert nu deze PC" : "⏸️ Mac controle gestopt");
                        break;

                    case "mouse_move":
                        if (_isReceivingInput && evt.X.HasValue && evt.Y.HasValue)
                        {
                            _inputInjector.MoveMouse(evt.X.Value, evt.Y.Value);
                        }
                        break;

                    case "mouse_button":
                        if (_isReceivingInput && evt.Button != null && evt.Action != null)
                        {
                            _inputInjector.MouseButton(evt.Button, evt.Action == "down");
                        }
                        break;

                    case "mouse_scroll":
                        if (_isReceivingInput)
                        {
                            _inputInjector.MouseScroll(evt.DeltaX ?? 0, evt.DeltaY ?? 0);
                        }
                        break;

                    case "key":
                        if (_isReceivingInput && evt.KeyCode.HasValue && evt.Action != null)
                        {
                            var mods = evt.Modifiers ?? new KeyModifiers();
                            _inputInjector.KeyPress(
                                evt.KeyCode.Value,
                                evt.Action == "down",
                                mods.Shift,
                                mods.Control,
                                mods.Alt
                            );
                        }
                        break;
                }
            }
            catch (Exception ex)
            {
                Log($"❌ Input error: {ex.Message}");
            }
        }

        private void Log(string message)
        {
            LogText.Text += message + "\n";
            LogScrollViewer.ScrollToEnd();
        }

        protected override void OnClosed(EventArgs e)
        {
            _networkClient.Disconnect();
            base.OnClosed(e);
        }
    }
}
