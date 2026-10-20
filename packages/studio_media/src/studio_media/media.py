"""Media utilities: image probing via Pillow, video probing via ffprobe,
thumbnail generation, and video poster-frame extraction.

Requirements:
  - ``Pillow`` (already a project dependency)
  - ``ffmpeg``/``ffprobe`` installed in the OS PATH (Docker images include these)

All public functions raise ``MediaProbeError`` on unrecognisable or corrupt media.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (512, 512)
SUPPORTED_IMAGE_MIME_PREFIXES = ("image/",)
SUPPORTED_VIDEO_MIME_PREFIXES = ("video/",)


class MediaProbeError(Exception):
    """Raised when a media file cannot be identified or probed."""


@dataclass
class ImageMetadata:
    """Dimensions and MIME type extracted from an image file."""

    width: int
    height: int
    mime_type: str


@dataclass
class VideoMetadata:
    """Dimensions, duration, FPS, and MIME type extracted from a video file."""

    width: int
    height: int
    duration_ms: int
    fps: Decimal
    mime_type: str


def probe_image(path: Path | str) -> ImageMetadata:
    """Open an image with Pillow and return its metadata.

    Args:
        path: Filesystem path to the image file.

    Returns:
        ``ImageMetadata`` with width, height, and MIME type.

    Raises:
        ``MediaProbeError`` if the file cannot be identified as an image.
    """
    path = Path(path)
    try:
        with Image.open(path) as img:
            img.verify()  # detect truncated files
        # Re-open after verify (verify closes the file internally on some backends)
        with Image.open(path) as img:
            width, height = img.size
            fmt = (img.format or "").lower()
            # Map Pillow format names to MIME types
            _fmt_to_mime = {
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
                "bmp": "image/bmp",
                "tiff": "image/tiff",
            }
            mime_type = _fmt_to_mime.get(fmt, f"image/{fmt}" if fmt else "image/octet-stream")
        return ImageMetadata(width=width, height=height, mime_type=mime_type)
    except UnidentifiedImageError as exc:
        raise MediaProbeError(f"Cannot identify image file: {path}") from exc
    except Exception as exc:
        raise MediaProbeError(f"Failed to probe image {path}: {exc}") from exc


def probe_video(path: Path | str) -> VideoMetadata:
    """Use ffprobe to extract video metadata.

    Args:
        path: Filesystem path to the video file.

    Returns:
        ``VideoMetadata`` with width, height, duration, FPS, and MIME type.

    Raises:
        ``MediaProbeError`` if ffprobe is not found or the file is not a valid video.
    """
    path = Path(path)
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    except FileNotFoundError as exc:
        raise MediaProbeError("ffprobe not found; install ffmpeg on this system") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaProbeError(f"ffprobe exited with error for {path}: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"ffprobe timed out probing {path}") from exc

    try:
        probe = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError(f"ffprobe returned invalid JSON for {path}") from exc

    # Find the first video stream
    video_stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise MediaProbeError(f"No video stream found in {path}")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if not width or not height:
        raise MediaProbeError(f"Could not determine video dimensions for {path}")

    # FPS from avg_frame_rate field (e.g. "30/1" or "25/1")
    fps_raw = video_stream.get("avg_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = Decimal(num) / Decimal(den) if int(den) else Decimal("0")
    except (ValueError, ZeroDivisionError):
        fps = Decimal("0")

    # Duration in milliseconds from the format block
    duration_s = float(probe.get("format", {}).get("duration", "0") or "0")
    duration_ms = int(duration_s * 1000)

    # Best-effort MIME from format name
    fmt_name = probe.get("format", {}).get("format_name", "")
    _fmt_to_mime = {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
    }
    mime_type = next(
        (mime for key, mime in _fmt_to_mime.items() if key in fmt_name),
        "video/mp4",
    )

    return VideoMetadata(
        width=width,
        height=height,
        duration_ms=duration_ms,
        fps=fps,
        mime_type=mime_type,
    )


def make_thumbnail(src: Path | str, dst: Path | str) -> None:
    """Generate a JPEG thumbnail from an image file.

    Resizes the image to fit within ``THUMBNAIL_SIZE`` while preserving aspect
    ratio, then saves as JPEG.

    Args:
        src: Source image path.
        dst: Destination JPEG path (created or overwritten).

    Raises:
        ``MediaProbeError`` if the source cannot be opened.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src) as img:
            rgb_img = img.convert("RGB")
            rgb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            rgb_img.save(dst, format="JPEG", quality=85, optimize=True)
    except UnidentifiedImageError as exc:
        raise MediaProbeError(f"Cannot open image for thumbnail: {src}") from exc
    except Exception as exc:
        raise MediaProbeError(f"Failed to create thumbnail for {src}: {exc}") from exc


def make_poster_frame(src: Path | str, dst: Path | str, time_s: float = 0.0) -> None:
    """Extract a single frame from a video and save it as a JPEG poster image.

    Args:
        src: Source video file path.
        dst: Destination JPEG path.
        time_s: Timestamp in seconds to extract (default: first frame).

    Raises:
        ``MediaProbeError`` if ffmpeg is not found or the extraction fails.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-ss", str(time_s),
        "-i", str(src),
        "-frames:v", "1",
        "-q:v", "2",
        "-vf", f"scale='min({THUMBNAIL_SIZE[0]},iw)':-2",
        str(dst),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    except FileNotFoundError as exc:
        raise MediaProbeError("ffmpeg not found; install ffmpeg on this system") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaProbeError(
            f"ffmpeg failed to extract poster frame from {src}: {exc.stderr}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"ffmpeg timed out extracting poster frame from {src}") from exc
