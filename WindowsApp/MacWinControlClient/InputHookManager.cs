using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace MacWinControlClient
{
    /// <summary>
    /// Low-level Windows input hooks for capturing mouse and keyboard events
    /// </summary>
    public class InputHookManager : IDisposable
    {
        #region Win32 API

        private const int WH_KEYBOARD_LL = 13;
        private const int WH_MOUSE_LL = 14;

        private const int WM_KEYDOWN = 0x0100;
        private const int WM_KEYUP = 0x0101;
        private const int WM_SYSKEYDOWN = 0x0104;
        private const int WM_SYSKEYUP = 0x0105;

        private const int WM_MOUSEMOVE = 0x0200;
        private const int WM_LBUTTONDOWN = 0x0201;
        private const int WM_LBUTTONUP = 0x0202;
        private const int WM_RBUTTONDOWN = 0x0204;
        private const int WM_RBUTTONUP = 0x0205;
        private const int WM_MBUTTONDOWN = 0x0207;
        private const int WM_MBUTTONUP = 0x0208;
        private const int WM_MOUSEWHEEL = 0x020A;
        private const int WM_MOUSEHWHEEL = 0x020E;

        [StructLayout(LayoutKind.Sequential)]
        private struct POINT
        {
            public int x;
            public int y;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSLLHOOKSTRUCT
        {
            public POINT pt;
            public uint mouseData;
            public uint flags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct KBDLLHOOKSTRUCT
        {
            public uint vkCode;
            public uint scanCode;
            public uint flags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        private delegate IntPtr LowLevelHookProc(int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr SetWindowsHookEx(int idHook, LowLevelHookProc lpfn, IntPtr hMod, uint dwThreadId);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool UnhookWindowsHookEx(IntPtr hhk);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr GetModuleHandle(string lpModuleName);

        [DllImport("user32.dll")]
        private static extern short GetAsyncKeyState(int vKey);

        #endregion

        #region Events

        public event EventHandler<MouseMoveEventArgs>? MouseMoved;
        public event EventHandler<MouseClickEventArgs>? MouseClicked;
        public event EventHandler<MouseScrollEventArgs>? MouseScrolled;
        public event EventHandler<KeyEventArgs>? KeyPressed;

        #endregion

        #region Fields

        private IntPtr _mouseHookId = IntPtr.Zero;
        private IntPtr _keyboardHookId = IntPtr.Zero;
        private LowLevelHookProc? _mouseProc;
        private LowLevelHookProc? _keyboardProc;
        private bool _isHooked = false;
        private bool _suppressInput = false;
        private int _lastMouseX = 0;
        private int _lastMouseY = 0;

        #endregion

        #region Public Methods

        public void Start(bool suppressInput = false)
        {
            if (_isHooked) return;

            _suppressInput = suppressInput;
            _mouseProc = MouseHookCallback;
            _keyboardProc = KeyboardHookCallback;

            using var curProcess = Process.GetCurrentProcess();
            using var curModule = curProcess.MainModule;

            if (curModule != null)
            {
                var moduleHandle = GetModuleHandle(curModule.ModuleName);
                _mouseHookId = SetWindowsHookEx(WH_MOUSE_LL, _mouseProc, moduleHandle, 0);
                _keyboardHookId = SetWindowsHookEx(WH_KEYBOARD_LL, _keyboardProc, moduleHandle, 0);
            }

            _isHooked = true;
            Console.WriteLine("[InputHook] Started");
        }

        public void Stop()
        {
            if (!_isHooked) return;

            if (_mouseHookId != IntPtr.Zero)
            {
                UnhookWindowsHookEx(_mouseHookId);
                _mouseHookId = IntPtr.Zero;
            }

            if (_keyboardHookId != IntPtr.Zero)
            {
                UnhookWindowsHookEx(_keyboardHookId);
                _keyboardHookId = IntPtr.Zero;
            }

            _isHooked = false;
            Console.WriteLine("[InputHook] Stopped");
        }

        public void SetSuppressInput(bool suppress)
        {
            _suppressInput = suppress;
        }

        public void Dispose()
        {
            Stop();
        }

        #endregion

        #region Hook Callbacks

        private IntPtr MouseHookCallback(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0)
            {
                var hookStruct = Marshal.PtrToStructure<MSLLHOOKSTRUCT>(lParam);
                int msg = wParam.ToInt32();

                switch (msg)
                {
                    case WM_MOUSEMOVE:
                        int dx = hookStruct.pt.x - _lastMouseX;
                        int dy = hookStruct.pt.y - _lastMouseY;
                        _lastMouseX = hookStruct.pt.x;
                        _lastMouseY = hookStruct.pt.y;

                        MouseMoved?.Invoke(this, new MouseMoveEventArgs
                        {
                            X = hookStruct.pt.x,
                            Y = hookStruct.pt.y,
                            DX = dx,
                            DY = dy
                        });
                        break;

                    case WM_LBUTTONDOWN:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "left", Pressed = true });
                        break;

                    case WM_LBUTTONUP:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "left", Pressed = false });
                        break;

                    case WM_RBUTTONDOWN:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "right", Pressed = true });
                        break;

                    case WM_RBUTTONUP:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "right", Pressed = false });
                        break;

                    case WM_MBUTTONDOWN:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "middle", Pressed = true });
                        break;

                    case WM_MBUTTONUP:
                        MouseClicked?.Invoke(this, new MouseClickEventArgs { Button = "middle", Pressed = false });
                        break;

                    case WM_MOUSEWHEEL:
                        short wheelDelta = (short)((hookStruct.mouseData >> 16) & 0xffff);
                        MouseScrolled?.Invoke(this, new MouseScrollEventArgs { DX = 0, DY = wheelDelta / 120.0 });
                        break;

                    case WM_MOUSEHWHEEL:
                        short hWheelDelta = (short)((hookStruct.mouseData >> 16) & 0xffff);
                        MouseScrolled?.Invoke(this, new MouseScrollEventArgs { DX = hWheelDelta / 120.0, DY = 0 });
                        break;
                }

                // Suppress input if needed (when controlling Mac)
                if (_suppressInput && msg != WM_MOUSEMOVE)
                {
                    return (IntPtr)1;
                }
            }

            return CallNextHookEx(_mouseHookId, nCode, wParam, lParam);
        }

        private IntPtr KeyboardHookCallback(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0)
            {
                var hookStruct = Marshal.PtrToStructure<KBDLLHOOKSTRUCT>(lParam);
                int msg = wParam.ToInt32();
                bool isDown = msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN;

                var modifiers = GetCurrentModifiers();
                string keyName = ((Keys)hookStruct.vkCode).ToString();

                KeyPressed?.Invoke(this, new KeyEventArgs
                {
                    KeyCode = (int)hookStruct.vkCode,
                    KeyName = keyName,
                    IsDown = isDown,
                    Modifiers = modifiers
                });

                // Suppress input if needed
                if (_suppressInput)
                {
                    return (IntPtr)1;
                }
            }

            return CallNextHookEx(_keyboardHookId, nCode, wParam, lParam);
        }

        private List<string> GetCurrentModifiers()
        {
            var mods = new List<string>();

            if ((GetAsyncKeyState((int)Keys.LShiftKey) & 0x8000) != 0 ||
                (GetAsyncKeyState((int)Keys.RShiftKey) & 0x8000) != 0)
                mods.Add("shift");

            if ((GetAsyncKeyState((int)Keys.LControlKey) & 0x8000) != 0 ||
                (GetAsyncKeyState((int)Keys.RControlKey) & 0x8000) != 0)
                mods.Add("ctrl");

            if ((GetAsyncKeyState((int)Keys.LMenu) & 0x8000) != 0 ||
                (GetAsyncKeyState((int)Keys.RMenu) & 0x8000) != 0)
                mods.Add("alt");

            if ((GetAsyncKeyState((int)Keys.LWin) & 0x8000) != 0 ||
                (GetAsyncKeyState((int)Keys.RWin) & 0x8000) != 0)
                mods.Add("win");

            return mods;
        }

        #endregion
    }

    #region Event Args

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

    public class MouseScrollEventArgs : EventArgs
    {
        public double DX { get; set; }
        public double DY { get; set; }
    }

    public class KeyEventArgs : EventArgs
    {
        public int KeyCode { get; set; }
        public string KeyName { get; set; } = "";
        public bool IsDown { get; set; }
        public List<string> Modifiers { get; set; } = new();
    }

    #endregion
}
