import AVFoundation
import CoreImage
import CoreMedia
import Foundation
import QuartzCore
import ReplayKit
import UIKit
import os.log

/// ReplayKit Broadcast Upload Extension sample handler.
///
/// Captures the screen via ReplayKit, converts each sample to a JPEG at a
/// bounded resolution, and streams it to the PC over the local Wi-Fi.
///
/// IMPORTANT: this extension only starts after the user explicitly
/// starts a broadcast from Control Center (or from the container app's
/// broadcast picker). iOS requires that user gesture; there is no way
/// around it.
final class BroadcastSampleHandler: RPBroadcastSampleHandler {

    private let sender = FrameSender()
    private let context = CIContext(options: nil)

    /// ReplayKit hands us samples at display rate; we throttle to
    /// `SharedConfig.targetFPS` so we do not saturate the Wi-Fi link.
    private var lastSendTime: CFTimeInterval = 0
    private let minimumInterval: CFTimeInterval

    override init() {
        minimumInterval = 1.0 / max(SharedConfig.targetFPS, 1.0)
        super.init()
        sender.onStateChange = { [weak self] state in
            self?.recordStatus(state)
        }
    }

    override func broadcastStarted(withSetupInfo setupInfo: [String: NSObject]?) {
        // Called when the user starts the broadcast.
        lastSendTime = 0
        // The sender publishes its own state (connecting/connected/...),
        // so we do not force a status here - that would briefly lie.
        sender.start()
    }

    override func broadcastPaused() {
        // The user paused the broadcast. Keep the connection alive but
        // stop sending frames.
    }

    override func broadcastResumed() {
        lastSendTime = 0
    }

    override func broadcastFinished() {
        sender.stop()
        recordStatus(.idle)
    }

    override func sampleHandler(
        _ sampleBuffer: CMSampleBuffer,
        with sampleBufferType: RPSampleBufferType
    ) {
        switch sampleBufferType {
        case .video:
            handleVideoSample(sampleBuffer)
        case .audio:
            // Audio is intentionally ignored: this is a video pipeline.
            break
        @unknown default:
            break
        }
    }

    // MARK: - Video

    private func handleVideoSample(_ sampleBuffer: CMSampleBuffer) {
        let now = CACurrentMediaTime()
        if now - lastSendTime < minimumInterval { return }
        lastSendTime = now

        guard let pixelBuffer = sampleBuffer.imageBuffer else { return }
        guard let jpeg = encodeJPEG(pixelBuffer) else { return }
        sender.send(jpeg: jpeg)
    }

    /// Convert a CVPixelBuffer to JPEG, scaled down to `maxFrameWidth`.
    private func encodeJPEG(_ pixelBuffer: CVPixelBuffer) -> Data? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)

        // Scale down if the frame is wider than the configured maximum.
        let scale = min(
            1.0,
            CGFloat(SharedConfig.maxFrameWidth) / max(ciImage.extent.width, 1)
        )
        let target = ciImage.transformed(by: CGAffineTransform(scaleX: scale, y: scale))

        guard let cgImage = context.createCGImage(target, from: target.extent) else {
            return nil
        }
        let uiImage = UIImage(cgImage: cgImage)
        guard let data = uiImage.jpegData(compressionQuality: SharedConfig.jpegQuality) else {
            return nil
        }
        return data
    }

    // MARK: - Status

    /// Record a human-readable status so the container app (and the PC
    /// dashboard) can show what the extension is doing.
    private func recordStatus(_ state: FrameSender.State) {
        let text: String
        switch state {
        case .idle:
            text = "Broadcast stopped."
        case .connecting:
            text = "Connecting to \(SharedConfig.receiverHost):\(SharedConfig.receiverPort)..."
        case .connected:
            text = "Connected. Streaming at up to \(Int(SharedConfig.targetFPS)) FPS."
        case .waitingToReconnect(let seconds):
            text = "Reconnecting in \(Int(seconds))s..."
        case .failed(let message):
            text = "Error: \(message)"
        }
        SharedStatus.write(text)
    }
}
