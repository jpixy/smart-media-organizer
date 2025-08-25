"""Unit tests for the media parser.

This module tests the MediaFileParser and MediaInfoExtractor components.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from smart_media_organizer.models.media_file import (
    AudioCodec,
    ProcessingStatus,
    VideoCodec,
    VideoFormat,
    VideoResolution,
)
from smart_media_organizer.services.media_parser import (
    CorruptedFileError,
    MediaFileParser,
    MediaInfoExtractor,
    MediaParserError,
    UnsupportedFileError,
    parse_media_file,
    verify_media_files,
)


class TestMediaInfoExtractor:
    """Test the MediaInfoExtractor class."""

    def test_extractor_initialization(self) -> None:
        """Test extractor initialization."""
        extractor = MediaInfoExtractor()
        assert extractor is not None

    def test_safe_get_track_value(self) -> None:
        """Test safe track value retrieval."""
        extractor = MediaInfoExtractor()

        # Mock track with some attributes
        mock_track = Mock()
        mock_track.width = 1920
        mock_track.height = 1080

        # Test successful retrieval
        assert extractor._safe_get_track_value(mock_track, "width") == 1920
        assert extractor._safe_get_track_value(mock_track, "height") == 1080

        # Test missing attribute with default
        assert (
            extractor._safe_get_track_value(mock_track, "missing", "default")
            == "default"
        )

        # Test missing attribute without default
        assert extractor._safe_get_track_value(mock_track, "missing") is None

    def test_parse_video_codec(self) -> None:
        """Test video codec parsing."""
        extractor = MediaInfoExtractor()

        test_cases = [
            ("h264", VideoCodec.H264),
            ("avc", VideoCodec.H264),
            ("h265", VideoCodec.H265),
            ("hevc", VideoCodec.HEVC),
            ("vp9", VideoCodec.VP9),
            ("av1", VideoCodec.AV1),
            ("xvid", VideoCodec.XVID),
            ("divx", VideoCodec.DIVX),
            ("unknown_codec", VideoCodec.UNKNOWN),
        ]

        for codec_name, expected in test_cases:
            result = extractor._parse_video_codec(codec_name)
            assert result == expected

    def test_parse_audio_codec(self) -> None:
        """Test audio codec parsing."""
        extractor = MediaInfoExtractor()

        test_cases = [
            ("aac", AudioCodec.AAC),
            ("ac-3", AudioCodec.AC3),
            ("ac3", AudioCodec.AC3),
            ("dts", AudioCodec.DTS),
            ("dts-hd", AudioCodec.DTS_HD),
            ("truehd", AudioCodec.TRUEHD),
            ("flac", AudioCodec.FLAC),
            ("mp3", AudioCodec.MP3),
            ("pcm", AudioCodec.PCM),
            ("unknown_codec", AudioCodec.UNKNOWN),
        ]

        for codec_name, expected in test_cases:
            result = extractor._parse_audio_codec(codec_name)
            assert result == expected

    def test_parse_video_resolution(self) -> None:
        """Test video resolution parsing."""
        extractor = MediaInfoExtractor()

        test_cases = [
            ((720, 480), VideoResolution.SD_480P),
            ((1280, 720), VideoResolution.HD_720P),
            ((1920, 1080), VideoResolution.FHD_1080P),
            ((2560, 1440), VideoResolution.QHD_1440P),
            ((3840, 2160), VideoResolution.UHD_4K),
            ((7680, 4320), VideoResolution.UHD_8K),
            ((8000, 5000), VideoResolution.UNKNOWN),
        ]

        for (width, height), expected in test_cases:
            result = extractor._parse_video_resolution(width, height)
            assert result == expected

    def test_parse_video_format(self) -> None:
        """Test video format parsing."""
        extractor = MediaInfoExtractor()

        test_cases = [
            ("bluray", VideoFormat.BLURAY),
            ("uhd bluray", VideoFormat.UHD_BLURAY),
            ("remux", VideoFormat.REMUX),
            ("web-dl", VideoFormat.WEB_DL),
            ("webrip", VideoFormat.WEBRIP),
            ("hdtv", VideoFormat.HDTV),
            ("dvdrip", VideoFormat.DVDRIP),
            ("cam", VideoFormat.CAM),
            ("telesync", VideoFormat.TELESYNC),
            ("unknown_format", VideoFormat.UNKNOWN),
        ]

        for format_name, expected in test_cases:
            result = extractor._parse_video_format(format_name)
            assert result == expected

    @pytest.mark.asyncio
    async def test_extract_media_info_success(self, temp_dir) -> None:
        """Test successful media info extraction."""
        extractor = MediaInfoExtractor()
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"fake video content")

        # Mock MediaInfo.parse
        mock_media_info = Mock()
        mock_media_info.tracks = [Mock(), Mock()]  # Some tracks

        with patch(
            "smart_media_organizer.services.media_parser.MediaInfo.parse"
        ) as mock_parse:
            mock_parse.return_value = mock_media_info

            result = await extractor.extract_media_info(test_file)

            assert result == mock_media_info
            mock_parse.assert_called_once_with(str(test_file))

    @pytest.mark.asyncio
    async def test_extract_media_info_no_tracks(self, temp_dir) -> None:
        """Test media info extraction with no tracks."""
        extractor = MediaInfoExtractor()
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"fake content")

        # Mock MediaInfo.parse to return info with no tracks
        mock_media_info = Mock()
        mock_media_info.tracks = []

        with patch(
            "smart_media_organizer.services.media_parser.MediaInfo.parse"
        ) as mock_parse:
            mock_parse.return_value = mock_media_info

            with pytest.raises(UnsupportedFileError):
                await extractor.extract_media_info(test_file)

    @pytest.mark.asyncio
    async def test_extract_media_info_corrupted(self, temp_dir) -> None:
        """Test media info extraction with corrupted file."""
        extractor = MediaInfoExtractor()
        test_file = temp_dir / "corrupted.mp4"
        test_file.write_bytes(b"corrupted content")

        with patch(
            "smart_media_organizer.services.media_parser.MediaInfo.parse"
        ) as mock_parse:
            mock_parse.side_effect = Exception("File is corrupted")

            with pytest.raises(CorruptedFileError):
                await extractor.extract_media_info(test_file)

    def test_extract_video_info_with_track(self) -> None:
        """Test video info extraction with video track."""
        extractor = MediaInfoExtractor()

        # Mock MediaInfo with video track
        mock_video_track = Mock()
        mock_video_track.track_type = "Video"
        mock_video_track.codec = "H264"
        mock_video_track.width = 1920
        mock_video_track.height = 1080
        mock_video_track.bit_rate = 5000000
        mock_video_track.frame_rate = 23.976
        mock_video_track.bit_depth = 8
        mock_video_track.format = "BluRay"

        mock_media_info = Mock()
        mock_media_info.tracks = [mock_video_track]

        result = extractor.extract_video_info(mock_media_info)

        assert result["codec"] == VideoCodec.H264
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["resolution"] == VideoResolution.FHD_1080P
        assert result["bitrate"] == 5000000
        assert result["fps"] == 23.976
        assert result["bit_depth"] == 8

    def test_extract_video_info_no_track(self) -> None:
        """Test video info extraction without video track."""
        extractor = MediaInfoExtractor()

        mock_media_info = Mock()
        mock_media_info.tracks = []  # No tracks

        result = extractor.extract_video_info(mock_media_info)

        assert result["codec"] == VideoCodec.UNKNOWN
        assert result["resolution"] == VideoResolution.UNKNOWN
        assert result["width"] is None
        assert result["height"] is None

    def test_extract_audio_info_with_track(self) -> None:
        """Test audio info extraction with audio track."""
        extractor = MediaInfoExtractor()

        # Mock MediaInfo with audio track
        mock_audio_track = Mock()
        mock_audio_track.track_type = "Audio"
        mock_audio_track.codec = "AAC"
        mock_audio_track.channel_s = 6  # 5.1 surround
        mock_audio_track.sampling_rate = 48000
        mock_audio_track.bit_rate = 320000

        mock_media_info = Mock()
        mock_media_info.tracks = [mock_audio_track]

        result = extractor.extract_audio_info(mock_media_info)

        assert result["codec"] == AudioCodec.AAC
        assert result["channels"] == 6
        assert result["sample_rate"] == 48000
        assert result["bitrate"] == 320000

    def test_extract_general_info_with_track(self) -> None:
        """Test general info extraction with general track."""
        extractor = MediaInfoExtractor()

        # Mock MediaInfo with general track
        mock_general_track = Mock()
        mock_general_track.track_type = "General"
        mock_general_track.duration = 7200000  # 2 hours in milliseconds
        mock_general_track.file_size = 1073741824  # 1GB
        mock_general_track.format = "Matroska"

        mock_media_info = Mock()
        mock_media_info.tracks = [mock_general_track]

        result = extractor.extract_general_info(mock_media_info)

        assert result["duration"] == 7200  # 2 hours in seconds
        assert result["file_size"] == 1073741824
        assert result["container"] == "matroska"


class TestMediaFileParser:
    """Test the MediaFileParser class."""

    def test_parser_initialization(self) -> None:
        """Test parser initialization."""
        parser = MediaFileParser()
        assert parser.extractor is not None

    @pytest.mark.asyncio
    async def test_parse_media_file_success(self, sample_media_file) -> None:
        """Test successful media file parsing."""
        parser = MediaFileParser()

        # Mock the extractor
        mock_media_info = Mock()
        mock_media_info.tracks = [Mock()]

        with patch.object(
            parser.extractor, "extract_media_info"
        ) as mock_extract, patch.object(
            parser.extractor, "extract_video_info"
        ) as mock_video, patch.object(
            parser.extractor, "extract_audio_info"
        ) as mock_audio, patch.object(
            parser.extractor, "extract_general_info"
        ) as mock_general:
            mock_extract.return_value = mock_media_info
            mock_video.return_value = {
                "codec": VideoCodec.H264,
                "resolution": VideoResolution.FHD_1080P,
                "width": 1920,
                "height": 1080,
                "bitrate": 5000000,
                "fps": 23.976,
                "bit_depth": 8,
                "format": VideoFormat.BLURAY,
            }
            mock_audio.return_value = {
                "codec": AudioCodec.AAC,
                "channels": 6,
                "sample_rate": 48000,
                "bitrate": 320000,
            }
            mock_general.return_value = {
                "duration": 7200,
                "file_size": 1073741824,
                "container": "matroska",
            }

            result = await parser.parse_media_file(sample_media_file)

            assert result == sample_media_file
            assert result.processing_status == ProcessingStatus.COMPLETED
            assert result.info.video_codec == VideoCodec.H264
            assert result.info.audio_codec == AudioCodec.AAC
            assert result.info.duration_seconds == 7200

    @pytest.mark.asyncio
    async def test_parse_media_file_failure(self, sample_media_file) -> None:
        """Test media file parsing failure."""
        parser = MediaFileParser()

        with patch.object(parser.extractor, "extract_media_info") as mock_extract:
            mock_extract.side_effect = UnsupportedFileError("Test error")

            with pytest.raises(MediaParserError):
                await parser.parse_media_file(sample_media_file)

            assert sample_media_file.processing_status == ProcessingStatus.FAILED
            assert sample_media_file.error_message is not None

    @pytest.mark.asyncio
    async def test_verify_file_integrity_valid(self, temp_dir) -> None:
        """Test file integrity verification for valid file."""
        parser = MediaFileParser()
        test_file = temp_dir / "valid.mp4"
        test_file.write_bytes(b"valid content")

        # Mock MediaInfo to return valid info
        mock_general_track = Mock()
        mock_general_track.track_type = "General"
        mock_general_track.duration = 7200000  # 2 hours

        mock_media_info = Mock()
        mock_media_info.tracks = [mock_general_track]

        with patch.object(parser.extractor, "extract_media_info") as mock_extract:
            mock_extract.return_value = mock_media_info

            result = await parser.verify_file_integrity(test_file)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_file_integrity_invalid(self, temp_dir) -> None:
        """Test file integrity verification for invalid file."""
        parser = MediaFileParser()
        test_file = temp_dir / "invalid.mp4"
        test_file.write_bytes(b"invalid content")

        with patch.object(parser.extractor, "extract_media_info") as mock_extract:
            mock_extract.side_effect = Exception("Cannot parse")

            result = await parser.verify_file_integrity(test_file)
            assert result is False

    @pytest.mark.asyncio
    async def test_calculate_file_hash(self, temp_dir) -> None:
        """Test file hash calculation."""
        parser = MediaFileParser()
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"test content for hashing")

        hash_result = await parser.calculate_file_hash(test_file)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 32  # MD5 hash length

        # Test with different algorithm
        sha256_hash = await parser.calculate_file_hash(test_file, "sha256")
        assert len(sha256_hash) == 64  # SHA256 hash length


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_parse_media_file(self, temp_dir) -> None:
        """Test the parse_media_file convenience function."""
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB file

        with patch(
            "smart_media_organizer.services.media_parser.get_file_info"
        ) as mock_get_info, patch(
            "smart_media_organizer.services.media_parser.MediaFileParser"
        ) as mock_parser_class:
            mock_get_info.return_value = {"size": 2 * 1024 * 1024}

            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser

            # Mock the parse method to return a MediaFile
            mock_media_file = Mock()
            mock_parser.parse_media_file = AsyncMock(return_value=mock_media_file)

            result = await parse_media_file(test_file)

            assert result == mock_media_file
            mock_parser.parse_media_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_media_files(self, temp_dir) -> None:
        """Test the verify_media_files convenience function."""
        # Create test files
        file1 = temp_dir / "file1.mp4"
        file2 = temp_dir / "file2.mp4"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")

        test_files = [file1, file2]

        with patch(
            "smart_media_organizer.services.media_parser.MediaFileParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser

            # Mock verify_file_integrity to return different results
            async def mock_verify(file_path):
                return "file1" in str(file_path)  # file1 valid, file2 invalid

            mock_parser.verify_file_integrity = mock_verify

            results = await verify_media_files(test_files)

            assert len(results) == 2
            assert results[file1] is True
            assert results[file2] is False


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_extractor_with_thread_pool_error(self, temp_dir) -> None:
        """Test extractor when thread pool execution fails."""
        extractor = MediaInfoExtractor()
        test_file = temp_dir / "error.mp4"
        test_file.write_bytes(b"content")

        with patch(
            "smart_media_organizer.services.media_parser.MediaInfo.parse"
        ) as mock_parse:
            mock_parse.side_effect = RuntimeError("Thread pool error")

            with pytest.raises(UnsupportedFileError):
                await extractor.extract_media_info(test_file)

    def test_safe_get_track_value_with_exception(self) -> None:
        """Test safe track value retrieval when attribute access raises exception."""
        extractor = MediaInfoExtractor()

        # Mock track that raises exception on attribute access
        mock_track = Mock()
        mock_track.configure_mock(
            **{"problematic_attr.side_effect": TypeError("Type error")}
        )

        result = extractor._safe_get_track_value(
            mock_track, "problematic_attr", "fallback"
        )
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_calculate_file_hash_with_invalid_algorithm(self, temp_dir) -> None:
        """Test file hash calculation with invalid algorithm."""
        parser = MediaFileParser()
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"content")

        with pytest.raises(ValueError):
            await parser.calculate_file_hash(test_file, "invalid_algorithm")
