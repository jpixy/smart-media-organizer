"""Type-safe media information parser using pymediainfo.

This module provides async media file analysis capabilities to extract
technical information like resolution, codecs, bitrates, and duration.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import aiofiles
from pymediainfo import MediaInfo
import structlog

from smart_media_organizer.models.media_file import (
    AudioCodec,
    MediaFile,
    MediaFileInfo,
    ProcessingStatus,
    VideoCodec,
    VideoFormat,
    VideoResolution,
)
from smart_media_organizer.utils.retry import retry_file_operation

logger = structlog.get_logger(__name__)


class MediaParserError(Exception):
    """Base exception for media parser errors."""


class UnsupportedFileError(MediaParserError):
    """File format not supported error."""


class CorruptedFileError(MediaParserError):
    """File appears to be corrupted error."""


class MediaInfoExtractor:
    """Type-safe wrapper around pymediainfo for extracting media information."""

    def __init__(self) -> None:
        """Initialize the media info extractor."""
        pass

    @retry_file_operation(max_attempts=2)
    async def extract_media_info(self, file_path: Path) -> MediaInfo:
        """Extract media info from file with retry logic.

        Args:
            file_path: Path to media file

        Returns:
            MediaInfo object

        Raises:
            UnsupportedFileError: If file format is not supported
            CorruptedFileError: If file appears to be corrupted
        """
        try:
            # Run pymediainfo in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            media_info = await loop.run_in_executor(
                None, MediaInfo.parse, str(file_path)
            )

            if not media_info.tracks:
                raise UnsupportedFileError(f"No media tracks found in {file_path}")

            logger.debug(
                "Media info extracted successfully",
                file_path=str(file_path),
                track_count=len(media_info.tracks),
            )

            return media_info

        except Exception as e:
            logger.error(
                "Error extracting media info",
                file_path=str(file_path),
                error=str(e),
            )

            if "corrupted" in str(e).lower() or "invalid" in str(e).lower():
                raise CorruptedFileError(
                    f"File appears to be corrupted: {file_path}"
                ) from e
            else:
                raise UnsupportedFileError(
                    f"Cannot extract media info from {file_path}: {e}"
                ) from e

    def _safe_get_track_value(
        self, track: Any, attribute: str, default: Any = None
    ) -> Any:
        """Safely get value from track with fallback."""
        try:
            value = getattr(track, attribute, default)
            return value if value is not None else default
        except (AttributeError, TypeError):
            return default

    def extract_video_info(self, media_info: MediaInfo) -> dict[str, Any]:
        """Extract video track information.

        Args:
            media_info: MediaInfo object

        Returns:
            Dictionary with video information
        """
        video_info = {
            "codec": VideoCodec.UNKNOWN,
            "resolution": VideoResolution.UNKNOWN,
            "width": None,
            "height": None,
            "bitrate": None,
            "fps": None,
            "bit_depth": None,
            "format": VideoFormat.UNKNOWN,
        }

        # Find first video track
        video_track = None
        for track in media_info.tracks:
            if track.track_type == "Video":
                video_track = track
                break

        if not video_track:
            logger.debug("No video track found in media file")
            return video_info

        # Extract codec
        codec_name = self._safe_get_track_value(video_track, "codec", "").lower()
        video_info["codec"] = self._parse_video_codec(codec_name)

        # Extract dimensions
        width = self._safe_get_track_value(video_track, "width")
        height = self._safe_get_track_value(video_track, "height")

        if width and height:
            video_info["width"] = int(width)
            video_info["height"] = int(height)
            video_info["resolution"] = self._parse_video_resolution(
                int(width), int(height)
            )

        # Extract bitrate
        bitrate = self._safe_get_track_value(video_track, "bit_rate")
        if bitrate:
            video_info["bitrate"] = int(bitrate)

        # Extract frame rate
        fps = self._safe_get_track_value(video_track, "frame_rate")
        if fps:
            video_info["fps"] = float(fps)

        # Extract bit depth
        bit_depth = self._safe_get_track_value(video_track, "bit_depth")
        if bit_depth:
            video_info["bit_depth"] = int(bit_depth)

        # Extract format from container or codec info
        format_info = self._safe_get_track_value(video_track, "format", "")
        video_info["format"] = self._parse_video_format(format_info)

        logger.debug(
            "Video info extracted",
            codec=video_info["codec"].value,
            resolution=video_info["resolution"].value,
            width=video_info["width"],
            height=video_info["height"],
        )

        return video_info

    def extract_audio_info(self, media_info: MediaInfo) -> dict[str, Any]:
        """Extract audio track information.

        Args:
            media_info: MediaInfo object

        Returns:
            Dictionary with audio information
        """
        audio_info = {
            "codec": AudioCodec.UNKNOWN,
            "channels": None,
            "sample_rate": None,
            "bitrate": None,
        }

        # Find first audio track
        audio_track = None
        for track in media_info.tracks:
            if track.track_type == "Audio":
                audio_track = track
                break

        if not audio_track:
            logger.debug("No audio track found in media file")
            return audio_info

        # Extract codec
        codec_name = self._safe_get_track_value(audio_track, "codec", "").lower()
        audio_info["codec"] = self._parse_audio_codec(codec_name)

        # Extract channels
        channels = self._safe_get_track_value(audio_track, "channel_s")
        if channels:
            audio_info["channels"] = int(channels)

        # Extract sample rate
        sample_rate = self._safe_get_track_value(audio_track, "sampling_rate")
        if sample_rate:
            audio_info["sample_rate"] = int(sample_rate)

        # Extract bitrate
        bitrate = self._safe_get_track_value(audio_track, "bit_rate")
        if bitrate:
            audio_info["bitrate"] = int(bitrate)

        logger.debug(
            "Audio info extracted",
            codec=audio_info["codec"].value,
            channels=audio_info["channels"],
            sample_rate=audio_info["sample_rate"],
        )

        return audio_info

    def extract_general_info(self, media_info: MediaInfo) -> dict[str, Any]:
        """Extract general file information.

        Args:
            media_info: MediaInfo object

        Returns:
            Dictionary with general information
        """
        general_info = {
            "duration": None,
            "file_size": None,
            "container": None,
        }

        # Find general track
        general_track = None
        for track in media_info.tracks:
            if track.track_type == "General":
                general_track = track
                break

        if not general_track:
            logger.debug("No general track found in media file")
            return general_info

        # Extract duration (in milliseconds, convert to seconds)
        duration = self._safe_get_track_value(general_track, "duration")
        if duration:
            general_info["duration"] = int(float(duration) / 1000)

        # Extract file size
        file_size = self._safe_get_track_value(general_track, "file_size")
        if file_size:
            general_info["file_size"] = int(file_size)

        # Extract container format
        container = self._safe_get_track_value(general_track, "format", "")
        general_info["container"] = container.lower() if container else "unknown"

        logger.debug(
            "General info extracted",
            duration=general_info["duration"],
            file_size=general_info["file_size"],
            container=general_info["container"],
        )

        return general_info

    def _parse_video_codec(self, codec_name: str) -> VideoCodec:
        """Parse video codec from string."""
        codec_name = codec_name.lower()

        if "h264" in codec_name or "avc" in codec_name:
            return VideoCodec.H264
        elif "h265" in codec_name or "hevc" in codec_name:
            return VideoCodec.H265
        elif "vp9" in codec_name:
            return VideoCodec.VP9
        elif "av1" in codec_name:
            return VideoCodec.AV1
        elif "xvid" in codec_name:
            return VideoCodec.XVID
        elif "divx" in codec_name:
            return VideoCodec.DIVX
        else:
            return VideoCodec.UNKNOWN

    def _parse_audio_codec(self, codec_name: str) -> AudioCodec:
        """Parse audio codec from string."""
        codec_name = codec_name.lower()

        if "aac" in codec_name:
            return AudioCodec.AAC
        elif "ac-3" in codec_name or "ac3" in codec_name:
            return AudioCodec.AC3
        elif "dts" in codec_name:
            if "hd" in codec_name or "master" in codec_name:
                return AudioCodec.DTS_HD
            else:
                return AudioCodec.DTS
        elif "truehd" in codec_name or "true hd" in codec_name:
            return AudioCodec.TRUEHD
        elif "flac" in codec_name:
            return AudioCodec.FLAC
        elif "mp3" in codec_name:
            return AudioCodec.MP3
        elif "pcm" in codec_name:
            return AudioCodec.PCM
        else:
            return AudioCodec.UNKNOWN

    def _parse_video_resolution(self, _width: int, height: int) -> VideoResolution:
        """Parse video resolution from dimensions."""
        if height <= 480:
            return VideoResolution.SD_480P
        elif height <= 720:
            return VideoResolution.HD_720P
        elif height <= 1080:
            return VideoResolution.FHD_1080P
        elif height <= 1440:
            return VideoResolution.QHD_1440P
        elif height <= 2160:
            return VideoResolution.UHD_4K
        elif height <= 4320:
            return VideoResolution.UHD_8K
        else:
            return VideoResolution.UNKNOWN

    def _parse_video_format(self, format_info: str) -> VideoFormat:
        """Parse video source format."""
        format_info = format_info.lower()

        if "bluray" in format_info or "blu-ray" in format_info:
            if "uhd" in format_info:
                return VideoFormat.UHD_BLURAY
            else:
                return VideoFormat.BLURAY
        elif "remux" in format_info:
            return VideoFormat.REMUX
        elif "web-dl" in format_info or "webdl" in format_info:
            return VideoFormat.WEB_DL
        elif "webrip" in format_info:
            return VideoFormat.WEBRIP
        elif "hdtv" in format_info:
            return VideoFormat.HDTV
        elif "dvdrip" in format_info:
            return VideoFormat.DVDRIP
        elif "cam" in format_info:
            return VideoFormat.CAM
        elif "telesync" in format_info or "ts" in format_info:
            return VideoFormat.TELESYNC
        else:
            return VideoFormat.UNKNOWN


class MediaFileParser:
    """High-level media file parser that updates MediaFile objects."""

    def __init__(self) -> None:
        """Initialize the media file parser."""
        self.extractor = MediaInfoExtractor()

    async def parse_media_file(self, media_file: MediaFile) -> MediaFile:
        """Parse media file and update with technical information.

        Args:
            media_file: MediaFile object to update

        Returns:
            Updated MediaFile object

        Raises:
            MediaParserError: If parsing fails
        """
        file_path = media_file.info.file_path

        logger.info("Starting media file parsing", file_path=str(file_path))

        try:
            # Update status
            media_file.update_status(ProcessingStatus.SCANNING)

            # Extract media information
            media_info = await self.extractor.extract_media_info(file_path)

            # Extract different types of information
            video_info = self.extractor.extract_video_info(media_info)
            audio_info = self.extractor.extract_audio_info(media_info)
            general_info = self.extractor.extract_general_info(media_info)

            # Update MediaFileInfo with extracted information
            media_file.info.duration_seconds = general_info.get("duration")
            media_file.info.video_codec = video_info["codec"]
            media_file.info.video_resolution = video_info["resolution"]
            media_file.info.video_width = video_info["width"]
            media_file.info.video_height = video_info["height"]
            media_file.info.video_bitrate = video_info["bitrate"]
            media_file.info.video_fps = video_info["fps"]
            media_file.info.bit_depth = video_info["bit_depth"]
            media_file.info.audio_codec = audio_info["codec"]
            media_file.info.audio_channels = audio_info["channels"]
            media_file.info.audio_sample_rate = audio_info["sample_rate"]
            media_file.info.audio_bitrate = audio_info["bitrate"]
            media_file.info.video_format = video_info["format"]

            # Update file size if not set
            if general_info.get("file_size") and not media_file.info.file_size:
                media_file.info.file_size = general_info["file_size"]

            # Mark as completed
            media_file.update_status(ProcessingStatus.COMPLETED)

            logger.info(
                "Media file parsing completed",
                file_path=str(file_path),
                duration=media_file.info.duration_seconds,
                resolution=f"{media_file.info.video_width}x{media_file.info.video_height}",
                video_codec=media_file.info.video_codec.value,
                audio_codec=media_file.info.audio_codec.value,
            )

            return media_file

        except Exception as e:
            error_msg = f"Failed to parse media file: {e}"
            media_file.update_status(ProcessingStatus.FAILED, error_msg)

            logger.error(
                "Media file parsing failed",
                file_path=str(file_path),
                error=str(e),
                exc_info=True,
            )

            raise MediaParserError(error_msg) from e

    async def verify_file_integrity(self, file_path: Path) -> bool:
        """Verify file integrity by attempting to parse it.

        Args:
            file_path: Path to file to verify

        Returns:
            True if file appears to be valid, False otherwise
        """
        try:
            media_info = await self.extractor.extract_media_info(file_path)

            # Basic integrity checks
            has_tracks = len(media_info.tracks) > 0
            has_duration = False

            for track in media_info.tracks:
                if track.track_type == "General":
                    duration = getattr(track, "duration", None)
                    if duration and float(duration) > 0:
                        has_duration = True
                        break

            is_valid = has_tracks and has_duration

            logger.debug(
                "File integrity check",
                file_path=str(file_path),
                valid=is_valid,
                tracks=len(media_info.tracks),
                has_duration=has_duration,
            )

            return is_valid

        except Exception as e:
            logger.warning(
                "File integrity check failed",
                file_path=str(file_path),
                error=str(e),
            )
            return False

    async def calculate_file_hash(self, file_path: Path, algorithm: str = "md5") -> str:
        """Calculate file hash for integrity verification.

        Args:
            file_path: Path to file
            algorithm: Hash algorithm to use

        Returns:
            Hexadecimal hash string
        """
        hash_obj = hashlib.new(algorithm)

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()


# Convenience functions
async def parse_media_file(file_path: Path) -> MediaFile:
    """Convenience function to parse a single media file.

    Args:
        file_path: Path to media file

    Returns:
        Parsed MediaFile object
    """
    from smart_media_organizer.utils.file_ops import get_file_info

    # Create basic MediaFile
    file_info_dict = await get_file_info(file_path)
    media_file_info = MediaFileInfo(
        file_path=file_path,
        file_size=file_info_dict["size"],
        file_extension=file_path.suffix.lower(),
    )

    media_file = MediaFile(info=media_file_info)

    # Parse and return
    parser = MediaFileParser()
    return await parser.parse_media_file(media_file)


async def verify_media_files(file_paths: list[Path]) -> dict[Path, bool]:
    """Verify integrity of multiple media files.

    Args:
        file_paths: List of file paths to verify

    Returns:
        Dictionary mapping file paths to verification results
    """
    parser = MediaFileParser()
    results = {}

    # Verify files concurrently
    tasks = []
    for file_path in file_paths:
        task = asyncio.create_task(parser.verify_file_integrity(file_path))
        tasks.append((file_path, task))

    for file_path, task in tasks:
        try:
            results[file_path] = await task
        except Exception:
            results[file_path] = False

    return results
