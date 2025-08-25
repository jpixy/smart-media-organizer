"""Unit tests for data models.

This module tests the Pydantic data models to ensure they work correctly.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
import pytest

from smart_media_organizer.models.config import LogLevel, MediaType, Settings
from smart_media_organizer.models.media_file import (
    AudioCodec,
    MediaFile,
    MediaFileInfo,
    ProcessingStatus,
    VideoCodec,
    VideoResolution,
)
from smart_media_organizer.models.movie import AIMovieIdentification


class TestMediaFileInfo:
    """Test MediaFileInfo model."""

    def test_create_valid_media_file_info(self, sample_video_file: Path) -> None:
        """Test creating valid media file info."""
        info = MediaFileInfo(
            file_path=sample_video_file,
            file_size=1024 * 1024 * 100,  # 100MB
            file_extension=".mkv",
            duration_seconds=3600,  # 1 hour
            video_codec=VideoCodec.H264,
            video_width=1920,
            video_height=1080,
        )

        assert info.file_path == sample_video_file
        assert info.filename == "sample_movie.mkv"
        assert info.file_size_mb == pytest.approx(100.0, rel=1e-2)
        assert info.duration_formatted == "01:00:00"
        assert info.resolution_display == "1920x1080"

    def test_computed_fields(self, sample_media_file_info: MediaFileInfo) -> None:
        """Test computed fields work correctly."""
        assert sample_media_file_info.filename == "sample_movie.mkv"
        assert sample_media_file_info.file_size_mb == pytest.approx(500.0, rel=1e-2)
        assert sample_media_file_info.file_size_gb == pytest.approx(0.488, rel=1e-2)
        assert sample_media_file_info.duration_formatted == "02:00:00"
        assert sample_media_file_info.resolution_display == "1920x1080"
        assert sample_media_file_info.audio_channels_display == "5.1 (Surround)"

    def test_validation_errors(self, sample_video_file: Path) -> None:
        """Test validation errors for invalid data."""
        with pytest.raises(ValidationError):
            # Negative file size
            MediaFileInfo(
                file_path=sample_video_file,
                file_size=-1,
                file_extension=".mkv",
            )

        with pytest.raises(ValidationError):
            # Negative duration
            MediaFileInfo(
                file_path=sample_video_file,
                file_size=1000,
                file_extension=".mkv",
                duration_seconds=-10,
            )


class TestMediaFile:
    """Test MediaFile model."""

    def test_create_media_file(self, sample_media_file: MediaFile) -> None:
        """Test creating a media file."""
        assert sample_media_file.processing_status == ProcessingStatus.PENDING
        assert not sample_media_file.is_processed
        assert not sample_media_file.has_error
        assert sample_media_file.filename == "sample_movie.mkv"

    def test_update_status(self, sample_media_file: MediaFile) -> None:
        """Test updating processing status."""
        # Update to completed
        sample_media_file.update_status(ProcessingStatus.COMPLETED)
        assert sample_media_file.processing_status == ProcessingStatus.COMPLETED
        assert sample_media_file.is_processed
        assert not sample_media_file.has_error
        assert sample_media_file.processed_at is not None

        # Update to failed with error
        sample_media_file.update_status(ProcessingStatus.FAILED, "Test error")
        assert sample_media_file.processing_status == ProcessingStatus.FAILED
        assert not sample_media_file.is_processed
        assert sample_media_file.has_error
        assert sample_media_file.error_message == "Test error"

    def test_to_dict(self, sample_media_file: MediaFile) -> None:
        """Test converting to dictionary."""
        data = sample_media_file.to_dict()
        assert isinstance(data, dict)
        assert "is_processed" in data
        assert "has_error" in data
        assert "file_path" in data
        assert "filename" in data


class TestAIMovieIdentification:
    """Test AIMovieIdentification model."""

    def test_create_ai_identification(self) -> None:
        """Test creating AI identification result."""
        ai_result = AIMovieIdentification(
            chinese_title="黑客帝国",
            english_title="The Matrix",
            year=1999,
            confidence=0.95,
            model_used="test-model",
            processing_time=1.5,
            raw_response={"test": "data"},
        )

        assert ai_result.best_title == "黑客帝国"
        assert ai_result.has_year
        assert ai_result.year == 1999
        assert ai_result.confidence == 0.95

    def test_best_title_fallback(self) -> None:
        """Test best title fallback logic."""
        # Only English title
        ai_result = AIMovieIdentification(
            english_title="The Matrix",
            year=1999,
            confidence=0.95,
            model_used="test-model",
            processing_time=1.5,
            raw_response={},
        )
        assert ai_result.best_title == "The Matrix"

        # Only Chinese title
        ai_result = AIMovieIdentification(
            chinese_title="黑客帝国",
            year=1999,
            confidence=0.95,
            model_used="test-model",
            processing_time=1.5,
            raw_response={},
        )
        assert ai_result.best_title == "黑客帝国"

        # No title
        ai_result = AIMovieIdentification(
            year=1999,
            confidence=0.95,
            model_used="test-model",
            processing_time=1.5,
            raw_response={},
        )
        assert ai_result.best_title is None

    def test_validation(self) -> None:
        """Test validation constraints."""
        # Valid confidence
        ai_result = AIMovieIdentification(
            confidence=0.5,
            model_used="test",
            processing_time=1.0,
            raw_response={},
        )
        assert ai_result.confidence == 0.5

        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            AIMovieIdentification(
                confidence=1.5,
                model_used="test",
                processing_time=1.0,
                raw_response={},
            )

        # Invalid confidence (negative)
        with pytest.raises(ValidationError):
            AIMovieIdentification(
                confidence=-0.1,
                model_used="test",
                processing_time=1.0,
                raw_response={},
            )

        # Invalid year (too old)
        with pytest.raises(ValidationError):
            AIMovieIdentification(
                year=1800,
                confidence=0.5,
                model_used="test",
                processing_time=1.0,
                raw_response={},
            )


class TestSettings:
    """Test Settings model."""

    def test_mock_settings(self, mock_settings: Settings) -> None:
        """Test mock settings work correctly."""
        assert mock_settings.hf_token == "mock_hf_token"
        assert mock_settings.tmdb_api_key == "mock_tmdb_key"
        assert mock_settings.debug is True

    def test_enum_validation(self, mock_settings: Settings) -> None:
        """Test enum validation in settings."""
        # Test video file detection
        assert mock_settings.is_video_file(Path("movie.mkv"))
        assert mock_settings.is_video_file(Path("movie.mp4"))
        assert not mock_settings.is_video_file(Path("movie.txt"))

        # Test skip patterns
        assert mock_settings.should_skip_file(Path("movie.sample.mkv"))
        assert not mock_settings.should_skip_file(Path("movie.mkv"))


class TestEnums:
    """Test enumeration types."""

    def test_video_codec_enum(self) -> None:
        """Test VideoCodec enum."""
        assert VideoCodec.H264 == "h264"
        assert VideoCodec.HEVC == "hevc"
        assert VideoCodec.H264.value == "h264"

    def test_audio_codec_enum(self) -> None:
        """Test AudioCodec enum."""
        assert AudioCodec.DTS == "dts"
        assert AudioCodec.AAC == "aac"
        assert AudioCodec.DTS.value == "dts"

    def test_video_resolution_enum(self) -> None:
        """Test VideoResolution enum."""
        assert VideoResolution.FHD_1080P == "1080p"
        assert VideoResolution.UHD_4K == "2160p"

    def test_media_type_enum(self) -> None:
        """Test MediaType enum."""
        assert MediaType.AUTO == "auto"
        assert MediaType.MOVIE == "movie"
        assert MediaType.TV == "tv"

    def test_log_level_enum(self) -> None:
        """Test LogLevel enum."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.ERROR == "ERROR"

    def test_processing_status_enum(self) -> None:
        """Test ProcessingStatus enum."""
        assert ProcessingStatus.PENDING == "pending"
        assert ProcessingStatus.COMPLETED == "completed"
        assert ProcessingStatus.FAILED == "failed"
