# MacWinControl Protocol Specification

## Overview

Communication between Mac (server) and Windows (client) uses TCP on port **52525**.
Messages are JSON encoded, terminated by newline (`\n`).

## Connection Flow

```
1. Windows client connects to Mac server
2. Mac sends: {"type": "hello", "version": "1.0"}
3. Windows responds: {"type": "hello", "version": "1.0", "name": "DESKTOP-PC"}
4. Mac sends: {"type": "connected"}
5. Ready for input events
```

## Message Types

### Mouse Move
```json
{
  "type": "mouse_move",
  "x": 500,
  "y": 300,
  "timestamp": 1702300000000
}
```

### Mouse Button
```json
{
  "type": "mouse_button",
  "button": "left",
  "action": "down",
  "x": 500,
  "y": 300,
  "timestamp": 1702300000000
}
```
- `button`: "left", "right", "middle"
- `action`: "down", "up"

### Mouse Scroll
```json
{
  "type": "mouse_scroll",
  "deltaX": 0,
  "deltaY": -120,
  "timestamp": 1702300000000
}
```

### Key Event
```json
{
  "type": "key",
  "keyCode": 65,
  "action": "down",
  "modifiers": {
    "shift": false,
    "control": false,
    "alt": false,
    "meta": false
  },
  "timestamp": 1702300000000
}
```
- `keyCode`: Virtual key code (cross-platform mapped)
- `action`: "down", "up"

### Mode Switch
```json
{
  "type": "mode_switch",
  "active": true
}
```
- `active`: true = Windows receives input, false = Mac mode

### Screen Info (Windows → Mac)
```json
{
  "type": "screen_info",
  "screens": [
    {"width": 1920, "height": 1080, "x": 0, "y": 0},
    {"width": 1920, "height": 1080, "x": 1920, "y": 0}
  ]
}
```

### Ping/Pong (Keep-alive)
```json
{"type": "ping"}
{"type": "pong"}
```

## Key Code Mapping

Uses Windows Virtual Key codes as the standard:
- A-Z: 65-90
- 0-9: 48-57
- F1-F12: 112-123
- Enter: 13
- Escape: 27
- Space: 32
- Backspace: 8
- Tab: 9
- Arrow keys: 37 (left), 38 (up), 39 (right), 40 (down)

## Error Handling

```json
{
  "type": "error",
  "message": "Description of error"
}
```

## Disconnect

Either side can close the TCP connection. Client should attempt reconnect after 3 seconds.
