using System.Runtime.InteropServices;
using static MacWinControlClient.Input.NativeInput;

namespace MacWinControlClient.Input
{
    /// <summary>
    /// High-level wrapper for simulating mouse and keyboard input
    /// </summary>
    public class InputInjector
    {
        private int _screenWidth;
        private int _screenHeight;
        private int _virtualLeft;
        private int _virtualTop;
        private int _virtualWidth;
        private int _virtualHeight;

        public InputInjector()
        {
            UpdateScreenMetrics();
        }

        public void UpdateScreenMetrics()
        {
            _screenWidth = GetSystemMetrics(SM_CXSCREEN);
            _screenHeight = GetSystemMetrics(SM_CYSCREEN);
            _virtualLeft = GetSystemMetrics(SM_XVIRTUALSCREEN);
            _virtualTop = GetSystemMetrics(SM_YVIRTUALSCREEN);
            _virtualWidth = GetSystemMetrics(SM_CXVIRTUALSCREEN);
            _virtualHeight = GetSystemMetrics(SM_CYVIRTUALSCREEN);

            Console.WriteLine($"Screen metrics: Primary {_screenWidth}x{_screenHeight}, Virtual {_virtualWidth}x{_virtualHeight} at ({_virtualLeft},{_virtualTop})");
        }

        #region Mouse

        public void MoveMouse(int x, int y)
        {
            // Adjust for virtual screen offset
            int adjustedX = x - _virtualLeft;
            int adjustedY = y - _virtualTop;

            // Convert to absolute coordinates (0-65535 range)
            int absX = (adjustedX * 65535) / _virtualWidth;
            int absY = (adjustedY * 65535) / _virtualHeight;

            var input = new INPUT
            {
                Type = InputType.Mouse,
                Data = new InputUnion
                {
                    Mouse = new MOUSEINPUT
                    {
                        dx = absX,
                        dy = absY,
                        dwFlags = MouseEventFlags.Move | MouseEventFlags.Absolute | MouseEventFlags.VirtualDesk,
                        time = 0,
                        dwExtraInfo = IntPtr.Zero
                    }
                }
            };

            SendInput(1, new[] { input }, Marshal.SizeOf<INPUT>());
        }

        public void MouseButton(string button, bool down)
        {
            MouseEventFlags flags = button.ToLower() switch
            {
                "left" => down ? MouseEventFlags.LeftDown : MouseEventFlags.LeftUp,
                "right" => down ? MouseEventFlags.RightDown : MouseEventFlags.RightUp,
                "middle" => down ? MouseEventFlags.MiddleDown : MouseEventFlags.MiddleUp,
                _ => throw new ArgumentException($"Unknown button: {button}")
            };

            var input = new INPUT
            {
                Type = InputType.Mouse,
                Data = new InputUnion
                {
                    Mouse = new MOUSEINPUT
                    {
                        dwFlags = flags,
                        time = 0,
                        dwExtraInfo = IntPtr.Zero
                    }
                }
            };

            SendInput(1, new[] { input }, Marshal.SizeOf<INPUT>());
        }

        public void MouseScroll(int deltaX, int deltaY)
        {
            var inputs = new List<INPUT>();

            // Vertical scroll
            if (deltaY != 0)
            {
                inputs.Add(new INPUT
                {
                    Type = InputType.Mouse,
                    Data = new InputUnion
                    {
                        Mouse = new MOUSEINPUT
                        {
                            mouseData = (uint)(deltaY),
                            dwFlags = MouseEventFlags.Wheel,
                            time = 0,
                            dwExtraInfo = IntPtr.Zero
                        }
                    }
                });
            }

            // Horizontal scroll
            if (deltaX != 0)
            {
                inputs.Add(new INPUT
                {
                    Type = InputType.Mouse,
                    Data = new InputUnion
                    {
                        Mouse = new MOUSEINPUT
                        {
                            mouseData = (uint)(deltaX),
                            dwFlags = MouseEventFlags.HWheel,
                            time = 0,
                            dwExtraInfo = IntPtr.Zero
                        }
                    }
                });
            }

            if (inputs.Count > 0)
            {
                SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf<INPUT>());
            }
        }

        #endregion

        #region Keyboard

        public void KeyPress(int virtualKeyCode, bool down, bool shift = false, bool control = false, bool alt = false)
        {
            var inputs = new List<INPUT>();

            // Add modifier keys if needed and key is going down
            if (down)
            {
                if (control) inputs.Add(CreateKeyInput(VK.CONTROL, true));
                if (alt) inputs.Add(CreateKeyInput(VK.MENU, true));
                if (shift) inputs.Add(CreateKeyInput(VK.SHIFT, true));
            }

            // Main key
            inputs.Add(CreateKeyInput((ushort)virtualKeyCode, down));

            // Release modifier keys if key is going up
            if (!down)
            {
                if (shift) inputs.Add(CreateKeyInput(VK.SHIFT, false));
                if (alt) inputs.Add(CreateKeyInput(VK.MENU, false));
                if (control) inputs.Add(CreateKeyInput(VK.CONTROL, false));
            }

            SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf<INPUT>());
        }

        private INPUT CreateKeyInput(ushort vk, bool down)
        {
            KeyEventFlags flags = down ? KeyEventFlags.None : KeyEventFlags.KeyUp;

            // Extended keys (arrows, insert, delete, home, end, page up/down, num lock, break, print screen, divide, enter on numpad)
            if (IsExtendedKey(vk))
            {
                flags |= KeyEventFlags.ExtendedKey;
            }

            return new INPUT
            {
                Type = InputType.Keyboard,
                Data = new InputUnion
                {
                    Keyboard = new KEYBDINPUT
                    {
                        wVk = vk,
                        wScan = 0,
                        dwFlags = flags,
                        time = 0,
                        dwExtraInfo = IntPtr.Zero
                    }
                }
            };
        }

        private bool IsExtendedKey(ushort vk)
        {
            return vk switch
            {
                0x21 or 0x22 or 0x23 or 0x24 or 0x25 or 0x26 or 0x27 or 0x28 => true, // Page up/down, End, Home, Arrows
                0x2D or 0x2E => true, // Insert, Delete
                0x5B or 0x5C => true, // Windows keys
                0x6F => true, // Divide
                0x90 => true, // Num Lock
                _ => false
            };
        }

        #endregion

        #region Screen Info

        public List<Models.ScreenRect> GetScreens()
        {
            var screens = new List<Models.ScreenRect>();

            // Get all screens using System.Windows.Forms would be ideal,
            // but for simplicity we'll use virtual screen bounds
            screens.Add(new Models.ScreenRect
            {
                Width = _virtualWidth,
                Height = _virtualHeight,
                X = _virtualLeft,
                Y = _virtualTop
            });

            return screens;
        }

        #endregion
    }
}
