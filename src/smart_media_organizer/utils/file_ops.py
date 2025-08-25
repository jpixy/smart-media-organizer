"""Async file operations utilities.

This module provides type-safe asynchronous file operations
for the media organizer application.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
import hashlib
from pathlib import Path

import aiofiles
import aiofiles.os
import structlog

logger = structlog.get_logger(__name__)


class FileOperationError(Exception):
    """Base exception for file operation errors."""


class FileNotFoundError(FileOperationError):
    """File not found error."""


class FilePermissionError(FileOperationError):
    """File permission error."""


class FileIntegrityError(FileOperationError):
    """File integrity verification error."""


async def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, create if it doesn't.

    Args:
        path: Directory path to ensure

    Returns:
        The created/existing directory path

    Raises:
        FilePermissionError: If unable to create directory
    """
    try:
        if not await aiofiles.os.path.exists(path):
            await aiofiles.os.makedirs(path, exist_ok=True)
            logger.debug("Created directory", path=str(path))
        return path
    except OSError as e:
        raise FilePermissionError(f"Cannot create directory {path}: {e}") from e


async def get_file_info(file_path: Path) -> dict[str, any]:
    """Get comprehensive file information asynchronously.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary containing file information

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    try:
        stat_result = await aiofiles.os.stat(file_path)

        return {
            "path": file_path,
            "size": stat_result.st_size,
            "size_mb": stat_result.st_size / (1024 * 1024),
            "size_gb": stat_result.st_size / (1024 * 1024 * 1024),
            "modified_time": stat_result.st_mtime,
            "created_time": stat_result.st_ctime,
            "permissions": oct(stat_result.st_mode),
            "is_file": await aiofiles.os.path.isfile(file_path),
            "is_directory": await aiofiles.os.path.isdir(file_path),
            "exists": True,
        }
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {file_path}") from e
    except OSError as e:
        logger.error("Error getting file info", file_path=str(file_path), error=str(e))
        raise FileOperationError(f"Cannot get file info for {file_path}: {e}") from e


async def calculate_file_hash(
    file_path: Path, *, algorithm: str = "md5", chunk_size: int = 8192
) -> str:
    """Calculate file hash asynchronously.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        chunk_size: Size of chunks to read at a time

    Returns:
        Hexadecimal hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is not supported
    """
    try:
        hash_obj = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from e

    try:
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                hash_obj.update(chunk)

        result = hash_obj.hexdigest()
        logger.debug(
            "Calculated file hash",
            file_path=str(file_path),
            algorithm=algorithm,
            hash=result[:16] + "...",
        )
        return result

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {file_path}") from e
    except OSError as e:
        logger.error("Error calculating hash", file_path=str(file_path), error=str(e))
        raise FileOperationError(f"Cannot calculate hash for {file_path}: {e}") from e


async def copy_file_atomic(
    source: Path,
    destination: Path,
    *,
    verify_integrity: bool = True,
    preserve_metadata: bool = True,
) -> Path:
    """Copy file atomically with integrity verification.

    Args:
        source: Source file path
        destination: Destination file path
        verify_integrity: Whether to verify file integrity after copy
        preserve_metadata: Whether to preserve file metadata

    Returns:
        Path to the copied file

    Raises:
        FileNotFoundError: If source file doesn't exist
        FileOperationError: If copy operation fails
        FileIntegrityError: If integrity verification fails
    """
    if not await aiofiles.os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")

    # Ensure destination directory exists
    await ensure_directory(destination.parent)

    # Create temporary file with .tmp suffix
    temp_destination = destination.with_suffix(destination.suffix + ".tmp")

    try:
        # Copy file using aiofiles
        async with aiofiles.open(source, "rb") as src_f, aiofiles.open(
            temp_destination, "wb"
        ) as dst_f:
            while chunk := await src_f.read(8192):
                await dst_f.write(chunk)

        # Preserve metadata if requested
        if preserve_metadata:
            source_stat = await aiofiles.os.stat(source)
            await aiofiles.os.utime(
                temp_destination, (source_stat.st_atime, source_stat.st_mtime)
            )

        # Verify integrity if requested
        if verify_integrity:
            source_hash = await calculate_file_hash(source)
            dest_hash = await calculate_file_hash(temp_destination)

            if source_hash != dest_hash:
                await aiofiles.os.remove(temp_destination)
                raise FileIntegrityError(
                    f"File integrity check failed: {source} -> {destination}"
                )

        # Atomic move to final destination
        await aiofiles.os.rename(temp_destination, destination)

        logger.info(
            "File copied successfully",
            source=str(source),
            destination=str(destination),
            verified=verify_integrity,
        )

        return destination

    except Exception as e:
        # Clean up temporary file if it exists
        if await aiofiles.os.path.exists(temp_destination):
            await aiofiles.os.remove(temp_destination)
        raise FileOperationError(
            f"Failed to copy {source} to {destination}: {e}"
        ) from e


async def move_file_atomic(
    source: Path,
    destination: Path,
    *,
    verify_integrity: bool = True,
    create_backup: bool = False,
) -> Path:
    """Move file atomically with optional backup.

    Args:
        source: Source file path
        destination: Destination file path
        verify_integrity: Whether to verify file integrity
        create_backup: Whether to create a backup of destination if it exists

    Returns:
        Path to the moved file

    Raises:
        FileNotFoundError: If source file doesn't exist
        FileOperationError: If move operation fails
    """
    if not await aiofiles.os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")

    # Ensure destination directory exists
    await ensure_directory(destination.parent)

    # Create backup if requested and destination exists
    backup_path = None
    if create_backup and await aiofiles.os.path.exists(destination):
        backup_path = destination.with_suffix(destination.suffix + ".backup")
        await copy_file_atomic(destination, backup_path, verify_integrity=False)
        logger.debug(
            "Created backup", original=str(destination), backup=str(backup_path)
        )

    try:
        # Try atomic move first (works if source and dest are on same filesystem)
        await aiofiles.os.rename(source, destination)
        logger.info(
            "File moved atomically", source=str(source), destination=str(destination)
        )

    except OSError:
        # Fall back to copy + delete for cross-filesystem moves
        logger.debug("Falling back to copy+delete for cross-filesystem move")

        await copy_file_atomic(source, destination, verify_integrity=verify_integrity)
        await aiofiles.os.remove(source)

        logger.info(
            "File moved via copy+delete",
            source=str(source),
            destination=str(destination),
        )

    return destination


async def scan_directory(
    directory: Path,
    *,
    pattern: str = "*",
    recursive: bool = True,
    include_files: bool = True,
    include_dirs: bool = False,
) -> AsyncGenerator[Path, None]:
    """Scan directory asynchronously yielding matching paths.

    Args:
        directory: Directory to scan
        pattern: Glob pattern to match
        recursive: Whether to scan recursively
        include_files: Whether to include files in results
        include_dirs: Whether to include directories in results

    Yields:
        Matching file/directory paths

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    if not await aiofiles.os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not await aiofiles.os.path.isdir(directory):
        raise FileOperationError(f"Path is not a directory: {directory}")

    try:
        if recursive:
            # Use Path.rglob for recursive scanning
            for path in directory.rglob(pattern):
                if (include_files and await aiofiles.os.path.isfile(path)) or (
                    include_dirs and await aiofiles.os.path.isdir(path)
                ):
                    yield path
        else:
            # Use Path.glob for non-recursive scanning
            for path in directory.glob(pattern):
                if (include_files and await aiofiles.os.path.isfile(path)) or (
                    include_dirs and await aiofiles.os.path.isdir(path)
                ):
                    yield path

    except OSError as e:
        logger.error("Error scanning directory", directory=str(directory), error=str(e))
        raise FileOperationError(f"Cannot scan directory {directory}: {e}") from e


