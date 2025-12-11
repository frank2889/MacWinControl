using System.Runtime.InteropServices;

namespace MacWinControlClient.Input
{
    /// <summary>
    /// P/Invoke declarations for Windows input APIs
    /// </summary>
    public static class NativeInput
    {
        #region SendInput

        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

        [DllImport("user32.dll")]
        public static extern bool SetCursorPos(int X, int Y);

        [DllImport("user32.dll")]
        public static extern bool GetCursorPos(out POINT lpPoint);

        [DllImport("user32.dll")]
        public static extern int GetSystemMetrics(int nIndex);

        public const int SM_CXSCREEN = 0;
        public const int SM_CYSCREEN = 1;
        public const int SM_XVIRTUALSCREEN = 76;
        public const int SM_YVIRTUALSCREEN = 77;
        public const int SM_CXVIRTUALSCREEN = 78;
        public const int SM_CYVIRTUALSCREEN = 79;

        #endregion

        #region Structures

        [StructLayout(LayoutKind.Sequential)]
        public struct POINT
        {
            public int X;
            public int Y;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct INPUT
        {
            public InputType Type;
            public InputUnion Data;
        }

        [StructLayout(LayoutKind.Explicit)]
        public struct InputUnion
        {
            [FieldOffset(0)]
            public MOUSEINPUT Mouse;
            [FieldOffset(0)]
            public KEYBDINPUT Keyboard;
            [FieldOffset(0)]
            public HARDWAREINPUT Hardware;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct MOUSEINPUT
        {
            public int dx;
            public int dy;
            public uint mouseData;
            public MouseEventFlags dwFlags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct KEYBDINPUT
        {
            public ushort wVk;
            public ushort wScan;
            public KeyEventFlags dwFlags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct HARDWAREINPUT
        {
            public uint uMsg;
            public ushort wParamL;
            public ushort wParamH;
        }

        #endregion

        #region Enums

        public enum InputType : uint
        {
            Mouse = 0,
            Keyboard = 1,
            Hardware = 2
        }

        [Flags]
        public enum MouseEventFlags : uint
        {
            Move = 0x0001,
            LeftDown = 0x0002,
            LeftUp = 0x0004,
            RightDown = 0x0008,
            RightUp = 0x0010,
            MiddleDown = 0x0020,
            MiddleUp = 0x0040,
            XDown = 0x0080,
            XUp = 0x0100,
            Wheel = 0x0800,
            HWheel = 0x1000,
            MoveNoCoalesce = 0x2000,
            VirtualDesk = 0x4000,
            Absolute = 0x8000
        }

        [Flags]
        public enum KeyEventFlags : uint
        {
            None = 0x0000,
            ExtendedKey = 0x0001,
            KeyUp = 0x0002,
            Unicode = 0x0004,
            Scancode = 0x0008
        }

        #endregion

        #region Virtual Key Codes

        public static class VK
        {
            public const ushort LBUTTON = 0x01;
            public const ushort RBUTTON = 0x02;
            public const ushort MBUTTON = 0x04;
            public const ushort BACK = 0x08;
            public const ushort TAB = 0x09;
            public const ushort RETURN = 0x0D;
            public const ushort SHIFT = 0x10;
            public const ushort CONTROL = 0x11;
            public const ushort MENU = 0x12; // Alt
            public const ushort ESCAPE = 0x1B;
            public const ushort SPACE = 0x20;
            public const ushort LEFT = 0x25;
            public const ushort UP = 0x26;
            public const ushort RIGHT = 0x27;
            public const ushort DOWN = 0x28;
            public const ushort LWIN = 0x5B;
            public const ushort RWIN = 0x5C;
        }

        #endregion
    }
}
