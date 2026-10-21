"""Tests for the wire protocol codec."""

from __future__ import annotations

import pytest

from receiver.protocol import (
    HEADER_SIZE,
    MAX_PAYLOAD,
    FrameDecoder,
    FrameType,
    ProtocolError,
    decode_header,
    encode_auth,
    encode_frame,
    encode_jpeg,
)


def test_header_is_nine_bytes():
    assert HEADER_SIZE == 9


def test_encode_jpeg_roundtrip():
    payload = b"\xff\xd8\xff\xe0fakejpeg"
    raw = encode_jpeg(payload)
    frame_type, length = decode_header(raw[:HEADER_SIZE])
    assert frame_type == FrameType.FRAME
    assert length == len(payload)
    assert raw[HEADER_SIZE:] == payload


def test_encode_auth_roundtrip():
    raw = encode_auth("hunter2")
    frame_type, length = decode_header(raw[:HEADER_SIZE])
    assert frame_type == FrameType.AUTH
    assert raw[HEADER_SIZE:].decode("utf-8") == "hunter2"
    assert length == 7


def test_decode_header_rejects_bad_magic():
    bad = b"XXXX" + b"\x02" + b"\x00\x00\x00\x00"
    with pytest.raises(ProtocolError):
        decode_header(bad)


def test_decode_header_rejects_short_header():
    with pytest.raises(ProtocolError):
        decode_header(b"MLB1")


def test_encode_rejects_oversized_payload():
    with pytest.raises(ProtocolError):
        encode_frame(FrameType.FRAME, b"x" * (MAX_PAYLOAD + 1))


def test_decoder_reassembles_split_frame():
    raw = encode_jpeg(b"hello world")
    dec = FrameDecoder()
    assert dec.feed(raw[:5]) == []
    assert dec.feed(raw[5:12]) == []
    frames = dec.feed(raw[12:])
    assert frames == [(FrameType.FRAME, b"hello world")]


def test_decoder_handles_multiple_frames_in_one_chunk():
    chunk = encode_auth("t") + encode_jpeg(b"a") + encode_jpeg(b"bb")
    frames = FrameDecoder().feed(chunk)
    assert frames == [
        (FrameType.AUTH, b"t"),
        (FrameType.FRAME, b"a"),
        (FrameType.FRAME, b"bb"),
    ]


def test_decoder_preserves_large_payload():
    payload = bytes(range(256)) * 400  # 102_400 bytes
    frames = FrameDecoder().feed(encode_jpeg(payload))
    assert frames[0][1] == payload


def test_decoder_rejects_bad_magic_in_stream():
    with pytest.raises(ProtocolError):
        FrameDecoder().feed(b"XXXX\x02\x00\x00\x00\x00")


def test_decoder_rejects_oversized_length():
    bad = b"MLB1\x02\xff\xff\xff\xff"
    with pytest.raises(ProtocolError):
        FrameDecoder().feed(bad)


def test_byte_at_a_time_delivery():
    raw = encode_auth("tok") + encode_jpeg(b"payload")
    dec = FrameDecoder()
    out = []
    for i in range(len(raw)):
        out.extend(dec.feed(raw[i : i + 1]))
    assert out == [
        (FrameType.AUTH, b"tok"),
        (FrameType.FRAME, b"payload"),
    ]
