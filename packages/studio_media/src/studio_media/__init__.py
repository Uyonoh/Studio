"""Studio Media package — image/video probing, thumbnails, and poster frames.

Public API:
  probe_image(path)        -> ImageMetadata
  probe_video(path)        -> VideoMetadata
  make_thumbnail(src, dst) -> None
  make_poster_frame(src, dst) -> None
"""

from studio_media.media import (
    ImageMetadata,
    VideoMetadata,
    make_poster_frame,
    make_thumbnail,
    probe_image,
    probe_video,
)

__version__ = "0.1.0"

__all__ = [
    "ImageMetadata",
    "VideoMetadata",
    "make_poster_frame",
    "make_thumbnail",
    "probe_image",
    "probe_video",
]
