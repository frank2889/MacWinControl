import Foundation

// MARK: - Input Events

enum InputEventType: String, Codable {
    case mouseMove = "mouse_move"
    case mouseButton = "mouse_button"
    case mouseScroll = "mouse_scroll"
    case key = "key"
    case modeSwitch = "mode_switch"
    case screenInfo = "screen_info"
    case hello = "hello"
    case connected = "connected"
    case ping = "ping"
    case pong = "pong"
    case error = "error"
}

enum MouseButton: String, Codable {
    case left
    case right
    case middle
}

enum ButtonAction: String, Codable {
    case down
    case up
}

struct KeyModifiers: Codable {
    var shift: Bool = false
    var control: Bool = false
    var alt: Bool = false
    var meta: Bool = false
}

struct ScreenRect: Codable {
    let width: Int
    let height: Int
    let x: Int
    let y: Int
}

// MARK: - Outgoing Events (Mac → Windows)

struct MouseMoveEvent: Codable {
    let type = "mouse_move"
    let x: Int
    let y: Int
    let timestamp: Int64
}

struct MouseButtonEvent: Codable {
    let type = "mouse_button"
    let button: String
    let action: String
    let x: Int
    let y: Int
    let timestamp: Int64
}

struct MouseScrollEvent: Codable {
    let type = "mouse_scroll"
    let deltaX: Int
    let deltaY: Int
    let timestamp: Int64
}

struct KeyEvent: Codable {
    let type = "key"
    let keyCode: Int
    let action: String
    let modifiers: KeyModifiers
    let timestamp: Int64
}

struct ModeSwitchEvent: Codable {
    let type = "mode_switch"
    let active: Bool
}

struct HelloMessage: Codable {
    let type = "hello"
    let version: String
    var name: String?
}

struct ConnectedMessage: Codable {
    let type = "connected"
}

struct PingMessage: Codable {
    let type = "ping"
}

struct PongMessage: Codable {
    let type = "pong"
}

// MARK: - Incoming Events (Windows → Mac)

struct IncomingMessage: Codable {
    let type: String
    var version: String?
    var name: String?
    var screens: [ScreenRect]?
    var message: String?
}

// MARK: - Key Code Mapping (Mac to Windows VK codes)

struct KeyCodeMapper {
    static func macToWindows(_ macKeyCode: Int64) -> Int {
        // Common key mappings from Mac CGKeyCode to Windows VK codes
        let mapping: [Int64: Int] = [
            0: 65,   // A
            1: 83,   // S
            2: 68,   // D
            3: 70,   // F
            4: 72,   // H
            5: 71,   // G
            6: 90,   // Z
            7: 88,   // X
            8: 67,   // C
            9: 86,   // V
            11: 66,  // B
            12: 81,  // Q
            13: 87,  // W
            14: 69,  // E
            15: 82,  // R
            16: 89,  // Y
            17: 84,  // T
            18: 49,  // 1
            19: 50,  // 2
            20: 51,  // 3
            21: 52,  // 4
            22: 54,  // 6
            23: 53,  // 5
            24: 187, // =
            25: 57,  // 9
            26: 55,  // 7
            27: 189, // -
            28: 56,  // 8
            29: 48,  // 0
            30: 221, // ]
            31: 79,  // O
            32: 85,  // U
            33: 219, // [
            34: 73,  // I
            35: 80,  // P
            36: 13,  // Return
            37: 76,  // L
            38: 74,  // J
            39: 222, // '
            40: 75,  // K
            41: 186, // ;
            42: 220, // \
            43: 188, // ,
            44: 191, // /
            45: 78,  // N
            46: 77,  // M
            47: 190, // .
            48: 9,   // Tab
            49: 32,  // Space
            50: 192, // `
            51: 8,   // Backspace
            53: 27,  // Escape
            55: 91,  // Left Command -> Win
            56: 16,  // Shift
            57: 20,  // Caps Lock
            58: 18,  // Option -> Alt
            59: 17,  // Control
            60: 16,  // Right Shift
            61: 18,  // Right Option
            62: 17,  // Right Control
            96: 112, // F5
            97: 113, // F6
            98: 114, // F7
            99: 116, // F3
            100: 115, // F8
            101: 117, // F9
            103: 119, // F11
            109: 118, // F10
            111: 120, // F12
            118: 121, // F4
            120: 122, // F2
            122: 123, // F1
            123: 37, // Left Arrow
            124: 39, // Right Arrow
            125: 40, // Down Arrow
            126: 38, // Up Arrow
        ]
        
        return mapping[macKeyCode] ?? Int(macKeyCode)
    }
}
