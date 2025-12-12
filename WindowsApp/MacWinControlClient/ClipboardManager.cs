using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;

namespace MacWinControlClient
{
    /// <summary>
    /// Manages clipboard synchronization between Mac and Windows
    /// </summary>
    public class ClipboardManager : IDisposable
    {
        private string _lastContent = "";
        private bool _monitoring = false;
        private CancellationTokenSource? _cts;
        private readonly int _pollIntervalMs = 500;

        public event EventHandler<ClipboardChangedEventArgs>? ClipboardChanged;

        /// <summary>
        /// Get current clipboard content
        /// </summary>
        public string GetClipboard()
        {
            try
            {
                if (Clipboard.ContainsText())
                {
                    return Clipboard.GetText();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[Clipboard] Error reading: {ex.Message}");
            }
            return "";
        }

        /// <summary>
        /// Set clipboard content
        /// </summary>
        public bool SetClipboard(string content)
        {
            try
            {
                Clipboard.SetText(content);
                _lastContent = content;
                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[Clipboard] Error writing: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Start monitoring clipboard for changes
        /// </summary>
        public void StartMonitoring()
        {
            if (_monitoring) return;

            _monitoring = true;
            _cts = new CancellationTokenSource();
            _lastContent = GetClipboard();

            Task.Run(() => MonitorLoop(_cts.Token));
            Console.WriteLine("[Clipboard] Monitoring started");
        }

        /// <summary>
        /// Stop monitoring clipboard
        /// </summary>
        public void StopMonitoring()
        {
            _monitoring = false;
            _cts?.Cancel();
            Console.WriteLine("[Clipboard] Monitoring stopped");
        }

        private async Task MonitorLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested && _monitoring)
            {
                try
                {
                    // Must access clipboard on STA thread
                    await Application.Current.Dispatcher.InvokeAsync(() =>
                    {
                        var current = GetClipboard();
                        if (!string.IsNullOrEmpty(current) && current != _lastContent)
                        {
                            _lastContent = current;
                            ClipboardChanged?.Invoke(this, new ClipboardChangedEventArgs
                            {
                                Content = current,
                                Source = "local"
                            });
                        }
                    });
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[Clipboard] Monitor error: {ex.Message}");
                }

                await Task.Delay(_pollIntervalMs, ct);
            }
        }

        public void Dispose()
        {
            StopMonitoring();
            _cts?.Dispose();
        }
    }

    /// <summary>
    /// Event args for clipboard changes
    /// </summary>
    public class ClipboardChangedEventArgs : EventArgs
    {
        public string Content { get; set; } = "";
        public string Source { get; set; } = "local";
    }

    /// <summary>
    /// Maintains a history of clipboard items
    /// </summary>
    public class ClipboardHistory
    {
        private readonly int _maxItems;
        private readonly List<ClipboardItem> _history = new();

        public ClipboardHistory(int maxItems = 50)
        {
            _maxItems = maxItems;
        }

        public void Add(string content, string source = "local")
        {
            var item = new ClipboardItem
            {
                Content = content,
                Source = source,
                Timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                Preview = content.Length > 100 ? content.Substring(0, 100) + "..." : content
            };

            // Remove duplicates
            _history.RemoveAll(h => h.Content == content);

            // Add to front
            _history.Insert(0, item);

            // Trim to max
            if (_history.Count > _maxItems)
            {
                _history.RemoveRange(_maxItems, _history.Count - _maxItems);
            }
        }

        public List<ClipboardItem> GetHistory() => new(_history);

        public void Clear() => _history.Clear();

        public string? GetItem(int index)
        {
            if (index >= 0 && index < _history.Count)
            {
                return _history[index].Content;
            }
            return null;
        }
    }

    /// <summary>
    /// A single clipboard history item
    /// </summary>
    public class ClipboardItem
    {
        public string Content { get; set; } = "";
        public string Source { get; set; } = "";
        public long Timestamp { get; set; }
        public string Preview { get; set; } = "";
    }
}
