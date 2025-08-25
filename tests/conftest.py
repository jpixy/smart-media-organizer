"""Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import tempfile
from typing import Any

from pydantic import BaseModel
import pytest

from smart_media_organizer.models.config import Settings
from smart_media_organizer.models.media_file import (
    AudioCodec,
    MediaFile,
    MediaFileInfo,
    VideoCodec,
)
from smart_media_organizer.utils.logging import setup_development_logging


@pytest.fixture(scope="session", autouse=True)
def setup_logging() -> None:
    """Set up logging for tests."""
    setup_development_logging()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """Create a sample video file for testing."""
    video_file = temp_dir / "sample_movie.mkv"
    video_file.write_text("fake video content")
    return video_file


@pytest.fixture
def sample_media_file_info(sample_video_file: Path) -> MediaFileInfo:
    """Create sample media file info for testing."""
    return MediaFileInfo(
        file_path=sample_video_file,
        file_size=1024 * 1024 * 500,  # 500MB
        file_extension=".mkv",
        duration_seconds=7200,  # 2 hours
        video_codec=VideoCodec.H264,
        video_width=1920,
        video_height=1080,
        video_bitrate=5000000,  # 5Mbps
        video_fps=23.976,
        bit_depth=8,
        audio_codec=AudioCodec.DTS,
        audio_channels=6,  # 5.1
        audio_sample_rate=48000,
        audio_bitrate=1536000,  # 1.5Mbps
    )


@pytest.fixture
def sample_media_file(sample_media_file_info: MediaFileInfo) -> MediaFile:
    """Create sample media file for testing."""
    return MediaFile(info=sample_media_file_info)


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""

    class MockSettings(BaseModel):
        """Mock settings that don't require API keys."""

        # Required fields with mock values
        hf_token: str = "mock_hf_token"
        tmdb_api_key: str = "mock_tmdb_key"

        # Other settings with defaults
        log_level: str = "DEBUG"
        log_format: str = "console"
        max_concurrent: int = 5
        timeout_seconds: int = 10
        debug: bool = True
        mock_apis: bool = True

        def get_logging_level(self) -> int:
            return 10  # DEBUG level

        def is_video_file(self, file_path: Path) -> bool:
            return file_path.suffix.lower() in [".mp4", ".mkv", ".avi"]

        def should_skip_file(self, file_path: Path) -> bool:
            return ".sample" in file_path.name.lower()

    return MockSettings()


@pytest.fixture
def sample_files_structure(temp_dir: Path) -> dict[str, Path]:
    """Create a sample file structure for testing."""
    structure = {}

    # Create movie files
    movies_dir = temp_dir / "movies"
    movies_dir.mkdir()

    structure["movie1"] = movies_dir / "The.Matrix.1999.1080p.BluRay.x264.mkv"
    structure["movie1"].write_text("fake matrix movie")

    structure["movie2"] = movies_dir / "复仇者联盟.Avengers.2012.mkv"
    structure["movie2"].write_text("fake avengers movie")

    # Create TV show files
    tv_dir = temp_dir / "tv"
    tv_dir.mkdir()

    breaking_bad_dir = tv_dir / "Breaking Bad"
    breaking_bad_dir.mkdir()
    season1_dir = breaking_bad_dir / "Season 1"
    season1_dir.mkdir()

    structure["tv_episode1"] = season1_dir / "Breaking.Bad.S01E01.Pilot.mkv"
    structure["tv_episode1"].write_text("fake breaking bad episode")

    structure["tv_episode2"] = season1_dir / "Breaking.Bad.S01E02.Cat's.in.the.Bag.mkv"
    structure["tv_episode2"].write_text("fake breaking bad episode 2")

    # Create some files that should be skipped
    structure["sample_file"] = movies_dir / "Movie.Sample.mkv"
    structure["sample_file"].write_text("sample file")

    structure["trailer_file"] = movies_dir / "Movie.Trailer.mp4"
    structure["trailer_file"].write_text("trailer file")

    return structure


# Async test fixtures
@pytest.fixture
def event_loop() -> Generator[Any, None, None]:
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()


# Mock API responses
@pytest.fixture
def mock_hf_response() -> dict[str, Any]:
    """Mock Hugging Face API response."""
    return {
        "generated_text": """{
            "chinese_title": "黑客帝国",
            "english_title": "The Matrix",
            "year": 1999,
            "edition": null,
            "confidence": 0.95
        }"""
    }


@pytest.fixture
def mock_tmdb_movie_response() -> dict[str, Any]:
    """Mock TMDB movie API response."""
    return {
        "id": 603,
        "imdb_id": "tt0133093",
        "title": "The Matrix",
        "original_title": "The Matrix",
        "overview": "Set in the 22nd century...",
        "release_date": "1999-03-30",
        "runtime": 136,
        "vote_average": 8.7,
        "vote_count": 22000,
        "popularity": 85.0,
        "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "backdrop_path": "/fNG7i7RqMErkcqhohV2a6cV1Ehy.jpg",
        "adult": False,
        "video": False,
        "status": "Released",
        "budget": 63000000,
        "revenue": 467222000,
        "genres": [
            {"id": 28, "name": "Action"},
            {"id": 878, "name": "Science Fiction"},
        ],
    }


@pytest.fixture
def mock_tmdb_tv_response() -> dict[str, Any]:
    """Mock TMDB TV show API response."""
    return {
        "id": 1396,
        "name": "Breaking Bad",
        "original_name": "Breaking Bad",
        "overview": "A high school chemistry teacher...",
        "first_air_date": "2008-01-20",
        "last_air_date": "2013-09-29",
        "number_of_episodes": 62,
        "number_of_seasons": 5,
        "vote_average": 9.5,
        "vote_count": 8000,
        "popularity": 400.0,
        "status": "Ended",
        "type": "Scripted",
        "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
    }
