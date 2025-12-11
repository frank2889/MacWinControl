import Foundation
import AppKit

enum ScreenEdge {
    case left
    case right
    case top
    case bottom
}

class ScreenManager {
    private var screens: [NSScreen] = []
    private var combinedBounds: CGRect = .zero
    
    init() {
        updateScreens()
        
        // Listen for screen changes
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screensDidChange),
            name: NSApplication.didChangeScreenParametersNotification,
            object: nil
        )
    }
    
    deinit {
        NotificationCenter.default.removeObserver(self)
    }
    
    @objc private func screensDidChange() {
        updateScreens()
    }
    
    func updateScreens() {
        screens = NSScreen.screens
        calculateCombinedBounds()
        
        print("📺 Detected \(screens.count) screen(s):")
        for (index, screen) in screens.enumerated() {
            print("   Screen \(index): \(screen.frame)")
        }
        print("   Combined bounds: \(combinedBounds)")
    }
    
    private func calculateCombinedBounds() {
        guard !screens.isEmpty else {
            combinedBounds = .zero
            return
        }
        
        var minX = CGFloat.infinity
        var minY = CGFloat.infinity
        var maxX = -CGFloat.infinity
        var maxY = -CGFloat.infinity
        
        for screen in screens {
            let frame = screen.frame
            minX = min(minX, frame.minX)
            minY = min(minY, frame.minY)
            maxX = max(maxX, frame.maxX)
            maxY = max(maxY, frame.maxY)
        }
        
        combinedBounds = CGRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
    }
    
    func checkEdge(at point: CGPoint, threshold: CGFloat = 2) -> ScreenEdge? {
        // Check if point is at any edge of the combined screen bounds
        if point.x <= combinedBounds.minX + threshold {
            return .left
        }
        if point.x >= combinedBounds.maxX - threshold {
            return .right
        }
        if point.y <= combinedBounds.minY + threshold {
            return .bottom
        }
        if point.y >= combinedBounds.maxY - threshold {
            return .top
        }
        return nil
    }
    
    func getScreenInfo() -> [ScreenRect] {
        return screens.map { screen in
            ScreenRect(
                width: Int(screen.frame.width),
                height: Int(screen.frame.height),
                x: Int(screen.frame.origin.x),
                y: Int(screen.frame.origin.y)
            )
        }
    }
    
    var totalWidth: CGFloat {
        return combinedBounds.width
    }
    
    var totalHeight: CGFloat {
        return combinedBounds.height
    }
    
    var screenCount: Int {
        return screens.count
    }
}
