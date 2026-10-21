import Foundation
import Network

/// TCP sender used by the Broadcast Upload Extension.
///
/// Responsibilities:
///   * open a TCP connection to the PC over the local Wi-Fi
///   * send the AUTH frame once, then JPEG frames
///   * reconnect automatically with exponential backoff
///   * never block the ReplayKit sample handler for long
///
/// The sender runs on a dedicated serial queue, so ReplayKit never blocks
/// on the network.
final class FrameSender {

    enum State: Equatable {
        case idle
        case connecting
        case connected
        case waitingToReconnect(seconds: Double)
        case failed(String)
    }

    /// Called on the sender queue whenever the state changes.
    var onStateChange: ((State) -> Void)?

    private let host: String
    private let port: UInt16
    private let token: String
    private let connectTimeout: Double

    private let queue = DispatchQueue(label: "mlbb.sender.queue")
    private var connection: NWConnection?
    private var didSendAuth = false
    private var reconnectAttempt = 0
    private var reconnectWorkItem: DispatchWorkItem?
    private var isStopped = true
    private var isReady = false

    init(
        host: String = SharedConfig.receiverHost,
        port: UInt16 = SharedConfig.receiverPort,
        token: String = SharedConfig.sharedToken,
        connectTimeout: Double = SharedConfig.connectTimeout
    ) {
        self.host = host
        self.port = port
        self.token = token
        self.connectTimeout = connectTimeout
    }

    // MARK: - Lifecycle

    func start() {
        queue.async { [weak self] in
            guard let self else { return }
            self.isStopped = false
            self.connect()
        }
    }

    func stop() {
        queue.async { [weak self] in
            guard let self else { return }
            self.isStopped = true
            self.reconnectWorkItem?.cancel()
            self.reconnectWorkItem = nil
            self.connection?.cancel()
            self.connection = nil
            self.isReady = false
            self.didSendAuth = false
            self.updateState(.idle)
        }
    }

    // MARK: - Connection

    private func connect() {
        guard !isStopped else { return }
        updateState(.connecting)

        let endpoint = NWEndpoint.hostPort(
            host: NWEndpoint.Host(host),
            port: NWEndpoint.Port(rawValue: port) ?? 8765
        )
        let params = NWParameters.tcp
        params.includePeerToPeer = true
        params.allowLocalEndpointReuse = true

        let conn = NWConnection(to: endpoint, using: params)
        connection = conn

        conn.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                self.queue.async {
                    guard self.connection === conn else { return }
                    self.isReady = true
                    self.reconnectAttempt = 0
                    self.updateState(.connected)
                    if !self.didSendAuth {
                        self.didSendAuth = true
                        self.sendRaw(WireProtocol.authFrame(token: self.token))
                    }
                }
            case .failed(let error):
                self.queue.async {
                    // Ignore a failure from a connection we already
                    // replaced - otherwise we would cancel the new one.
                    guard self.connection === conn else { return }
                    self.isReady = false
                    self.didSendAuth = false
                    self.connection?.cancel()
                    self.connection = nil
                    self.updateState(.failed(error.localizedDescription))
                    self.scheduleReconnect()
                }
            case .cancelled:
                self.queue.async {
                    guard self.connection === conn else { return }
                    self.isReady = false
                    self.didSendAuth = false
                }
            default:
                break
            }
        }

        conn.start(queue: queue)

        // Guard against a silent connection attempt.
        queue.asyncAfter(deadline: .now() + connectTimeout) { [weak self] in
            guard let self, self.connection === conn, !self.isReady else { return }
            self.connection?.cancel()
            self.connection = nil
            self.updateState(.failed("Connection timed out"))
            self.scheduleReconnect()
        }
    }

    /// Exponential backoff: 1s, 2s, 4s, 8s ... capped at maxReconnectDelay.
    private func scheduleReconnect() {
        guard !isStopped else { return }
        reconnectWorkItem?.cancel()
        let delay = min(
            SharedConfig.initialReconnectDelay * pow(2.0, Double(reconnectAttempt)),
            SharedConfig.maxReconnectDelay
        )
        reconnectAttempt += 1
        updateState(.waitingToReconnect(seconds: delay))

        let work = DispatchWorkItem { [weak self] in
            guard let self, !self.isStopped else { return }
            self.connect()
        }
        reconnectWorkItem = work
        queue.asyncAfter(deadline: .now() + delay, execute: work)
    }
    // MARK: - Sending

    /// Queue a JPEG frame for delivery. Safe to call from any thread.
    func send(jpeg: Data) {
        queue.async { [weak self] in
            guard let self, self.isReady, !self.isStopped else { return }
            self.sendRaw(WireProtocol.jpegFrame(jpeg))
        }
    }

    private func sendRaw(_ data: Data) {
        guard let conn = connection else { return }
        conn.send(
            content: data,
            completion: .contentProcessed { [weak self] error in
                guard let self, let error else { return }
                self.queue.async {
                    // Only react if this is still the live connection.
                    guard self.connection === conn else { return }
                    self.updateState(.failed(error.localizedDescription))
                    self.connection?.cancel()
                    self.connection = nil
                    self.isReady = false
                    self.didSendAuth = false
                    self.scheduleReconnect()
                }
            }
        )
    }

    private func updateState(_ state: State) {
        onStateChange?(state)
    }
}
