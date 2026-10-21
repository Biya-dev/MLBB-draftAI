/// Unit tests for the Swift wire protocol.
///
/// These mirror `windows/tests/test_protocol.py` exactly so both sides of
/// the wire format are proven to agree.
///
/// NOTE: these tests require Xcode (and therefore macOS) to run. They are
/// included for completeness but cannot be executed on Windows.
import XCTest

final class WireProtocolTests: XCTestCase {

    func testHeaderIsNineBytes() {
        XCTAssertEqual(WireProtocol.headerSize, 9)
    }

    func testJPEGFrameRoundTrip() {
        let payload = Data([0xFF, 0xD8, 0xFF, 0xE0, 0x01, 0x02])
        let raw = WireProtocol.jpegFrame(payload)

        XCTAssertEqual(raw.count, WireProtocol.headerSize + payload.count)
        XCTAssertEqual(Array(raw.prefix(4)), WireProtocol.magic)
        XCTAssertEqual(raw[4], WireProtocol.FrameType.frame.rawValue)

        // Length is big-endian.
        let length = raw[5..<9].reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
        XCTAssertEqual(length, UInt32(payload.count))
        XCTAssertEqual(Data(raw.dropFirst(WireProtocol.headerSize)), payload)
    }

    func testAuthFrameCarriesToken() {
        let raw = WireProtocol.authFrame(token: "hunter2")
        XCTAssertEqual(raw[4], WireProtocol.FrameType.auth.rawValue)
        let payload = String(data: Data(raw.dropFirst(WireProtocol.headerSize)),
                             encoding: .utf8)
        XCTAssertEqual(payload, "hunter2")
    }

    func testDecoderReassemblesSplitFrame() {
        let raw = WireProtocol.jpegFrame(Data("hello world".utf8))
        let decoder = WireProtocol.Decoder()

        XCTAssertTrue(decoder.feed(raw.prefix(5)).isEmpty)
        XCTAssertTrue(decoder.feed(raw[5..<12]).isEmpty)

        let frames = decoder.feed(raw[12...])
        XCTAssertEqual(frames.count, 1)
        XCTAssertEqual(frames[0].0, .frame)
        XCTAssertEqual(frames[0].1, Data("hello world".utf8))
    }

    func testDecoderHandlesMultipleFramesInOneChunk() {
        var chunk = WireProtocol.authFrame(token: "t")
        chunk.append(WireProtocol.jpegFrame(Data("a".utf8)))
        chunk.append(WireProtocol.jpegFrame(Data("bb".utf8)))

        let frames = WireProtocol.Decoder().feed(chunk)
        XCTAssertEqual(frames.count, 3)
        XCTAssertEqual(frames[0].0, .auth)
        XCTAssertEqual(frames[1].1, Data("a".utf8))
        XCTAssertEqual(frames[2].1, Data("bb".utf8))
    }

    func testDecoderByteAtATimeDelivery() {
        var raw = WireProtocol.authFrame(token: "tok")
        raw.append(WireProtocol.jpegFrame(Data("payload".utf8)))

        let decoder = WireProtocol.Decoder()
        var frames: [(WireProtocol.FrameType, Data)] = []
        for index in raw.indices {
            frames.append(contentsOf: decoder.feed(raw[index...index]))
        }
        XCTAssertEqual(frames.count, 2)
        XCTAssertEqual(frames[0].1, Data("tok".utf8))
        XCTAssertEqual(frames[1].1, Data("payload".utf8))
    }

    func testDecoderIgnoresUnknownFrameType() {
        // Type byte 0x7F is not a defined frame type.
        let raw = WireProtocol.encode(type: .frame, payload: Data())
        var bad = raw
        bad[4] = 0x7F
        let frames = WireProtocol.Decoder().feed(bad)
        XCTAssertTrue(frames.isEmpty)
    }

    func testEmptyPayloadIsValid() {
        let raw = WireProtocol.jpegFrame(Data())
        let frames = WireProtocol.Decoder().feed(raw)
        XCTAssertEqual(frames.count, 1)
        XCTAssertEqual(frames[0].1.count, 0)
    }
}
