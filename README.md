# MacWinControl

Cross-platform mouse & keyboard sharing between Mac and Windows - like Synergy/Barrier, but simpler.

## Architecture

**Single Codebase**: Built with Rust + Tauri for both Mac and Windows from the same code.

## Project Structure

```
MacWinControl/
├── RustApp/                    # Main cross-platform app (Rust + Tauri)
│   ├── src/                    # Frontend (HTML/CSS/JS)
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── main.js
│   └── src-tauri/              # Rust backend
│       └── src/
│           ├── lib.rs          # Tauri commands & state
│           ├── network.rs      # TCP server/client
│           ├── input.rs        # Mouse/keyboard control
│           └── clipboard_sync.rs
└── WindowsApp/                 # Legacy C# client (being replaced)
```

## Building

### Prerequisites
- Rust (https://rustup.rs)
- Tauri CLI: `cargo install tauri-cli`

### Mac
```bash
cd RustApp
cargo tauri build
```
Output: `src-tauri/target/release/bundle/macos/MacWinControl.app`

### Windows
```bash
cd RustApp
cargo tauri build
```
Output: `src-tauri/target/release/bundle/msi/MacWinControl_1.0.0_x64.msi`

## How It Works

1. **Mac** runs as server (Start Server button)
2. **Windows** connects to Mac's IP address
3. Move mouse to screen edge → control transfers to other computer
4. Clipboard is synchronized automatically

## Network Protocol

- Port: 52525 (TCP)
- Messages: JSON with newline delimiter
- Types: `mouse_move`, `mouse_click`, `key_event`, `clipboard`

## Features

- ✅ Multi-monitor support (detects all displays)
- ✅ Visual screen layout editor
- ✅ Drag-and-drop positioning
- ✅ Clipboard sync
- ✅ Native performance (8MB app size)

## License

MIT
