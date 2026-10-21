import Foundation

/// Shared configuration for both the container app and the Broadcast
/// Upload Extension.
///
/// This file is a member of BOTH targets, so there is no App Group
/// entitlement and no shared-container requirement. Edit the values here,
/// rebuild, and both sides pick them up. This is the simplest approach
/// that works with a free Apple ID provisioning profile.
///
/// The extension needs a value it can read at launch: the PC's LAN IP and
/// the ingest port. The token is optional but recommended.
enum SharedConfig {

    /// IP address of the Windows PC on the same Wi-Fi network.
    /// Find it by running `ipconfig` on the PC and reading the
    /// "IPv4 Address" of the Wi-Fi adapter.
    static let receiverHost = "192.168.1.158"

    /// TCP port the Python receiver listens on for frames.
    static let receiverPort: UInt16 = 8765

    /// Shared secret sent in the AUTH frame. Both sides must match.
    /// Leave empty to disable authentication (fine on a trusted LAN).
    static let sharedToken = "mlbb-phase1"

    /// Maximum width (px) of a transmitted frame. iPhone frames are
    /// scaled down to this width before encoding to keep the link fast.
    static let maxFrameWidth: Int = 1280

    /// Target frames per second. Higher costs more battery and bandwidth.
    static let targetFPS: Double = 12.0

    /// JPEG quality (0.0 - 1.0) used for the transmitted frames.
    static let jpegQuality: CGFloat = 0.6

    /// Seconds to wait before the first reconnect attempt.
    static let initialReconnectDelay: Double = 1.0

    /// Maximum seconds between reconnect attempts.
    static let maxReconnectDelay: Double = 15.0

    /// How long to wait for the TCP connection to establish.
    static let connectTimeout: Double = 8.0
}
