"""Media file data models using Pydantic.

This module defines the core data structures for representing
media files and their technical information.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field


class VideoCodec(str, Enum):
    """Video codec enumeration."""

    H264 = "h264"
    H265 = "h265"
    HEVC = "hevc"
    AVC = "avc"
    VP9 = "vp9"
    AV1 = "av1"
    XVID = "xvid"
    DIVX = "divx"
    UNKNOWN = "unknown"


class AudioCodec(str, Enum):
    """Audio codec enumeration."""

    AAC = "aac"
    AC3 = "ac3"
    DTS = "dts"
    DTS_HD = "dts-hd"
    TRUEHD = "truehd"
    FLAC = "flac"
    MP3 = "mp3"
    PCM = "pcm"
    UNKNOWN = "unknown"


class VideoResolution(str, Enum):
    """Video resolution enumeration."""

    SD_480P = "480p"
    HD_720P = "720p"
    FHD_1080P = "1080p"
    QHD_1440P = "1440p"
    UHD_4K = "2160p"
    UHD_8K = "4320p"
    UNKNOWN = "unknown"


class VideoFormat(str, Enum):
    """Video source format enumeration."""

    BLURAY = "BluRay"
    UHD_BLURAY = "UHD.BluRay"
    REMUX = "REMUX"
    WEB_DL = "WEB-DL"
    WEBRIP = "WEBRip"
    HDTV = "HDTV"
    DVDRIP = "DVDRip"
    CAM = "CAM"
    TELESYNC = "TELESYNC"
    UNKNOWN = "unknown"


class MediaFileInfo(BaseModel):
    """Technical information about a media file."""

    # File information
    file_path: Path = Field(..., description="Full path to the media file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    file_extension: str = Field(..., description="File extension")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    modified_at: datetime | None = Field(
        default=None, description="Last modification time"
    )

    # Video information
    duration_seconds: int | None = Field(
        default=None, ge=0, description="Duration in seconds"
    )
    video_codec: VideoCodec = Field(
        default=VideoCodec.UNKNOWN, description="Video codec"
    )
    video_resolution: VideoResolution = Field(
        default=VideoResolution.UNKNOWN, description="Video resolution"
    )
    video_width: int | None = Field(
        default=None, ge=0, description="Video width in pixels"
    )
    video_height: int | None = Field(
        default=None, ge=0, description="Video height in pixels"
    )
    video_bitrate: int | None = Field(
        default=None, ge=0, description="Video bitrate in bps"
    )
    video_fps: float | None = Field(default=None, ge=0, description="Frames per second")
    bit_depth: int | None = Field(default=None, ge=0, description="Video bit depth")

    # Audio information
    audio_codec: AudioCodec = Field(
        default=AudioCodec.UNKNOWN, description="Audio codec"
    )
    audio_channels: int | None = Field(
        default=None, ge=0, description="Number of audio channels"
    )
    audio_sample_rate: int | None = Field(
        default=None, ge=0, description="Audio sample rate in Hz"
    )
    audio_bitrate: int | None = Field(
        default=None, ge=0, description="Audio bitrate in bps"
    )

    # Source information
    video_format: VideoFormat = Field(
        default=VideoFormat.UNKNOWN, description="Video source format"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {Path: str, datetime: lambda v: v.isoformat()}

    @computed_field  # type: ignore
    @property
    def filename(self) -> str:
        """Get the filename without path."""
        return self.file_path.name

    @computed_field  # type: ignore
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)

    @computed_field  # type: ignore
    @property
    def file_size_gb(self) -> float:
        """Get file size in gigabytes."""
        return self.file_size / (1024 * 1024 * 1024)

    @computed_field  # type: ignore
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string (HH:MM:SS)."""
        if self.duration_seconds is None:
            return "Unknown"

        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @computed_field  # type: ignore
    @property
    def resolution_display(self) -> str:
        """Get display-friendly resolution string."""
        if self.video_width and self.video_height:
            return f"{self.video_width}x{self.video_height}"
        return self.video_resolution.value

    @computed_field  # type: ignore
    @property
    def audio_channels_display(self) -> str:
        """Get display-friendly audio channels string."""
        if self.audio_channels is None:
            return "Unknown"

        channel_map = {
            1: "1.0 (Mono)",
            2: "2.0 (Stereo)",
            6: "5.1 (Surround)",
            8: "7.1 (Surround)",
        }

        return channel_map.get(self.audio_channels, f"{self.audio_channels}.0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with computed fields."""
        data = self.model_dump()
        # Add computed fields
        data.update(
            {
                "filename": self.filename,
                "file_size_mb": self.file_size_mb,
                "file_size_gb": self.file_size_gb,
                "duration_formatted": self.duration_formatted,
                "resolution_display": self.resolution_display,
                "audio_channels_display": self.audio_channels_display,
            }
        )
        return data


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""

    PENDING = "pending"
    SCANNING = "scanning"
    IDENTIFYING = "identifying"
    FETCHING_METADATA = "fetching_metadata"
    ORGANIZING = "organizing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MediaFile(BaseModel):
    """Complete media file representation with processing status."""

    # Core file information
    info: MediaFileInfo = Field(..., description="Technical file information")

    # Processing information
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING, description="Current processing status"
    )
    error_message: str | None = Field(
        default=None, description="Error message if processing failed"
    )
    processed_at: datetime | None = Field(
        default=None, description="When processing completed"
    )

    # AI identification results (will be populated by AI identifier)
    ai_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="AI identification confidence score"
    )
    ai_raw_response: dict[str, Any] | None = Field(
        default=None, description="Raw AI response for debugging"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {Path: str, datetime: lambda v: v.isoformat()}

    @computed_field  # type: ignore
    @property
    def is_processed(self) -> bool:
        """Check if file has been successfully processed."""
        return self.processing_status == ProcessingStatus.COMPLETED

    @computed_field  # type: ignore
    @property
    def has_error(self) -> bool:
        """Check if file processing encountered an error."""
        return self.processing_status == ProcessingStatus.FAILED

    @computed_field  # type: ignore
    @property
    def file_path(self) -> Path:
        """Get file path for convenience."""
        return self.info.file_path

    @computed_field  # type: ignore
    @property
    def filename(self) -> str:
        """Get filename for convenience."""
        return self.info.filename

    def update_status(self, status: ProcessingStatus, error: str | None = None) -> None:
        """Update processing status and timestamp."""
        self.processing_status = status
        self.error_message = error
        if status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
            self.processed_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with computed fields."""
        data = self.model_dump()
        # Add computed fields
        data.update(
            {
                "is_processed": self.is_processed,
                "has_error": self.has_error,
                "file_path": str(self.file_path),
                "filename": self.filename,
            }
        )
        return data