async def get_directory_size(directory: Path) -> tuple[int, int]:
    """Calculate total size and file count of directory recursively.

    Args:
        directory: Directory to analyze

    Returns:
        Tuple of (total_size_bytes, file_count)

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    if not await aiofiles.os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    total_size = 0
    file_count = 0

    try:
        async for file_path in scan_directory(
            directory, recursive=True, include_files=True
        ):
            try:
                stat_result = await aiofiles.os.stat(file_path)
                total_size += stat_result.st_size
                file_count += 1
            except OSError:
                # Skip files that can't be accessed
                continue
    except FileOperationError:
        # Re-raise directory scanning errors
        raise

    logger.debug(
        "Directory size calculated",
        directory=str(directory),
        total_size=total_size,
        file_count=file_count,
    )

    return total_size, file_count


async def clean_empty_directories(root_directory: Path) -> int:
    """Remove empty directories recursively.

    Args:
        root_directory: Root directory to clean

    Returns:
        Number of directories removed

    Raises:
        FileNotFoundError: If root directory doesn't exist
    """
    if not await aiofiles.os.path.exists(root_directory):
        raise FileNotFoundError(f"Directory not found: {root_directory}")

    removed_count = 0

    # Collect all directories first (to avoid modification during iteration)
    directories = []
    async for dir_path in scan_directory(
        root_directory, recursive=True, include_files=False, include_dirs=True
    ):
        directories.append(dir_path)

    # Sort by depth (deepest first) to ensure we remove child dirs before parents
    directories.sort(key=lambda p: len(p.parts), reverse=True)

    for dir_path in directories:
        try:
            # Don't remove the root directory itself
            if dir_path == root_directory:
                continue

            # Check if directory is empty
            try:
                next(dir_path.iterdir())
                # Directory is not empty, skip
                continue
            except StopIteration:
                # Directory is empty, remove it
                await aiofiles.os.rmdir(dir_path)
                removed_count += 1
                logger.debug("Removed empty directory", path=str(dir_path))
        except OSError:
            # Skip directories that can't be removed
            continue

    logger.info(
        "Empty directory cleanup completed",
        root=str(root_directory),
        removed_count=removed_count,
    )

    return removed_count


async def safe_filename(filename: str, *, replacement: str = "_") -> str:
    """Create filesystem-safe filename.

    Args:
        filename: Original filename
        replacement: Character to replace unsafe characters with

    Returns:
        Safe filename
    """
    # Characters that are unsafe in filenames
    unsafe_chars = '<>:"/\\|?*'

    # Replace unsafe characters
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, replacement)

    # Remove leading/trailing whitespace and dots
    safe_name = safe_name.strip(". ")

    # Ensure filename is not empty
    if not safe_name:
        safe_name = "unnamed"

    # Truncate if too long (most filesystems have 255 char limit)
    if len(safe_name) > 255:
        safe_name = safe_name[:255]

    return safe_name


# Convenience functions for common file extensions
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".ogv",
    ".rm",
    ".rmvb",
    ".asf",
    ".ts",
}

SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".sup"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}


def is_video_file(file_path: Path) -> bool:
    """Check if file is a video file based on extension."""
    return file_path.suffix.lower() in VIDEO_EXTENSIONS


def is_subtitle_file(file_path: Path) -> bool:
    """Check if file is a subtitle file based on extension."""
    return file_path.suffix.lower() in SUBTITLE_EXTENSIONS


def is_image_file(file_path: Path) -> bool:
    """Check if file is an image file based on extension."""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS
