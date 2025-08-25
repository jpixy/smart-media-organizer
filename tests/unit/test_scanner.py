"""Unit tests for the async file scanner.

This module tests the MediaFileScanner and related components.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from smart_media_organizer.core.scanner import (
    InvalidDirectoryError,
    MediaFileScanner,
    ScanProgress,
    get_media_file_count,
    scan_for_media,
)
from smart_media_organizer.models.media_file import ProcessingStatus


class TestScanProgress:
    """Test the ScanProgress class."""

    @pytest.mark.asyncio
    async def test_progress_context_manager(self) -> None:
        """Test ScanProgress as async context manager."""
        progress = ScanProgress()

        async with progress:
            task_id = progress.start_scan("Test scan", total=10)
            assert task_id is not None

            progress.update_scan(advance=1, description="Updated")
            progress.set_scan_total(20)

    @pytest.mark.asyncio
    async def test_analysis_progress(self) -> None:
        """Test analysis progress tracking."""
        progress = ScanProgress()

        async with progress:
            analysis_task = progress.start_analysis("Test analysis", total=5)
            assert analysis_task is not None

            progress.update_analysis(advance=2)
            progress.set_analysis_total(15)


class TestMediaFileScanner:
    """Test the MediaFileScanner class."""

    def test_scanner_initialization(self, mock_settings) -> None:
        """Test scanner initialization."""
        scanner = MediaFileScanner(mock_settings)
        assert scanner.settings == mock_settings
        assert scanner.magic_mime is not None
        assert scanner.magic_type is not None

    @pytest.mark.asyncio
    async def test_scan_nonexistent_directory(self, mock_settings) -> None:
        """Test scanning a nonexistent directory."""
        scanner = MediaFileScanner(mock_settings)
        nonexistent_dir = Path("/nonexistent/directory")

        with pytest.raises(InvalidDirectoryError):
            async for _ in scanner.scan_directory(nonexistent_dir):
                pass

    @pytest.mark.asyncio
    async def test_scan_single_file_not_found(self, mock_settings) -> None:
        """Test scanning a nonexistent file."""
        scanner = MediaFileScanner(mock_settings)
        nonexistent_file = Path("/nonexistent/file.mp4")

        with pytest.raises(InvalidDirectoryError):
            await scanner.scan_single_file(nonexistent_file)

    @pytest.mark.asyncio
    async def test_is_potential_media_file(self, mock_settings) -> None:
        """Test media file detection by extension."""
        scanner = MediaFileScanner(mock_settings)

        # Video files
        assert scanner._is_potential_media_file(Path("movie.mp4"))
        assert scanner._is_potential_media_file(Path("show.mkv"))
        assert scanner._is_potential_media_file(Path("video.avi"))

        # Subtitle files
        assert scanner._is_potential_media_file(Path("subtitles.srt"))
        assert scanner._is_potential_media_file(Path("subs.ass"))

        # Image files
        assert scanner._is_potential_media_file(Path("poster.jpg"))
        assert scanner._is_potential_media_file(Path("banner.png"))

        # Non-media files
        assert not scanner._is_potential_media_file(Path("document.txt"))
        assert not scanner._is_potential_media_file(Path("archive.zip"))
        assert not scanner._is_potential_media_file(Path("config.json"))

    @pytest.mark.asyncio
    async def test_verify_media_file_success(self, mock_settings, temp_dir) -> None:
        """Test successful media file verification."""
        scanner = MediaFileScanner(mock_settings)

        # Create a fake media file
        test_file = temp_dir / "test_video.mp4"
        test_file.write_bytes(b"fake mp4 content with some data")

        # Mock the magic detection to return video MIME type
        with patch.object(scanner.magic_mime, "from_buffer", return_value="video/mp4"):
            result = await scanner._verify_media_file(test_file)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_media_file_failure(self, mock_settings, temp_dir) -> None:
        """Test failed media file verification."""
        scanner = MediaFileScanner(mock_settings)

        # Create a fake non-media file
        test_file = temp_dir / "test_document.txt"
        test_file.write_text("This is not a media file")

        # Mock the magic detection to return text MIME type
        with patch.object(scanner.magic_mime, "from_buffer", return_value="text/plain"):
            result = await scanner._verify_media_file(test_file)
            assert result is False

    @pytest.mark.asyncio
    async def test_analyze_file_skip_patterns(self, mock_settings, temp_dir) -> None:
        """Test file analysis with skip patterns."""
        scanner = MediaFileScanner(mock_settings)

        # Create a file that should be skipped
        skip_file = temp_dir / "movie.sample.mp4"
        skip_file.write_bytes(b"sample content")

        result = await scanner._analyze_file(skip_file)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_file_too_small(self, mock_settings, temp_dir) -> None:
        """Test file analysis with file too small."""
        scanner = MediaFileScanner(mock_settings)

        # Create a small file
        small_file = temp_dir / "tiny_video.mp4"
        small_file.write_bytes(b"tiny")  # Very small file

        result = await scanner._analyze_file(small_file)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_file_success(self, mock_settings, temp_dir) -> None:
        """Test successful file analysis."""
        scanner = MediaFileScanner(mock_settings)

        # Create a reasonably sized file
        media_file = temp_dir / "good_video.mp4"
        media_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB file

        # Mock various checks
        with patch.object(
            scanner, "_is_potential_media_file", return_value=True
        ), patch.object(scanner, "_verify_media_file", return_value=True):
            result = await scanner._analyze_file(media_file)

            assert result is not None
            assert result.info.file_path == media_file
            assert result.info.file_extension == ".mp4"
            assert result.processing_status == ProcessingStatus.SCANNING

    @pytest.mark.asyncio
    async def test_get_directory_stats(
        self, mock_settings, sample_files_structure
    ) -> None:
        """Test directory statistics calculation."""
        scanner = MediaFileScanner(mock_settings)

        # Get the temp directory from the structure
        temp_dir = next(iter(sample_files_structure.values())).parent.parent

        stats = await scanner.get_directory_stats(temp_dir)

        assert isinstance(stats, dict)
        assert "total_files" in stats
        assert "video_files" in stats
        assert "subtitle_files" in stats
        assert "image_files" in stats
        assert "other_files" in stats
        assert "total_size" in stats

        assert stats["total_files"] >= 0
        assert stats["total_size"] >= 0

    @pytest.mark.asyncio
    @patch("smart_media_organizer.core.scanner.aiofiles.os.path.exists")
    @patch("smart_media_organizer.core.scanner.aiofiles.os.path.isdir")
    async def test_scan_directory_with_progress(
        self, mock_isdir, mock_exists, mock_settings
    ) -> None:
        """Test directory scanning with progress display."""
        mock_exists.return_value = True
        mock_isdir.return_value = True

        scanner = MediaFileScanner(mock_settings)

        # Mock the file discovery to return empty list
        with patch.object(scanner, "_discover_files") as mock_discover:
            mock_discover.return_value = asyncio.iter([])

            files = []
            async for media_file in scanner.scan_directory(
                Path("/fake/dir"), show_progress=True
            ):
                files.append(media_file)

            assert len(files) == 0
            mock_discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_files_recursive(
        self, mock_settings, sample_files_structure
    ) -> None:
        """Test recursive file discovery."""
        scanner = MediaFileScanner(mock_settings)

        # Get the root directory
        root_dir = next(iter(sample_files_structure.values())).parent.parent

        files = []
        async for file_path in scanner._discover_files(root_dir, recursive=True):
            files.append(file_path)

        assert len(files) > 0
        # Should find files in subdirectories
        assert any("movies" in str(f) for f in files)

    @pytest.mark.asyncio
    async def test_discover_files_non_recursive(self, mock_settings, temp_dir) -> None:
        """Test non-recursive file discovery."""
        scanner = MediaFileScanner(mock_settings)

        # Create files in root and subdirectory
        root_file = temp_dir / "root_file.txt"
        root_file.write_text("root")

        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()
        sub_file = sub_dir / "sub_file.txt"
        sub_file.write_text("sub")

        files = []
        async for file_path in scanner._discover_files(temp_dir, recursive=False):
            files.append(file_path)

        # Should only find root level files
        file_names = [f.name for f in files]
        assert "root_file.txt" in file_names
        assert "sub_file.txt" not in file_names


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_scan_for_media(self, mock_settings, temp_dir) -> None:
        """Test the scan_for_media convenience function."""
        # Create a fake media file
        media_file = temp_dir / "test.mp4"
        media_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        with patch(
            "smart_media_organizer.core.scanner.MediaFileScanner"
        ) as mock_scanner_class:
            mock_scanner = Mock()
            mock_scanner_class.return_value = mock_scanner

            # Mock the async generator
            async def mock_scan_generator(*args, **kwargs):
                yield Mock()  # Fake MediaFile

            mock_scanner.scan_directory = mock_scan_generator

            result = await scan_for_media(temp_dir, mock_settings)

            assert isinstance(result, list)
            assert len(result) == 1
            mock_scanner_class.assert_called_once_with(mock_settings)

    @pytest.mark.asyncio
    async def test_get_media_file_count(self, mock_settings, temp_dir) -> None:
        """Test the get_media_file_count convenience function."""
        with patch(
            "smart_media_organizer.core.scanner.MediaFileScanner"
        ) as mock_scanner_class:
            mock_scanner = Mock()
            mock_scanner_class.return_value = mock_scanner

            # Mock the async generator to yield 3 files
            async def mock_scan_generator(*args, **kwargs):
                for _ in range(3):
                    yield Mock()  # Fake MediaFile

            mock_scanner.scan_directory = mock_scan_generator

            count = await get_media_file_count(temp_dir, mock_settings)

            assert count == 3
            mock_scanner_class.assert_called_once_with(mock_settings)


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_analyze_file_with_exception(self, mock_settings, temp_dir) -> None:
        """Test file analysis with exceptions."""
        scanner = MediaFileScanner(mock_settings)

        # Create a file
        test_file = temp_dir / "error_file.mp4"
        test_file.write_bytes(b"content")

        # Mock get_file_info to raise an exception
        with patch("smart_media_organizer.core.scanner.get_file_info") as mock_get_info:
            mock_get_info.side_effect = OSError("Mock file error")

            result = await scanner._analyze_file(test_file)
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_media_file_with_exception(
        self, mock_settings, temp_dir
    ) -> None:
        """Test media file verification with exceptions."""
        scanner = MediaFileScanner(mock_settings)

        test_file = temp_dir / "error_file.mp4"
        test_file.write_bytes(b"content")

        # Mock magic to raise an exception
        with patch.object(scanner.magic_mime, "from_buffer") as mock_magic:
            mock_magic.side_effect = Exception("Magic error")

            result = await scanner._verify_media_file(test_file)
            # Should fall back to extension-based detection
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_directory_stats_with_error_files(
        self, mock_settings, temp_dir
    ) -> None:
        """Test directory stats with some files causing errors."""
        scanner = MediaFileScanner(mock_settings)

        # Create some files
        good_file = temp_dir / "good.txt"
        good_file.write_text("good content")

        bad_file = temp_dir / "bad.txt"
        bad_file.write_text("bad content")

        # Mock get_file_info to fail for one file
        async def mock_get_info(file_path):
            if "bad" in str(file_path):
                raise OSError("Mock error")
            return {"size": 100}

        with patch(
            "smart_media_organizer.core.scanner.get_file_info",
            side_effect=mock_get_info,
        ):
            stats = await scanner.get_directory_stats(temp_dir)

            # Should still return stats, just excluding the bad file
            assert isinstance(stats, dict)
            assert stats["total_files"] >= 1  # At least the good file
