"""Type-safe formatting utilities for media files.

This module provides utilities for formatting movie and TV show names,
filenames, and directory structures according to the specified patterns.
"""

from __future__ import annotations

import re

import structlog

from smart_media_organizer.models.media_file import (
    AudioCodec,
    VideoCodec,
)
from smart_media_organizer.utils.file_ops import safe_filename

logger = structlog.get_logger(__name__)


class FormattingError(Exception):
    """Base exception for formatting errors."""


class InvalidFormatStringError(FormattingError):
    """Invalid format string error."""


def clean_title(title: str) -> str:
    """Clean and normalize a movie/TV show title.

    Args:
        title: Original title

    Returns:
        Cleaned title
    """
    if not title:
        return ""

    # Remove excessive whitespace
    cleaned = re.sub(r"\s+", " ", title.strip())

    # Remove common suffixes that don't belong in clean titles
    suffixes_to_remove = [
        r"\s*\(.*?\)\s*$",  # Remove parentheses at the end
        r"\s*\[.*?\]\s*$",  # Remove brackets at the end
        r"\s*\{.*?\}\s*$",  # Remove braces at the end
    ]

    for suffix_pattern in suffixes_to_remove:
        cleaned = re.sub(suffix_pattern, "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def handle_articles(title: str) -> str:
    """Move English articles to the end for better sorting.

    Args:
        title: Original title

    Returns:
        Title with articles moved to the end

    Examples:
        "The Matrix" -> "Matrix, The"
        "A Beautiful Mind" -> "Beautiful Mind, A"
        "An Education" -> "Education, An"
    """
    if not title:
        return ""

    # English articles to move
    articles = ["The", "A", "An"]

    for article in articles:
        pattern = rf"^{re.escape(article)}\s+"
        if re.match(pattern, title, re.IGNORECASE):
            # Move article to the end
            remaining = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()
            return f"{remaining}, {article}"

    return title


def format_year_range(start_year: int | None, end_year: int | None) -> str:
    """Format year range for TV shows.

    Args:
        start_year: Start year
        end_year: End year (None if ongoing)

    Returns:
        Formatted year range
    """
    if start_year is None:
        return "Unknown"

    if end_year is None or end_year == start_year:
        return str(start_year)

    return f"{start_year}-{end_year}"


def format_resolution(width: int | None, height: int | None) -> str:
    """Format video resolution string.

    Args:
        width: Video width in pixels
        height: Video height in pixels

    Returns:
        Formatted resolution string
    """
    if width and height:
        # Map common resolutions to standard names
        resolution_map = {
            (720, 480): "480p",
            (720, 576): "576p",
            (1280, 720): "720p",
            (1920, 1080): "1080p",
            (2560, 1440): "1440p",
            (3840, 2160): "2160p",
            (7680, 4320): "4320p",
        }

        if (width, height) in resolution_map:
            return resolution_map[(width, height)]

        # For non-standard resolutions, return the height-based format
        return f"{height}p"

    return "Unknown"


def format_audio_channels(channels: int | None) -> str:
    """Format audio channels string.

    Args:
        channels: Number of audio channels

    Returns:
        Formatted audio channels string
    """
    if channels is None:
        return "Unknown"

    channel_map = {
        1: "1.0",
        2: "2.0",
        6: "5.1",
        8: "7.1",
    }

    return channel_map.get(channels, f"{channels}.0")


def format_bit_depth(bit_depth: int | None) -> str:
    """Format video bit depth.

    Args:
        bit_depth: Video bit depth

    Returns:
        Formatted bit depth string
    """
    if bit_depth is None:
        return "8bit"

    return f"{bit_depth}bit"


def format_edition(edition: str | None) -> str:
    """Format edition string for movies.

    Args:
        edition: Edition information

    Returns:
        Formatted edition string (empty if None)
    """
    if not edition:
        return ""

    # Clean up common edition formats
    edition_cleaned = edition.strip()

    # Common edition patterns
    common_editions = [
        "Director's Cut",
        "Extended Cut",
        "Unrated",
        "Theatrical Cut",
        "Final Cut",
        "Special Edition",
        "Ultimate Edition",
        "Collector's Edition",
    ]

    # Try to match common patterns (case insensitive)
    for common in common_editions:
        if edition_cleaned.lower() == common.lower():
            return common

    return edition_cleaned


def format_season_episode(season: int | None, episode: int | None) -> str:
    """Format season and episode for TV shows.

    Args:
        season: Season number
        episode: Episode number

    Returns:
        Formatted season/episode string (e.g., "S01E05")
    """
    if season is None or episode is None:
        return "S00E00"

    return f"S{season:02d}E{episode:02d}"


def format_imdb_id(imdb_id: str | None) -> str:
    """Format IMDB ID.

    Args:
        imdb_id: IMDB ID (with or without 'tt' prefix)

    Returns:
        Formatted IMDB ID
    """
    if not imdb_id:
        return "unknown"

    # Ensure it starts with 'tt'
    if not imdb_id.startswith("tt"):
        return f"tt{imdb_id}"

    return imdb_id


def format_tmdb_id(tmdb_id: int | None) -> str:
    """Format TMDB ID.

    Args:
        tmdb_id: TMDB ID

    Returns:
        Formatted TMDB ID
    """
    if tmdb_id is None:
        return "unknown"

    return str(tmdb_id)


def format_movie_folder_name(
    original_title: str | None,
    title: str | None,
    year: int | None,
    edition: str | None = None,
    imdb_id: str | None = None,
    tmdb_id: int | None = None,
    *,
    handle_chinese: bool = True,
) -> str:
    """Format movie folder name according to the specified pattern.

    Pattern: [${originalTitle}]-[${title}](${edition})-${year}-${imdb}-${tmdb}
    For Chinese movies: [${title}]-${year}-${imdb}-${tmdb}

    Args:
        original_title: Original movie title
        title: Movie title
        year: Release year
        edition: Edition information
        imdb_id: IMDB ID
        tmdb_id: TMDB ID
        handle_chinese: Whether to use simplified format for Chinese titles

    Returns:
        Formatted folder name
    """
    # Clean titles
    original_clean = clean_title(original_title or "")
    title_clean = clean_title(title or "")

    # Use the best available title
    best_title = original_clean or title_clean or "Unknown Movie"

    # Check if this appears to be a Chinese movie (simplified format)
    is_chinese = handle_chinese and (
        bool(re.search(r"[\u4e00-\u9fff]", best_title))  # Contains Chinese characters
        or (original_clean and title_clean and original_clean == title_clean)
    )

    # Format components
    year_str = str(year) if year else "Unknown"
    edition_str = format_edition(edition)
    imdb_str = format_imdb_id(imdb_id)
    tmdb_str = format_tmdb_id(tmdb_id)

    if is_chinese:
        # Simplified format for Chinese movies
        folder_name = f"[{best_title}]-{year_str}-{imdb_str}-{tmdb_str}"
    else:
        # Full format for non-Chinese movies
        if original_clean and title_clean and original_clean != title_clean:
            # Both titles available and different
            title_part = f"[{original_clean}]-[{title_clean}]"
        else:
            # Use single title
            title_part = f"[{best_title}]"

        if edition_str:
            title_part += f"({edition_str})"

        folder_name = f"{title_part}-{year_str}-{imdb_str}-{tmdb_str}"

    # Apply article handling for better sorting
    folder_name = handle_articles(folder_name)

    # Make filename safe
    return safe_filename(folder_name)


async def format_movie_file_name(
    original_title: str | None,
    title: str | None,
    year: int | None,
    edition: str | None = None,
    video_resolution: str | None = None,
    video_format: str | None = None,
    video_codec: VideoCodec | None = None,
    bit_depth: int | None = None,
    audio_codec: AudioCodec | None = None,
    audio_channels: int | None = None,
    file_extension: str | None = None,
    *,
    handle_chinese: bool = True,
) -> str:
    """Format movie file name according to the specified pattern.

    Pattern: [${originalTitle}]-[${title}](${edition})-${year}-${videoResolution}-
             ${videoFormat}-${videoCodec}-${videoBitDepth}bit-${audioCodec}-${audioChannels}

    Args:
        original_title: Original movie title
        title: Movie title
        year: Release year
        edition: Edition information
        video_resolution: Video resolution
        video_format: Video source format
        video_codec: Video codec
        bit_depth: Video bit depth
        audio_codec: Audio codec
        audio_channels: Number of audio channels
        file_extension: File extension
        handle_chinese: Whether to use simplified format for Chinese titles

    Returns:
        Formatted file name
    """
    # Clean titles
    original_clean = clean_title(original_title or "")
    title_clean = clean_title(title or "")

    # Use the best available title
    best_title = original_clean or title_clean or "Unknown Movie"

    # Check if this appears to be a Chinese movie
    is_chinese = handle_chinese and (
        bool(re.search(r"[\u4e00-\u9fff]", best_title))
        or (original_clean and title_clean and original_clean == title_clean)
    )

    # Format title part
    if is_chinese:
        title_part = f"[{best_title}]"
    else:
        if original_clean and title_clean and original_clean != title_clean:
            title_part = f"[{original_clean}]-[{title_clean}]"
        else:
            title_part = f"[{best_title}]"

    # Add edition if available
    edition_str = format_edition(edition)
    if edition_str:
        title_part += f"({edition_str})"

    # Format other components
    year_str = str(year) if year else "Unknown"
    resolution_str = video_resolution or "Unknown"
    format_str = video_format or "Unknown"
    codec_str = video_codec.value if video_codec else "unknown"
    bit_depth_str = format_bit_depth(bit_depth)
    audio_codec_str = audio_codec.value if audio_codec else "unknown"
    audio_channels_str = format_audio_channels(audio_channels)

    # Combine all parts
    filename = (
        f"{title_part}-{year_str}-{resolution_str}-{format_str}-"
        f"{codec_str}-{bit_depth_str}-{audio_codec_str}-{audio_channels_str}"
    )

    # Add file extension
    if file_extension:
        if not file_extension.startswith("."):
            file_extension = f".{file_extension}"
        filename += file_extension

    # Make filename safe
    return await safe_filename(filename)


def format_tv_show_folder_name(
    show_original_title: str | None,
    show_title: str | None,
    show_year: int | None,
    show_imdb_id: str | None = None,
    show_tmdb_id: int | None = None,
) -> str:
    """Format TV show folder name according to the specified pattern.

    Pattern: [${showOriginalTitle}]-[${showTitle}]-${showYear}-${showImdb}-${showTmdb}

    Args:
        show_original_title: Original show title
        show_title: Show title
        show_year: Show start year
        show_imdb_id: IMDB ID
        show_tmdb_id: TMDB ID

    Returns:
        Formatted folder name
    """
    # Clean titles
    original_clean = clean_title(show_original_title or "")
    title_clean = clean_title(show_title or "")

    # Use the best available title
    best_title = original_clean or title_clean or "Unknown Show"

    # Format title part
    if original_clean and title_clean and original_clean != title_clean:
        title_part = f"[{original_clean}]-[{title_clean}]"
    else:
        title_part = f"[{best_title}]"

    # Format other components
    year_str = str(show_year) if show_year else "Unknown"
    imdb_str = format_imdb_id(show_imdb_id)
    tmdb_str = format_tmdb_id(show_tmdb_id)

    folder_name = f"{title_part}-{year_str}-{imdb_str}-{tmdb_str}"

    # Apply article handling for better sorting
    folder_name = handle_articles(folder_name)

    # Make filename safe
    return safe_filename(folder_name)


def format_tv_season_folder_name(season_number: int | None) -> str:
    """Format TV season folder name.

    Pattern: Season-${seasonNr2}

    Args:
        season_number: Season number

    Returns:
        Formatted season folder name
    """
    if season_number is None:
        return "Season-00"

    return f"Season-{season_number:02d}"


async def format_tv_episode_file_name(
    show_original_title: str | None,
    show_title: str | None,
    season_number: int | None,
    episode_number: int | None,
    episode_original_title: str | None = None,
    episode_title: str | None = None,
    video_format: str | None = None,
    video_codec: VideoCodec | None = None,
    bit_depth: int | None = None,
    audio_codec: AudioCodec | None = None,
    audio_channels: int | None = None,
    file_extension: str | None = None,
) -> str:
    """Format TV episode file name according to the specified pattern.

    Pattern: [${showOriginalTitle}]-S${seasonNr2}E${episodeNr2}-[${originalTitle}]-
             [${title}]-${videoFormat}-${videoCodec}-${videoBitDepth}bit-${audioCodec}-${audioChannels}

    Args:
        show_original_title: Original show title
        show_title: Show title
        season_number: Season number
        episode_number: Episode number
        episode_original_title: Original episode title
        episode_title: Episode title
        video_format: Video source format
        video_codec: Video codec
        bit_depth: Video bit depth
        audio_codec: Audio codec
        audio_channels: Number of audio channels
        file_extension: File extension

    Returns:
        Formatted file name
    """
    # Clean show title
    show_original_clean = clean_title(show_original_title or "")
    show_title_clean = clean_title(show_title or "")
    best_show_title = show_original_clean or show_title_clean or "Unknown Show"

    # Clean episode titles
    episode_original_clean = clean_title(episode_original_title or "")
    episode_title_clean = clean_title(episode_title or "")

    # Format show and episode part
    season_episode = format_season_episode(season_number, episode_number)
    show_part = f"[{best_show_title}]-{season_episode}"

    # Add episode titles if available
    if episode_original_clean or episode_title_clean:
        if (
            episode_original_clean
            and episode_title_clean
            and episode_original_clean != episode_title_clean
        ):
            episode_part = f"-[{episode_original_clean}]-[{episode_title_clean}]"
        else:
            best_episode_title = episode_original_clean or episode_title_clean
            episode_part = f"-[{best_episode_title}]"
    else:
        episode_part = ""

    # Format technical components
    format_str = video_format or "Unknown"
    codec_str = video_codec.value if video_codec else "unknown"
    bit_depth_str = format_bit_depth(bit_depth)
    audio_codec_str = audio_codec.value if audio_codec else "unknown"
    audio_channels_str = format_audio_channels(audio_channels)

    # Combine all parts
    filename = (
        f"{show_part}{episode_part}-{format_str}-{codec_str}-"
        f"{bit_depth_str}-{audio_codec_str}-{audio_channels_str}"
    )

    # Add file extension
    if file_extension:
        if not file_extension.startswith("."):
            file_extension = f".{file_extension}"
        filename += file_extension

    # Make filename safe
    return await safe_filename(filename)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted file size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def format_duration(seconds: int | None) -> str:
    """Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (HH:MM:SS)
    """
    if seconds is None:
        return "Unknown"

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix
