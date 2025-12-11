import SwiftUI

struct ContentView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    @State private var showingPermissionAlert = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HeaderView()
            
            Divider()
            
            ScrollView {
                VStack(spacing: 20) {
                    // Connection Status
                    ConnectionStatusView()
                    
                    // Screen Position
                    ScreenPositionView()
                    
                    // Instructions
                    InstructionsView()
                }
                .padding()
            }
            
            Divider()
            
            // Footer with controls
            FooterView()
        }
        .background(Color(NSColor.windowBackgroundColor))
        .onAppear {
            checkAccessibilityPermissions()
        }
        .alert("Accessibility Toegang Vereist", isPresented: $showingPermissionAlert) {
            Button("Open Systeemvoorkeuren") {
                openAccessibilitySettings()
            }
            Button("Later", role: .cancel) {}
        } message: {
            Text("MacWinControl heeft Accessibility toegang nodig om je muis en toetsenbord te kunnen onderscheppen.")
        }
    }
    
    private func checkAccessibilityPermissions() {
        let trusted = AXIsProcessTrusted()
        if !trusted {
            showingPermissionAlert = true
        }
    }
    
    private func openAccessibilitySettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
    }
}

struct HeaderView: View {
    var body: some View {
        HStack {
            Image(systemName: "desktopcomputer")
                .font(.title)
                .foregroundColor(.accentColor)
            
            VStack(alignment: .leading) {
                Text("MacWinControl")
                    .font(.title2)
                    .fontWeight(.semibold)
                Text("Bedien Windows met je Mac")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding()
    }
}

struct ConnectionStatusView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    
    var body: some View {
        GroupBox("Verbinding") {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 12, height: 12)
                    Text(connectionManager.status.description)
                        .font(.headline)
                    Spacer()
                }
                
                if !connectionManager.clientName.isEmpty {
                    HStack {
                        Image(systemName: "pc")
                        Text(connectionManager.clientName)
                            .foregroundColor(.secondary)
                    }
                }
                
                HStack {
                    Image(systemName: "network")
                    Text("Jouw IP: \(connectionManager.localIP)")
                        .foregroundColor(.secondary)
                        .textSelection(.enabled)
                    
                    Button(action: {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(connectionManager.localIP, forType: .string)
                    }) {
                        Image(systemName: "doc.on.doc")
                    }
                    .buttonStyle(.borderless)
                }
                
                Text("Poort: 52525")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 8)
        }
    }
    
    var statusColor: Color {
        switch connectionManager.status {
        case .disconnected: return .gray
        case .listening: return .orange
        case .connected: return .green
        case .error: return .red
        }
    }
}

struct ScreenPositionView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    
    var body: some View {
        GroupBox("Windows Scherm Positie") {
            VStack(spacing: 12) {
                Text("Waar staan je Windows schermen?")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack(spacing: 20) {
                    PositionButton(
                        position: .left,
                        icon: "arrow.left.square.fill",
                        selected: connectionManager.windowsPosition == .left
                    )
                    
                    // Visual representation
                    HStack(spacing: 4) {
                        if connectionManager.windowsPosition == .left {
                            WindowsScreenIcon()
                        }
                        MacScreenIcon()
                        if connectionManager.windowsPosition == .right {
                            WindowsScreenIcon()
                        }
                    }
                    
                    PositionButton(
                        position: .right,
                        icon: "arrow.right.square.fill",
                        selected: connectionManager.windowsPosition == .right
                    )
                }
            }
            .padding(.vertical, 8)
        }
    }
}

struct PositionButton: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    let position: WindowsPosition
    let icon: String
    let selected: Bool
    
    var body: some View {
        Button(action: {
            connectionManager.windowsPosition = position
        }) {
            Image(systemName: icon)
                .font(.title)
                .foregroundColor(selected ? .accentColor : .gray)
        }
        .buttonStyle(.borderless)
    }
}

struct MacScreenIcon: View {
    var body: some View {
        VStack(spacing: 2) {
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.accentColor.opacity(0.3))
                .frame(width: 50, height: 35)
                .overlay(
                    Image(systemName: "apple.logo")
                        .font(.caption)
                )
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.gray)
                .frame(width: 20, height: 3)
        }
    }
}

struct WindowsScreenIcon: View {
    var body: some View {
        VStack(spacing: 2) {
            RoundedRectangle(cornerRadius: 4)
                .fill(Color.blue.opacity(0.3))
                .frame(width: 50, height: 35)
                .overlay(
                    Image(systemName: "pc")
                        .font(.caption)
                )
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.gray)
                .frame(width: 20, height: 3)
        }
    }
}

struct InstructionsView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    
    var body: some View {
        GroupBox("Sneltoetsen") {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    KeyboardShortcut(keys: ["⌃", "⌥", "M"])
                    Text("Terug naar Mac")
                        .foregroundColor(.secondary)
                }
                HStack {
                    KeyboardShortcut(keys: ["⌃", "⌥", "W"])
                    Text("Naar Windows")
                        .foregroundColor(.secondary)
                }
            }
            .padding(.vertical, 8)
        }
    }
}

struct KeyboardShortcut: View {
    let keys: [String]
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(keys, id: \.self) { key in
                Text(key)
                    .font(.system(.caption, design: .monospaced))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.secondary.opacity(0.2))
                    .cornerRadius(4)
            }
        }
    }
}

struct FooterView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    
    var body: some View {
        HStack {
            if connectionManager.isWindowsMode {
                Label("Windows Modus Actief", systemImage: "pc")
                    .foregroundColor(.blue)
            }
            
            Spacer()
            
            if case .disconnected = connectionManager.status {
                Button("Start Server") {
                    connectionManager.startServer()
                }
                .buttonStyle(.borderedProminent)
            } else if case .listening = connectionManager.status {
                Button("Stop") {
                    connectionManager.stopServer()
                }
            } else if connectionManager.isConnected {
                Button("Verbreek") {
                    connectionManager.stopServer()
                }
            }
        }
        .padding()
    }
}

#Preview {
    ContentView()
        .environmentObject(ConnectionManager())
        .frame(width: 400, height: 500)
}
