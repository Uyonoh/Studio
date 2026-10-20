"""T3.3 studio_media tests — image probing and thumbnail generation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image


def _create_test_image(path: Path, width: int = 100, height: int = 80) -> None:
    """Create a small PNG test image at the given path."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    img.save(path, format="PNG")


def test_probe_image_returns_correct_dimensions() -> None:
    """probe_image extracts width, height, and MIME type from a PNG."""
    from studio_media import probe_image

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.png"
        _create_test_image(p, 200, 150)
        meta = probe_image(p)
    assert meta.width == 200
    assert meta.height == 150
    assert meta.mime_type == "image/png"


def test_probe_image_raises_on_non_image() -> None:
    """probe_image raises MediaProbeError on a non-image file."""
    from studio_media import probe_image
    from studio_media.media import MediaProbeError

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "junk.txt"
        p.write_text("this is not an image")
        with pytest.raises(MediaProbeError):
            probe_image(p)


def test_make_thumbnail_creates_jpeg() -> None:
    """make_thumbnail creates a JPEG thumbnail from a PNG source."""
    from studio_media import make_thumbnail

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.png"
        dst = Path(tmp) / "thumb.jpg"
        _create_test_image(src, 1024, 768)
        make_thumbnail(src, dst)
        assert dst.exists()
        with Image.open(dst) as thumb:
            assert thumb.format == "JPEG"
            assert thumb.width <= 512
            assert thumb.height <= 512


def test_make_thumbnail_preserves_aspect_ratio() -> None:
    """Thumbnails preserve aspect ratio within the THUMBNAIL_SIZE box."""
    from studio_media import make_thumbnail

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "wide.png"
        dst = Path(tmp) / "wide_thumb.jpg"
        _create_test_image(src, 1000, 200)
        make_thumbnail(src, dst)
        with Image.open(dst) as thumb:
            # Width should be capped at 512; height proportionally scaled
            assert thumb.width == 512
            assert abs(thumb.height - 102) <= 2  # 200 * (512/1000) ≈ 102


def test_probe_video_raises_when_ffprobe_missing() -> None:
    """probe_video raises MediaProbeError if ffprobe is not installed."""
    from unittest.mock import patch

    from studio_media import probe_video
    from studio_media.media import MediaProbeError

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "fake.mp4"
        p.write_bytes(b"not a real video")
        with patch("subprocess.run", side_effect=FileNotFoundError("ffprobe not found")):
            with pytest.raises(MediaProbeError, match="ffprobe not found"):
                probe_video(p)
