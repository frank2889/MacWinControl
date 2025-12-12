using System;
using System.Drawing;
using System.Windows.Forms;
using System.Timers;

namespace MacWinControlClient
{
    /// <summary>
    /// Edge detection for switching from Windows to Mac
    /// Monitors when mouse hits screen edges
    /// </summary>
    public class EdgeDetector : IDisposable
    {
        public enum Edge { Left, Right, Top, Bottom }

        public event EventHandler<EdgeHitEventArgs>? EdgeHit;

        private readonly System.Timers.Timer _pollTimer;
        private Edge _activeEdge = Edge.Left;
        private int _edgeThreshold = 0;
        private bool _enabled = false;
        private Point _lastPosition;
        private int _edgeHitCount = 0;
        private const int REQUIRED_HITS = 3; // Debounce - require multiple hits

        public EdgeDetector()
        {
            _pollTimer = new System.Timers.Timer(16); // ~60fps
            _pollTimer.Elapsed += OnPollTick;
        }

        public void Start()
        {
            if (_enabled) return;
            _enabled = true;
            _lastPosition = Cursor.Position;
            _pollTimer.Start();
            Console.WriteLine($"[EdgeDetector] Started - watching {_activeEdge} edge");
        }

        public void Stop()
        {
            _pollTimer.Stop();
            _enabled = false;
            Console.WriteLine("[EdgeDetector] Stopped");
        }

        public void SetEdge(Edge edge)
        {
            _activeEdge = edge;
            Console.WriteLine($"[EdgeDetector] Now watching {edge} edge");
        }

        public void SetEdge(string edge)
        {
            _activeEdge = edge.ToLower() switch
            {
                "left" => Edge.Left,
                "right" => Edge.Right,
                "top" => Edge.Top,
                "bottom" => Edge.Bottom,
                _ => Edge.Left
            };
        }

        private void OnPollTick(object? sender, ElapsedEventArgs e)
        {
            if (!_enabled) return;

            try
            {
                var pos = Cursor.Position;
                var bounds = GetVirtualScreenBounds();

                bool atEdge = _activeEdge switch
                {
                    Edge.Left => pos.X <= bounds.Left + _edgeThreshold,
                    Edge.Right => pos.X >= bounds.Right - _edgeThreshold - 1,
                    Edge.Top => pos.Y <= bounds.Top + _edgeThreshold,
                    Edge.Bottom => pos.Y >= bounds.Bottom - _edgeThreshold - 1,
                    _ => false
                };

                // Check if mouse is moving towards edge
                bool movingTowardsEdge = _activeEdge switch
                {
                    Edge.Left => pos.X < _lastPosition.X,
                    Edge.Right => pos.X > _lastPosition.X,
                    Edge.Top => pos.Y < _lastPosition.Y,
                    Edge.Bottom => pos.Y > _lastPosition.Y,
                    _ => false
                };

                if (atEdge && movingTowardsEdge)
                {
                    _edgeHitCount++;
                    if (_edgeHitCount >= REQUIRED_HITS)
                    {
                        _edgeHitCount = 0;
                        EdgeHit?.Invoke(this, new EdgeHitEventArgs
                        {
                            Edge = _activeEdge,
                            Position = pos,
                            ScreenBounds = bounds
                        });
                    }
                }
                else
                {
                    _edgeHitCount = 0;
                }

                _lastPosition = pos;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[EdgeDetector] Error: {ex.Message}");
            }
        }

        private Rectangle GetVirtualScreenBounds()
        {
            int left = SystemInformation.VirtualScreen.Left;
            int top = SystemInformation.VirtualScreen.Top;
            int right = SystemInformation.VirtualScreen.Right;
            int bottom = SystemInformation.VirtualScreen.Bottom;

            return new Rectangle(left, top, right - left, bottom - top);
        }

        public static ScreenLayout GetScreenLayout()
        {
            var layout = new ScreenLayout();

            foreach (var screen in Screen.AllScreens)
            {
                layout.Screens.Add(new ScreenRect
                {
                    Name = screen.DeviceName,
                    X = screen.Bounds.X,
                    Y = screen.Bounds.Y,
                    Width = screen.Bounds.Width,
                    Height = screen.Bounds.Height,
                    IsPrimary = screen.Primary
                });

                if (screen.Primary)
                {
                    layout.PrimaryIndex = layout.Screens.Count - 1;
                }
            }

            layout.TotalBounds = GetVirtualScreenBoundsStatic();
            return layout;
        }

        private static Rectangle GetVirtualScreenBoundsStatic()
        {
            return SystemInformation.VirtualScreen;
        }

        public void Dispose()
        {
            Stop();
            _pollTimer.Dispose();
        }
    }

    #region Data Classes

    public class EdgeHitEventArgs : EventArgs
    {
        public EdgeDetector.Edge Edge { get; set; }
        public Point Position { get; set; }
        public Rectangle ScreenBounds { get; set; }
    }

    public class ScreenRect
    {
        public string Name { get; set; } = "";
        public int X { get; set; }
        public int Y { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public bool IsPrimary { get; set; }
    }

    public class ScreenLayout
    {
        public List<ScreenRect> Screens { get; set; } = new();
        public int PrimaryIndex { get; set; }
        public Rectangle TotalBounds { get; set; }
    }

    #endregion
}
