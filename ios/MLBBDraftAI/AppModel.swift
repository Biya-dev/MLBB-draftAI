import Foundation
import SwiftUI

/// The container app. Its job is small:
///   * show the PC address the extension will stream to
///   * let the user start/stop the broadcast (required by iOS)
///   * show the live extension status
///
/// The extension does all the real work. See `BroadcastSampleHandler`.
@main
struct MLBBDraftAIApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
        }
    }
}

/// Observable state for the UI.
final class AppModel: ObservableObject {

    @Published var status: String = "Idle"
    @Published var statusIsStale: Bool = false
    @Published var isBroadcasting: Bool = false
    @Published var lastUpdate: Date = Date()

    /// Poll the shared status written by the extension.
    private var timer: Timer?

    init() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) {
            [weak self] _ in
            self?.refresh()
        }
        refresh()
    }

    deinit {
        timer?.invalidate()
    }

    func refresh() {
        guard let info = SharedStatus.read() else {
            if status != "Waiting for the broadcast extension to report..." {
                status = "Waiting for the broadcast extension to report..."
                statusIsStale = true
                lastUpdate = Date()
            }
            return
        }
        status = info.message
        // If the extension has not written for a while it is not running.
        statusIsStale = info.age > 10
        lastUpdate = Date()
    }
}
