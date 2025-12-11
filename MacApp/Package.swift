// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MacWinControl",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "MacWinControl", targets: ["MacWinControl"])
    ],
    targets: [
        .executableTarget(
            name: "MacWinControl",
            path: "MacWinControl"
        )
    ]
)
