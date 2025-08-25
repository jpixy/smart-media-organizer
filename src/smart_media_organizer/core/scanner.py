"""Async media file scanner with Rich progress display.

This module provides high-performance asynchronous file scanning capabilities
for discovering and analyzing media files in directory structures.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import aiofiles
import aiofiles.os
import magic
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
import structlog

from smart_media_organizer.models.config import Settings
from smart_media_organizer.models.media_file import (
    MediaFile,
    MediaFileInfo,
    ProcessingStatus,
)
from smart_media_organizer.utils.file_ops import (
    get_file_info,
    is_image_file,
    is_subtitle_file,
    is_video_file,
)

logger = structlog.get_logger(__name__)


class ScannerError(Exception):
    """Base exception for scanner errors."""


class InvalidDirectoryError(ScannerError):
    """Invalid directory error."""


class ScanProgress:
    """Progress tracking for file scanning operations."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console,
        )
        self.scan_task: TaskID | None = None
        self.analyze_task: TaskID | None = None

    async def __aenter__(self):
        self.progress.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.progress.stop()

    def start_scan(self, description: str, total: int | None = None) -> TaskID:
        """Start a new scan task."""
        self.scan_task = self.progress.add_task(description, total=total)
        return self.scan_task

    def start_analysis(self, description: str, total: int | None = None) -> TaskID:
        """Start a new analysis task."""
        self.analyze_task = self.progress.add_task(description, total=total)
        return self.analyze_task

    def update_scan(self, advance: int = 1, description: str | None = None) -> None:
        """Update scan progress."""
        if self.scan_task is not None:
            self.progress.update(
                self.scan_task, advance=advance, description=description
            )

    def update_analysis(self, advance: int = 1, description: str | None = None) -> None:
        """Update analysis progress."""
        if self.analyze_task is not None:
            self.progress.update(
                self.analyze_task, advance=advance, description=description
            )

    def set_scan_total(self, total: int) -> None:
        """Set the total for scan task."""
        if self.scan_task is not None:
            self.progress.update(self.scan_task, total=total)

    def set_analysis_total(self, total: int) -> None:
        """Set the total for analysis task."""
        if self.analyze_task is not None:
            self.progress.update(self.analyze_task, total=total)


