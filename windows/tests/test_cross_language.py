"""Cross-language check: the Swift encoder must match this one byte-for-byte.

``swift_encode_reference`` below is a line-by-line port of
``ios/Shared/WireProtocol.swift``. If these two ever disagree, the iPhone
will send frames the PC cannot parse. Run this test after any change to
either implementation.
"""

from __future__ import annotations

import struct

from receiver.protocol import FrameType, encode_frame, encode_jpeg


def swift_encode_reference(frame_type: int, payload: bytes) -> bytes:
    """Port of Swift's ``WireProtocol.encode(type:payload:)``."""
    magic = list(b"MLB1")
    out = bytearray()
    out.extend(magic)
    out.append(frame_type & 0xFF)
    # Swift writes UInt32 bigEndian, i.e. struct.pack(">I", ...).
    out.extend(struct.pack(">I", len(payload)))
    out.extend(payload)
    return bytes(out)


def swift_auth_reference(token: str) -> bytes:
    return swift_encode_reference(0x01, token.encode("utf-8"))


def swift_jpeg_reference(jpeg: bytes) -> bytes:
    return swift_encode_reference(0x02, jpeg)


def test_swift_and_python_encoders_match():
    for payload in [b"", b"\x00", b"hello world", bytes(range(256))]:
        assert swift_encode_reference(FrameType.FRAME, payload) == (
            encode_frame(FrameType.FRAME, payload)
        )


def test_swift_auth_matches():
    for token in ["", "t", "mlbb-phase1", "unicode-éè"]:
        assert swift_auth_reference(token) == encode_frame(
            FrameType.AUTH, token.encode("utf-8")
        )


def test_swift_jpeg_matches():
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 500
    assert swift_jpeg_reference(jpeg) == encode_jpeg(jpeg)


def test_header_layout_matches_swift_expectations():
    raw = swift_jpeg_reference(b"abc")
    assert raw[0:4] == b"MLB1"
    assert raw[4] == 0x02
    assert raw[5:9] == b"\x00\x00\x00\x03"
    assert raw[9:] == b"abc"
