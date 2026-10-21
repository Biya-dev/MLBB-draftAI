import Foundation

/// Swift mirror of the Python `receiver.protocol` module.
///
/// Frame layout (big-endian):
///
///     +--------+--------+---------+-----------------------+
///     | magic  | type   | length  | payload               |
///     | 4 B    | 1 B    | 4 B     | `length` bytes        |
///     +--------+--------+---------+-----------------------+
///
/// The magic lets the receiver resynchronise, and the length prefix means
/// a partial frame can never be mistaken for a complete one.
enum WireProtocol {

    static let magic: [UInt8] = Array("MLB1".utf8)
    static let headerSize = 9
    static let maxPayload = 4 * 1024 * 1024

    enum FrameType: UInt8 {
        case auth = 0x01
        case frame = 0x02
    }

    /// Build a complete wire frame.
    static func encode(type: FrameType, payload: Data) -> Data {
        var out = Data(capacity: headerSize + payload.count)
        out.append(contentsOf: magic)
        out.append(type.rawValue)
        let length = UInt32(payload.count).bigEndian
        withUnsafeBytes(of: length) { out.append(contentsOf: $0) }
        out.append(payload)
        return out
    }

    static func authFrame(token: String) -> Data {
        encode(type: .auth, payload: Data(token.utf8))
    }

    static func jpegFrame(_ jpeg: Data) -> Data {
        encode(type: .frame, payload: jpeg)
    }

    /// Incremental decoder. Feed it bytes; it returns complete frames.
    final class Decoder {
        private var buffer = Data()

        func feed(_ chunk: Data) -> [(FrameType, Data)] {
            buffer.append(chunk)
            var frames: [(FrameType, Data)] = []
            while buffer.count >= headerSize {
                // NOTE: `buffer` is a Data whose startIndex is NOT
                // necessarily 0 (removeFirst keeps the original indices),
                // so every access must be relative to buffer.startIndex.
                let base = buffer.startIndex
                guard buffer[base..<(base + 4)] == Data(magic) else { break }
                let typeByte = buffer[base + 4]
                let length: UInt32 = buffer[(base + 5)..<(base + 9)].reduce(0) {
                    ($0 << 8) | UInt32($1)
                }
                guard length <= maxPayload else { break }
                let total = headerSize + Int(length)
                guard buffer.count >= total else { break }
                let payload = Data(buffer[(base + headerSize)..<(base + total)])
                buffer.removeFirst(total)
                if let type = FrameType(rawValue: typeByte) {
                    frames.append((type, payload))
                }
            }
            return frames
        }
    }
}
