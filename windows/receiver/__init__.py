"""MLBB Draft AI - Phase 1 local screen receiver."""

from .app import ReceiverApp
from .frame_processor import FrameProcessor
from .hub import FrameHub, LinkState
from .protocol import (
    FrameDecoder,
    FrameType,
    ProtocolError,
    decode_header,
    encode_auth,
    encode_frame,
    encode_jpeg,
)
from .server import FrameServer

__all__ = [
    "ReceiverApp",
    "FrameProcessor",
    "FrameHub",
    "LinkState",
    "FrameDecoder",
    "FrameType",
    "ProtocolError",
    "decode_header",
    "encode_auth",
    "encode_frame",
    "encode_jpeg",
    "FrameServer",
]

__version__ = "1.0.0"
