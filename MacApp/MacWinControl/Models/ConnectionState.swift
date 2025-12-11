import Foundation
import Combine

enum WindowsPosition: String, CaseIterable {
    case right = "Rechts"
    case left = "Links"
}

enum ConnectionStatus {
    case disconnected
    case listening
    case connected
    case error(String)
    
    var description: String {
        switch self {
        case .disconnected: return "Niet verbonden"
        case .listening: return "Wachten op verbinding..."
        case .connected: return "Verbonden"
        case .error(let msg): return "Fout: \(msg)"
        }
    }
    
    var color: String {
        switch self {
        case .disconnected: return "gray"
        case .listening: return "orange"
        case .connected: return "green"
        case .error: return "red"
        }
    }
}

class ConnectionManager: ObservableObject {
    @Published var status: ConnectionStatus = .disconnected
    @Published var clientName: String = ""
    @Published var windowsPosition: WindowsPosition = .right
    @Published var isWindowsMode: Bool = false
    @Published var localIP: String = ""
    @Published var windowsScreens: [ScreenRect] = []
    
    private var networkServer: NetworkServer?
    private var eventCapture: EventCapture?
    private var screenManager: ScreenManager?
    
    var isConnected: Bool {
        if case .connected = status { return true }
        return false
    }
    
    init() {
        screenManager = ScreenManager()
        localIP = NetworkServer.getLocalIP() ?? "Unknown"
        
        eventCapture = EventCapture { [weak self] event in
            self?.sendEvent(event)
        }
        
        eventCapture?.onEdgeHit = { [weak self] edge in
            self?.handleEdgeHit(edge)
        }
    }
    
    func startServer() {
        networkServer = NetworkServer(port: 52525)
        
        networkServer?.onClientConnected = { [weak self] name in
            DispatchQueue.main.async {
                self?.status = .connected
                self?.clientName = name
            }
        }
        
        networkServer?.onClientDisconnected = { [weak self] in
            DispatchQueue.main.async {
                self?.status = .listening
                self?.clientName = ""
                self?.isWindowsMode = false
            }
        }
        
        networkServer?.onScreenInfo = { [weak self] screens in
            DispatchQueue.main.async {
                self?.windowsScreens = screens
            }
        }
        
        networkServer?.start()
        status = .listening
    }
    
    func stopServer() {
        networkServer?.stop()
        networkServer = nil
        status = .disconnected
        clientName = ""
        isWindowsMode = false
    }
    
    func switchToMac() {
        isWindowsMode = false
        eventCapture?.stopCapture()
        sendModeSwitch(active: false)
    }
    
    func switchToWindows() {
        guard isConnected else { return }
        isWindowsMode = true
        eventCapture?.startCapture()
        sendModeSwitch(active: true)
    }
    
    private func handleEdgeHit(_ edge: ScreenEdge) {
        guard isConnected else { return }
        
        // Check if edge matches windows position
        let shouldSwitch = (windowsPosition == .right && edge == .right) ||
                          (windowsPosition == .left && edge == .left)
        
        if shouldSwitch && !isWindowsMode {
            switchToWindows()
        }
    }
    
    private func sendEvent(_ event: Data) {
        guard isWindowsMode else { return }
        networkServer?.send(data: event)
    }
    
    private func sendModeSwitch(active: Bool) {
        let event = ModeSwitchEvent(active: active)
        if let data = try? JSONEncoder().encode(event) {
            networkServer?.send(data: data)
        }
    }
}
