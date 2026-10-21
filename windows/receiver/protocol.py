"""Wire protocol shared by the iOS sender and the Windows receiver.

Frame layout (all big-endian):

    +--------+--------+-----------------+-----------------------+
    | magic  | type   | length          | payload               |
    | 4 B    | 1 B    | 4 B (uint32)    | `length` bytes        |
    +--------+--------+-----------------+-----------------------+

Types:
    0x01 AUTH  - payload is the UTF-8 shared token (sent once, first frame).
    0x02 FRAME - payload is a JPEG-encoded image.

Length-prefixed framing means the receiver can always resynchronise on the
magic bytes, so a dropped byte cannot corrupt the whole stream.
"""

from __future__ import annotations

import struct
from enum import IntEnum

MAGIC = b"MLB1"
HEADER = struct.Struct("!4sBI")
HEADER_SIZE = HEADER.size  # 9 bytes

#: Hard cap on a single payload (4 MiB). Protects the receiver against a
#: malformed or hostile length field allocating unbounded memory.
MAX_PAYLOAD = 4 * 1024 * 1024


class ProtocolError(Exception):
    """Raised when bytes on the wire violate the frame format."""


class FrameType(IntEnum):
    AUTH = 0x01
    FRAME = 0x02


def encode_frame(frame_type: FrameType | int, payload: bytes) -> bytes:
    """Build a single wire frame."""
    if not 0 <= int(frame_type) <= 0xFF:
        raise ProtocolError(f"frame type out of range: {frame_type!r}")
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(
            f"payload too large: {len(payload)} bytes (max {MAX_PAYLOAD})"
        )
    return HEADER.pack(MAGIC, int(frame_type), len(payload)) + payload


def decode_header(header: bytes) -> tuple[int, int]:
    """Decode a 9-byte header into ``(frame_type, payload_length)``."""
    if len(header) != HEADER_SIZE:
        raise ProtocolError(
            f"header must be {HEADER_SIZE} bytes, got {len(header)}"
        )
    magic, frame_type, length = HEADER.unpack(header)
    if magic != MAGIC:
        raise ProtocolError(f"bad magic: {magic!r}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"payload length {length} exceeds max {MAX_PAYLOAD}")
    return frame_type, length


def encode_auth(token: str) -> bytes:
    """Encode the AUTH frame carrying the shared token."""
    return encode_frame(FrameType.AUTH, token.encode("utf-8"))


def encode_jpeg(jpeg_bytes: bytes) -> bytes:
    """Encode a FRAME frame carrying JPEG data."""
    return encode_frame(FrameType.FRAME, jpeg_bytes)


class FrameDecoder:
    """Incremental decoder: feed it arbitrary chunks, get back whole frames."""

    def __init__(self, max_payload: int = MAX_PAYLOAD) -> None:
        self._buffer = bytearray()
        self._max_payload = max_payload

    def feed(self, chunk: bytes) -> list[tuple[int, bytes]]:
        """Append ``chunk`` and return every complete frame it completed."""
        self._buffer.extend(chunk)
        frames: list[tuple[int, bytes]] = []
        while True:
            if len(self._buffer) < HEADER_SIZE:
                break
            magic, frame_type, length = HEADER.unpack_from(self._buffer, 0)
            if magic != MAGIC:
                raise ProtocolError(f"bad magic: {magic!r}")
            if length > self._max_payload:
                raise ProtocolError(
                    f"payload length {length} exceeds max {self._max_payload}"
                )
            total = HEADER_SIZE + length
            if len(self._buffer) < total:
                break
            payload = bytes(self._buffer[HEADER_SIZE:total])
            del self._buffer[:total]
            frames.append((frame_type, payload))
        return frames
