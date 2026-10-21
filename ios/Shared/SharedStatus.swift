import Foundation

/// Shares a short status string between the Broadcast Upload Extension and
/// the container app.
///
/// App Groups need an entitlement. A free personal team *can* use them, but
/// if the App Group fails to provision we must not crash: every accessor
/// here falls back to standard `UserDefaults` (extension-local) so the app
/// still works, just without cross-process status sharing.
enum SharedStatus {

    static let appGroupID = "group.mlbb.draftai"
    static let statusKey = "mlbb.broadcast.status"
    static let timestampKey = "mlbb.broadcast.timestamp"

    private static var defaults: UserDefaults {
        UserDefaults(suiteName: appGroupID) ?? .standard
    }

    static func write(_ message: String) {
        defaults.set(message, forKey: statusKey)
        defaults.set(Date().timeIntervalSince1970, forKey: timestampKey)
    }

    /// Returns the last status and how long ago it was written.
    /// Returns nil if the extension has never reported in.
    static func read() -> (message: String, age: TimeInterval)? {
        let ts = defaults.double(forKey: timestampKey)
        guard ts > 0 else { return nil }
        let message = defaults.string(forKey: statusKey) ?? "Unknown status"
        return (message, Date().timeIntervalSince1970 - ts)
    }
}