class MediaFileScanner:
    """High-performance async media file scanner."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the scanner.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.magic_mime = magic.Magic(mime=True)
        self.magic_type = magic.Magic()

    async def scan_directory(
        self,
        directory: Path,
        *,
        recursive: bool = True,
        show_progress: bool = True,
        max_concurrent: int | None = None,
    ) -> AsyncGenerator[MediaFile, None]:
        """Scan directory for media files asynchronously.

        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            show_progress: Whether to show progress bar
            max_concurrent: Maximum concurrent file operations

        Yields:
            MediaFile objects for discovered files

        Raises:
            InvalidDirectoryError: If directory doesn't exist or isn't accessible
        """
        if not await aiofiles.os.path.exists(directory):
            raise InvalidDirectoryError(f"Directory not found: {directory}")

        if not await aiofiles.os.path.isdir(directory):
            raise InvalidDirectoryError(f"Path is not a directory: {directory}")

        max_concurrent = max_concurrent or self.settings.max_concurrent_api_calls

        logger.info(
            "Starting directory scan",
            directory=str(directory),
            recursive=recursive,
            max_concurrent=max_concurrent,
        )

        # Use semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async with ScanProgress() as progress:
            if show_progress:
                progress.start_scan("🔍 Discovering files...")

            # First pass: discover all files
            file_paths = []
            async for file_path in self._discover_files(directory, recursive=recursive):
                file_paths.append(file_path)
                if show_progress:
                    progress.update_scan(
                        description=f"🔍 Found {len(file_paths)} files..."
                    )

            if show_progress:
                progress.set_scan_total(len(file_paths))
                progress.start_analysis("📊 Analyzing files...", total=len(file_paths))

            # Second pass: analyze files concurrently
            tasks = []
            for file_path in file_paths:
                task = asyncio.create_task(
                    self._analyze_file_with_semaphore(
                        semaphore, file_path, progress if show_progress else None
                    )
                )
                tasks.append(task)

            # Process results as they complete
            for completed_task in asyncio.as_completed(tasks):
                try:
                    media_file = await completed_task
                    if media_file:
                        yield media_file
                except Exception as e:
                    logger.error("Error analyzing file", error=str(e), exc_info=True)

        logger.info(
            "Directory scan completed",
            directory=str(directory),
            total_files=len(file_paths),
        )

    async def _discover_files(
        self, directory: Path, *, recursive: bool = True
    ) -> AsyncGenerator[Path, None]:
        """Discover all files in directory."""
        try:
            if recursive:
                # Use Path.rglob for recursive discovery
                for path in directory.rglob("*"):
                    if await aiofiles.os.path.isfile(path):
                        yield path
            else:
                # Use Path.glob for single-level discovery
                for path in directory.glob("*"):
                    if await aiofiles.os.path.isfile(path):
                        yield path
        except OSError as e:
            logger.error(
                "Error discovering files", directory=str(directory), error=str(e)
            )
            raise ScannerError(f"Cannot scan directory {directory}: {e}") from e

    async def _analyze_file_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        file_path: Path,
        progress: ScanProgress | None,
    ) -> MediaFile | None:
        """Analyze a single file with semaphore protection."""
        async with semaphore:
            result = await self._analyze_file(file_path)
            if progress:
                progress.update_analysis(description=f"📊 Analyzed {file_path.name}")
            return result

    async def _analyze_file(self, file_path: Path) -> MediaFile | None:
        """Analyze a single file and create MediaFile if it's a media file."""
        try:
            # Check if file should be skipped
            if self.settings.should_skip_file(file_path):
                logger.debug(
                    "Skipping file due to skip patterns", file_path=str(file_path)
                )
                return None

            # Check file extension first for quick filtering
            if not self._is_potential_media_file(file_path):
                return None

            # Get basic file information
            file_info_dict = await get_file_info(file_path)

            # Check file size constraints
            min_size, max_size = self.settings.get_file_size_limits()
            file_size = file_info_dict["size"]

            if file_size < min_size:
                logger.debug(
                    "File too small",
                    file_path=str(file_path),
                    size=file_size,
                    min_size=min_size,
                )
                return None

            if max_size and file_size > max_size:
                logger.debug(
                    "File too large",
                    file_path=str(file_path),
                    size=file_size,
                    max_size=max_size,
                )
                return None

            # Verify it's actually a video file using magic numbers
            if not await self._verify_media_file(file_path):
                return None

            # Create MediaFileInfo
            media_file_info = MediaFileInfo(
                file_path=file_path,
                file_size=file_size,
                file_extension=file_path.suffix.lower(),
                modified_at=None,  # Will be populated by media parser if needed
            )

            # Create MediaFile
            media_file = MediaFile(
                info=media_file_info,
                processing_status=ProcessingStatus.SCANNING,
            )

            logger.debug(
                "Media file discovered", file_path=str(file_path), size=file_size
            )
            return media_file

        except Exception as e:
            logger.error("Error analyzing file", file_path=str(file_path), error=str(e))
            return None

    def _is_potential_media_file(self, file_path: Path) -> bool:
        """Quick check if file might be a media file based on extension."""
        return (
            is_video_file(file_path)
            or is_subtitle_file(file_path)
            or is_image_file(file_path)
        )

    async def _verify_media_file(self, file_path: Path) -> bool:
        """Verify file is actually a media file using magic numbers."""
        try:
            # Read first few bytes to check magic numbers
            async with aiofiles.open(file_path, "rb") as f:
                header = await f.read(2048)

            if not header:
                return False

            # Use python-magic to get MIME type
            try:
                mime_type = self.magic_mime.from_buffer(header)

                # Check if it's a video/audio/image MIME type
                media_mimes = [
                    "video/",
                    "audio/",
                    "image/",
                    "application/ogg",  # OGG containers
                    "application/x-matroska",  # MKV files
                ]

                is_media = any(mime_type.startswith(prefix) for prefix in media_mimes)

                if is_media:
                    logger.debug(
                        "File verified as media",
                        file_path=str(file_path),
                        mime_type=mime_type,
                    )
                else:
                    logger.debug(
                        "File not recognized as media",
                        file_path=str(file_path),
                        mime_type=mime_type,
                    )

                return is_media

            except Exception as e:
                logger.warning(
                    "Cannot determine MIME type, assuming media file",
                    file_path=str(file_path),
                    error=str(e),
                )
                # Fallback to extension-based detection
                return is_video_file(file_path)

        except Exception as e:
            logger.error(
                "Error verifying media file", file_path=str(file_path), error=str(e)
            )
            return False

    async def scan_single_file(self, file_path: Path) -> MediaFile | None:
        """Scan and analyze a single file.

        Args:
            file_path: Path to the file to scan

        Returns:
            MediaFile if the file is a valid media file, None otherwise
        """
        if not await aiofiles.os.path.exists(file_path):
            raise InvalidDirectoryError(f"File not found: {file_path}")

        if not await aiofiles.os.path.isfile(file_path):
            raise InvalidDirectoryError(f"Path is not a file: {file_path}")

        logger.info("Scanning single file", file_path=str(file_path))
        return await self._analyze_file(file_path)

    async def get_directory_stats(self, directory: Path) -> dict[str, int]:
        """Get statistics about a directory.

        Args:
            directory: Directory to analyze

        Returns:
            Dictionary with directory statistics
        """
        if not await aiofiles.os.path.exists(directory):
            raise InvalidDirectoryError(f"Directory not found: {directory}")

        stats = {
            "total_files": 0,
            "video_files": 0,
            "subtitle_files": 0,
            "image_files": 0,
            "other_files": 0,
            "total_size": 0,
        }

        async for file_path in self._discover_files(directory, recursive=True):
            try:
                file_info = await get_file_info(file_path)
                stats["total_files"] += 1
                stats["total_size"] += file_info["size"]

                if is_video_file(file_path):
                    stats["video_files"] += 1
                elif is_subtitle_file(file_path):
                    stats["subtitle_files"] += 1
                elif is_image_file(file_path):
                    stats["image_files"] += 1
                else:
                    stats["other_files"] += 1

            except Exception as e:
                logger.warning(
                    "Error getting file stats", file_path=str(file_path), error=str(e)
                )

        logger.info("Directory stats calculated", directory=str(directory), stats=stats)
        return stats


# Convenience functions
async def scan_for_media(
    directory: Path,
    settings: Settings,
    *,
    recursive: bool = True,
    show_progress: bool = True,
) -> list[MediaFile]:
    """Convenience function to scan for media files and return a list.

    Args:
        directory: Directory to scan
        settings: Application settings
        recursive: Whether to scan recursively
        show_progress: Whether to show progress

    Returns:
        List of discovered MediaFile objects
    """
    scanner = MediaFileScanner(settings)
    media_files = []

    async for media_file in scanner.scan_directory(
        directory, recursive=recursive, show_progress=show_progress
    ):
        media_files.append(media_file)

    return media_files


async def get_media_file_count(directory: Path, settings: Settings) -> int:
    """Get the count of media files in a directory.

    Args:
        directory: Directory to scan
        settings: Application settings

    Returns:
        Number of media files found
    """
    scanner = MediaFileScanner(settings)
    count = 0

    async for _ in scanner.scan_directory(directory, show_progress=False):
        count += 1

    return count
