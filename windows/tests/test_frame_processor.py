"""Tests for the OpenCV frame processor."""

from __future__ import annotations

import numpy as np
import pytest

from receiver.frame_processor import FrameProcessor


def make_jpeg(width: int = 640, height: int = 360, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    import cv2

    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return bytes(buf)


def test_decode_returns_bgr_image():
    proc = FrameProcessor()
    img = proc.decode(make_jpeg(320, 240))
    assert img.shape == (240, 320, 3)


def test_decode_rejects_garbage():
    proc = FrameProcessor()
    with pytest.raises(ValueError):
        proc.decode(b"not a jpeg at all")


def test_decode_rejects_empty():
    proc = FrameProcessor()
    with pytest.raises(ValueError):
        proc.decode(b"")


def test_resize_downscales_to_max_width():
    proc = FrameProcessor(max_width=320)
    img = proc.decode(make_jpeg(1280, 720))
    out = proc.resize(img)
    assert out.shape[1] == 320
    assert out.shape[0] == 180  # 720 * (320/1280)


def test_resize_does_not_upscale():
    proc = FrameProcessor(max_width=1280)
    img = proc.decode(make_jpeg(320, 240))
    out = proc.resize(img)
    assert out.shape == (240, 320, 3)


def test_process_returns_encoded_jpeg():
    proc = FrameProcessor()
    result = proc.process(make_jpeg(640, 360))
    assert result.ok
    assert result.jpeg is not None
    assert result.jpeg[:2] == b"\xff\xd8"
    assert result.image is not None


def test_process_handles_corrupt_jpeg_without_raising():
    proc = FrameProcessor()
    result = proc.process(b"\x00\x01\x02corrupt")
    assert result.ok is False
    assert result.jpeg is None
    assert result.error and "ValueError" in result.error


def test_process_scales_down_large_frame():
    proc = FrameProcessor(max_width=640)
    result = proc.process(make_jpeg(2532, 1170))
    assert result.ok
    assert result.image is not None
    assert result.image.shape[1] == 640


def test_processing_time_is_recorded():
    proc = FrameProcessor()
    result = proc.process(make_jpeg(640, 360))
    assert result.processing_ms >= 0.0


def test_invalid_max_width_rejected():
    with pytest.raises(ValueError):
        FrameProcessor(max_width=4)


def test_jpeg_quality_is_clamped():
    proc = FrameProcessor(jpeg_quality=500)
    assert proc.jpeg_quality == 100
    proc = FrameProcessor(jpeg_quality=0)
    assert proc.jpeg_quality == 1
