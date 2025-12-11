import Foundation
import CoreGraphics
import AppKit

class EventCapture {
    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private var isCapturing = false
    
    private let onEvent: (Data) -> Void
    var onEdgeHit: ((ScreenEdge) -> Void)?
    
    private var screenManager = ScreenManager()
    private var lastMousePosition: CGPoint = .zero
    private var windowsMouseX: Int = 960  // Start in center of typical 1080p
    private var windowsMouseY: Int = 540
    
    init(onEvent: @escaping (Data) -> Void) {
        self.onEvent = onEvent
        setupHotkeys()
    }
    
    deinit {
        stopCapture()
    }
    
    private func setupHotkeys() {
        // Global hotkey for Ctrl+Alt+M to switch back to Mac
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            // Ctrl + Alt + M
            if event.modifierFlags.contains([.control, .option]) && event.keyCode == 46 {
                self?.stopCapture()
            }
        }
    }
    
    func startCapture() {
        guard !isCapturing else { return }
        
        let eventMask: CGEventMask = (
            (1 << CGEventType.mouseMoved.rawValue) |
            (1 << CGEventType.leftMouseDown.rawValue) |
            (1 << CGEventType.leftMouseUp.rawValue) |
            (1 << CGEventType.rightMouseDown.rawValue) |
            (1 << CGEventType.rightMouseUp.rawValue) |
            (1 << CGEventType.leftMouseDragged.rawValue) |
            (1 << CGEventType.rightMouseDragged.rawValue) |
            (1 << CGEventType.scrollWheel.rawValue) |
            (1 << CGEventType.keyDown.rawValue) |
            (1 << CGEventType.keyUp.rawValue) |
            (1 << CGEventType.flagsChanged.rawValue)
        )
        
        // Create event tap
        let callback: CGEventTapCallBack = { proxy, type, event, refcon in
            guard let refcon = refcon else { return Unmanaged.passRetained(event) }
            let capture = Unmanaged<EventCapture>.fromOpaque(refcon).takeUnretainedValue()
            return capture.handleEvent(proxy: proxy, type: type, event: event)
        }
        
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: eventMask,
            callback: callback,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            print("❌ Failed to create event tap. Check Accessibility permissions!")
            return
        }
        
        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        
        isCapturing = true
        print("✅ Event capture started")
        
        // Hide cursor
        CGDisplayHideCursor(CGMainDisplayID())
    }
    
    func stopCapture() {
        guard isCapturing else { return }
        
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
            if let source = runLoopSource {
                CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes)
            }
        }
        
        eventTap = nil
        runLoopSource = nil
        isCapturing = false
        
        // Show cursor
        CGDisplayShowCursor(CGMainDisplayID())
        
        print("⏹ Event capture stopped")
    }
    
    private func handleEvent(proxy: CGEventTapProxy, type: CGEventType, event: CGEvent) -> Unmanaged<CGEvent>? {
        let timestamp = Int64(Date().timeIntervalSince1970 * 1000)
        
        switch type {
        case .mouseMoved, .leftMouseDragged, .rightMouseDragged:
            let deltaX = event.getIntegerValueField(.mouseEventDeltaX)
            let deltaY = event.getIntegerValueField(.mouseEventDeltaY)
            
            // Update virtual Windows mouse position
            windowsMouseX += Int(deltaX)
            windowsMouseY += Int(deltaY)
            
            // Clamp to reasonable bounds (TODO: use actual Windows screen info)
            windowsMouseX = max(0, min(windowsMouseX, 3840))
            windowsMouseY = max(0, min(windowsMouseY, 2160))
            
            let moveEvent = MouseMoveEvent(
                x: windowsMouseX,
                y: windowsMouseY,
                timestamp: timestamp
            )
            sendEvent(moveEvent)
            
        case .leftMouseDown:
            sendMouseButton(button: "left", action: "down", timestamp: timestamp)
            
        case .leftMouseUp:
            sendMouseButton(button: "left", action: "up", timestamp: timestamp)
            
        case .rightMouseDown:
            sendMouseButton(button: "right", action: "down", timestamp: timestamp)
            
        case .rightMouseUp:
            sendMouseButton(button: "right", action: "up", timestamp: timestamp)
            
        case .scrollWheel:
            let deltaY = event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
            let deltaX = event.getIntegerValueField(.scrollWheelEventDeltaAxis2)
            
            let scrollEvent = MouseScrollEvent(
                deltaX: Int(deltaX) * 40,
                deltaY: Int(deltaY) * 40,
                timestamp: timestamp
            )
            sendEvent(scrollEvent)
            
        case .keyDown:
            let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
            let modifiers = getModifiers(from: event)
            
            // Check for Ctrl+Alt+M to exit Windows mode
            if keyCode == 46 && modifiers.control && modifiers.alt {
                stopCapture()
                return nil
            }
            
            let keyEvent = KeyEvent(
                keyCode: KeyCodeMapper.macToWindows(keyCode),
                action: "down",
                modifiers: modifiers,
                timestamp: timestamp
            )
            sendEvent(keyEvent)
            
        case .keyUp:
            let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
            let modifiers = getModifiers(from: event)
            
            let keyEvent = KeyEvent(
                keyCode: KeyCodeMapper.macToWindows(keyCode),
                action: "up",
                modifiers: modifiers,
                timestamp: timestamp
            )
            sendEvent(keyEvent)
            
        case .flagsChanged:
            // Handle modifier key changes if needed
            break
            
        case .tapDisabledByTimeout, .tapDisabledByUserInput:
            // Re-enable tap
            if let tap = eventTap {
                CGEvent.tapEnable(tap: tap, enable: true)
            }
            
        default:
            break
        }
        
        // Consume the event (don't pass to system) when capturing
        return nil
    }
    
    private func sendMouseButton(button: String, action: String, timestamp: Int64) {
        let event = MouseButtonEvent(
            button: button,
            action: action,
            x: windowsMouseX,
            y: windowsMouseY,
            timestamp: timestamp
        )
        sendEvent(event)
    }
    
    private func getModifiers(from event: CGEvent) -> KeyModifiers {
        let flags = event.flags
        return KeyModifiers(
            shift: flags.contains(.maskShift),
            control: flags.contains(.maskControl),
            alt: flags.contains(.maskAlternate),
            meta: flags.contains(.maskCommand)
        )
    }
    
    private func sendEvent<T: Encodable>(_ event: T) {
        guard let data = try? JSONEncoder().encode(event) else { return }
        onEvent(data)
    }
    
    // Check for screen edge (called when not capturing)
    func checkForEdge(at point: CGPoint) {
        if let edge = screenManager.checkEdge(at: point) {
            onEdgeHit?(edge)
        }
    }
}
