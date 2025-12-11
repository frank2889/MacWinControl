import SwiftUI

@main
struct MacWinControlApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var connectionManager = ConnectionManager()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(connectionManager)
                .frame(minWidth: 400, minHeight: 500)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        
        MenuBarExtra("MacWinControl", systemImage: connectionManager.isConnected ? "link.circle.fill" : "link.circle") {
            MenuBarView()
                .environmentObject(connectionManager)
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Request accessibility permissions
        let options: NSDictionary = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
        let accessEnabled = AXIsProcessTrustedWithOptions(options)
        
        if !accessEnabled {
            print("⚠️ Accessibility permissions required!")
        }
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false // Keep running in menu bar
    }
}

struct MenuBarView: View {
    @EnvironmentObject var connectionManager: ConnectionManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(connectionManager.isConnected ? "Connected: \(connectionManager.clientName)" : "Not Connected")
                .font(.headline)
            
            Divider()
            
            if connectionManager.isWindowsMode {
                Button("Switch to Mac (⌃⌥M)") {
                    connectionManager.switchToMac()
                }
            }
            
            Button("Open Settings...") {
                NSApp.activate(ignoringOtherApps: true)
                if let window = NSApp.windows.first {
                    window.makeKeyAndOrderFront(nil)
                }
            }
            
            Divider()
            
            Button("Quit") {
                NSApp.terminate(nil)
            }
        }
        .padding()
    }
}
