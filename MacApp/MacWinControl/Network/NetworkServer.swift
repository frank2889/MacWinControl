import Foundation
import Network

class NetworkServer {
    private var listener: NWListener?
    private var connection: NWConnection?
    private let port: UInt16
    private let queue = DispatchQueue(label: "NetworkServer", qos: .userInteractive)
    
    var onClientConnected: ((String) -> Void)?
    var onClientDisconnected: (() -> Void)?
    var onScreenInfo: (([ScreenRect]) -> Void)?
    
    init(port: UInt16) {
        self.port = port
    }
    
    func start() {
        do {
            let params = NWParameters.tcp
            params.allowLocalEndpointReuse = true
            
            listener = try NWListener(using: params, on: NWEndpoint.Port(rawValue: port)!)
            
            listener?.stateUpdateHandler = { [weak self] state in
                switch state {
                case .ready:
                    print("✅ Server listening on port \(self?.port ?? 0)")
                case .failed(let error):
                    print("❌ Server failed: \(error)")
                case .cancelled:
                    print("⏹ Server cancelled")
                default:
                    break
                }
            }
            
            listener?.newConnectionHandler = { [weak self] connection in
                self?.handleNewConnection(connection)
            }
            
            listener?.start(queue: queue)
            
        } catch {
            print("❌ Failed to start server: \(error)")
        }
    }
    
    func stop() {
        connection?.cancel()
        connection = nil
        listener?.cancel()
        listener = nil
    }
    
    private func handleNewConnection(_ newConnection: NWConnection) {
        // Only allow one connection at a time
        connection?.cancel()
        connection = newConnection
        
        connection?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                print("✅ Client connected")
                self?.sendHello()
                self?.startReceiving()
            case .failed(let error):
                print("❌ Connection failed: \(error)")
                self?.onClientDisconnected?()
            case .cancelled:
                print("⏹ Connection cancelled")
                self?.onClientDisconnected?()
            default:
                break
            }
        }
        
        connection?.start(queue: queue)
    }
    
    private func sendHello() {
        let hello = HelloMessage(version: "1.0", name: Host.current().localizedName)
        if let data = try? JSONEncoder().encode(hello),
           var message = String(data: data, encoding: .utf8) {
            message += "\n"
            send(string: message)
        }
    }
    
    private func startReceiving() {
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            if let data = data, !data.isEmpty {
                self?.handleReceivedData(data)
            }
            
            if let error = error {
                print("❌ Receive error: \(error)")
                return
            }
            
            if isComplete {
                self?.onClientDisconnected?()
                return
            }
            
            // Continue receiving
            self?.startReceiving()
        }
    }
    
    private func handleReceivedData(_ data: Data) {
        guard let string = String(data: data, encoding: .utf8) else { return }
        
        // Handle multiple messages (separated by newlines)
        let messages = string.split(separator: "\n")
        for message in messages {
            handleMessage(String(message))
        }
    }
    
    private func handleMessage(_ message: String) {
        guard let data = message.data(using: .utf8),
              let incoming = try? JSONDecoder().decode(IncomingMessage.self, from: data) else {
            return
        }
        
        switch incoming.type {
        case "hello":
            let clientName = incoming.name ?? "Windows PC"
            print("👋 Received hello from: \(clientName)")
            
            // Send connected confirmation
            let connected = ConnectedMessage()
            if let data = try? JSONEncoder().encode(connected),
               var msg = String(data: data, encoding: .utf8) {
                msg += "\n"
                send(string: msg)
            }
            
            onClientConnected?(clientName)
            
        case "screen_info":
            if let screens = incoming.screens {
                print("📺 Received Windows screen info: \(screens.count) screens")
                onScreenInfo?(screens)
            }
            
        case "ping":
            let pong = PongMessage()
            if let data = try? JSONEncoder().encode(pong),
               var msg = String(data: data, encoding: .utf8) {
                msg += "\n"
                send(string: msg)
            }
            
        default:
            break
        }
    }
    
    func send(data: Data) {
        guard var message = String(data: data, encoding: .utf8) else { return }
        message += "\n"
        send(string: message)
    }
    
    private func send(string: String) {
        guard let data = string.data(using: .utf8) else { return }
        
        connection?.send(content: data, completion: .contentProcessed { error in
            if let error = error {
                print("❌ Send error: \(error)")
            }
        })
    }
    
    static func getLocalIP() -> String? {
        var address: String?
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        
        if getifaddrs(&ifaddr) == 0 {
            var ptr = ifaddr
            while ptr != nil {
                defer { ptr = ptr?.pointee.ifa_next }
                
                let interface = ptr?.pointee
                let addrFamily = interface?.ifa_addr.pointee.sa_family
                
                if addrFamily == UInt8(AF_INET) {
                    let name = String(cString: (interface?.ifa_name)!)
                    if name == "en0" || name == "en1" {
                        var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                        getnameinfo(interface?.ifa_addr,
                                   socklen_t((interface?.ifa_addr.pointee.sa_len)!),
                                   &hostname,
                                   socklen_t(hostname.count),
                                   nil,
                                   0,
                                   NI_NUMERICHOST)
                        address = String(cString: hostname)
                    }
                }
            }
            freeifaddrs(ifaddr)
        }
        
        return address
    }
}
