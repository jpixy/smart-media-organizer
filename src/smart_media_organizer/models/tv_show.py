"""TV show data models using Pydantic.

This module defines data structures for representing TV shows,
seasons, episodes, and related metadata.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from smart_media_organizer.models.media_file import MediaFile


class TVGenre(BaseModel):
    """TV show genre information."""

    id: int = Field(..., description="TMDB genre ID")
    name: str = Field(..., description="Genre name")


class TVCast(BaseModel):
    """TV show cast member information."""

    id: int = Field(..., description="TMDB person ID")
    name: str = Field(..., description="Actor name")
    character: str = Field(..., description="Character name")
    credit_id: str = Field(..., description="Credit ID")
    order: int = Field(..., description="Billing order")
    profile_path: str | None = Field(default=None, description="Profile image path")


class TVCrew(BaseModel):
    """TV show crew member information."""

    id: int = Field(..., description="TMDB person ID")
    name: str = Field(..., description="Crew member name")
    job: str = Field(..., description="Job title")
    department: str = Field(..., description="Department")
    credit_id: str = Field(..., description="Credit ID")
    profile_path: str | None = Field(default=None, description="Profile image path")


class Network(BaseModel):
    """TV network information."""

    id: int = Field(..., description="TMDB network ID")
    name: str = Field(..., description="Network name")
    logo_path: str | None = Field(default=None, description="Network logo path")
    origin_country: str = Field(..., description="Origin country")


class Season(BaseModel):
    """TV season information."""

    id: int = Field(..., description="TMDB season ID")
    season_number: int = Field(..., ge=0, description="Season number")
    name: str = Field(..., description="Season name")
    overview: str | None = Field(default=None, description="Season overview")
    air_date: date | None = Field(default=None, description="Season air date")
    episode_count: int = Field(..., ge=0, description="Number of episodes")
    poster_path: str | None = Field(default=None, description="Season poster path")

    class Config:
        """Pydantic configuration."""

        json_encoders = {date: lambda v: v.isoformat()}


class Episode(BaseModel):
    """TV episode information."""

    id: int = Field(..., description="TMDB episode ID")
    episode_number: int = Field(..., ge=1, description="Episode number")
    season_number: int = Field(..., ge=0, description="Season number")
    name: str = Field(..., description="Episode name")
    overview: str | None = Field(default=None, description="Episode overview")
    air_date: date | None = Field(default=None, description="Episode air date")
    runtime: int | None = Field(default=None, ge=0, description="Runtime in minutes")
    vote_average: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Average vote rating"
    )
    vote_count: int = Field(default=0, ge=0, description="Number of votes")
    still_path: str | None = Field(default=None, description="Episode still image path")

    # Cast and crew for this specific episode
    cast: list[TVCast] = Field(default_factory=list, description="Episode cast")
    crew: list[TVCrew] = Field(default_factory=list, description="Episode crew")

    @computed_field  # type: ignore
    @property
    def episode_code(self) -> str:
        """Get standard episode code (e.g., S01E05)."""
        return f"S{self.season_number:02d}E{self.episode_number:02d}"

    @computed_field  # type: ignore
    @property
    def runtime_formatted(self) -> str:
        """Get formatted runtime string."""
        if not self.runtime:
            return "Unknown"
        hours, minutes = divmod(self.runtime, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    class Config:
        """Pydantic configuration."""

        json_encoders = {date: lambda v: v.isoformat()}


class AITVIdentification(BaseModel):
    """AI identification result for a TV show episode."""

    # Show information
    show_chinese_title: str | None = Field(
        default=None, description="Chinese show title"
    )
    show_english_title: str | None = Field(
        default=None, description="English show title"
    )
    show_year: int | None = Field(
        default=None, ge=1900, le=2100, description="Show start year"
    )

    # Episode information
    season_number: int | None = Field(default=None, ge=0, description="Season number")
    episode_number: int | None = Field(default=None, ge=1, description="Episode number")
    episode_chinese_title: str | None = Field(
        default=None, description="Chinese episode title"
    )
    episode_english_title: str | None = Field(
        default=None, description="English episode title"
    )

    # AI metadata
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    model_used: str = Field(..., description="AI model that generated this result")
    processing_time: float = Field(
        ..., ge=0.0, description="Processing time in seconds"
    )
    raw_response: dict[str, Any] = Field(..., description="Raw AI response")

    # Processing metadata
    identified_at: datetime = Field(
        default_factory=datetime.now, description="Identification timestamp"
    )

    @computed_field  # type: ignore
    @property
    def best_show_title(self) -> str | None:
        """Get the best available show title."""
        return self.show_chinese_title or self.show_english_title

    @computed_field  # type: ignore
    @property
    def best_episode_title(self) -> str | None:
        """Get the best available episode title."""
        return self.episode_chinese_title or self.episode_english_title

    @computed_field  # type: ignore
    @property
    def episode_code(self) -> str | None:
        """Get standard episode code if available."""
        if self.season_number is not None and self.episode_number is not None:
            return f"S{self.season_number:02d}E{self.episode_number:02d}"
        return None

    @computed_field  # type: ignore
    @property
    def has_complete_episode_info(self) -> bool:
        """Check if complete episode information is available."""
        return (
            self.season_number is not None
            and self.episode_number is not None
            and self.best_show_title is not None
        )

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class TMDBTVShowInfo(BaseModel):
    """TMDB TV show information."""

    # Core show information
    id: int = Field(..., description="TMDB TV show ID")
    name: str = Field(..., description="TV show name")
    original_name: str = Field(..., description="Original TV show name")
    overview: str | None = Field(default=None, description="Show overview")
    tagline: str | None = Field(default=None, description="Show tagline")

    # Air information
    first_air_date: date | None = Field(default=None, description="First air date")
    last_air_date: date | None = Field(default=None, description="Last air date")
    in_production: bool = Field(default=False, description="Currently in production")
    status: str = Field(..., description="Show status")

    # Episode information
    number_of_episodes: int = Field(..., ge=0, description="Total number of episodes")
    number_of_seasons: int = Field(..., ge=0, description="Total number of seasons")
    episode_run_time: list[int] = Field(
        default_factory=list, description="Episode runtimes"
    )

    # Ratings and popularity
    vote_average: float = Field(..., ge=0.0, le=10.0, description="Average vote rating")
    vote_count: int = Field(..., ge=0, description="Number of votes")
    popularity: float = Field(..., ge=0.0, description="Popularity score")

    # Media paths
    poster_path: str | None = Field(default=None, description="Poster image path")
    backdrop_path: str | None = Field(default=None, description="Backdrop image path")

    # Classification
    adult: bool = Field(default=False, description="Adult content flag")
    type: str = Field(..., description="Show type")

    # Relationships
    genres: list[TVGenre] = Field(default_factory=list, description="TV show genres")
    networks: list[Network] = Field(
        default_factory=list, description="Broadcasting networks"
    )
    seasons: list[Season] = Field(default_factory=list, description="Show seasons")

    # Cast and crew (main/recurring)
    cast: list[TVCast] = Field(default_factory=list, description="Main cast")
    crew: list[TVCrew] = Field(default_factory=list, description="Main crew")

    # Processing metadata
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="Data fetch timestamp"
    )

    @computed_field  # type: ignore
    @property
    def start_year(self) -> int | None:
        """Get show start year."""
        return self.first_air_date.year if self.first_air_date else None

    @computed_field  # type: ignore
    @property
    def end_year(self) -> int | None:
        """Get show end year."""
        return self.last_air_date.year if self.last_air_date else None

    @computed_field  # type: ignore
    @property
    def year_range(self) -> str:
        """Get formatted year range."""
        start = self.start_year
        end = self.end_year
        if start and end and start != end:
            return f"{start}-{end}"
        elif start:
            return str(start)
        return "Unknown"

    @computed_field  # type: ignore
    @property
    def average_runtime(self) -> int | None:
        """Get average episode runtime."""
        if self.episode_run_time:
            return sum(self.episode_run_time) // len(self.episode_run_time)
        return None

    @computed_field  # type: ignore
    @property
    def creators(self) -> list[TVCrew]:
        """Get list of creators."""
        return [
            member
            for member in self.crew
            if member.job in ("Creator", "Executive Producer")
        ]

    @computed_field  # type: ignore
    @property
    def creator_names(self) -> list[str]:
        """Get list of creator names."""
        return [creator.name for creator in self.creators]

    @computed_field  # type: ignore
    @property
    def main_cast(self) -> list[TVCast]:
        """Get main cast (first 10 members)."""
        return sorted(self.cast, key=lambda x: x.order)[:10]

    @computed_field  # type: ignore
    @property
    def genre_names(self) -> list[str]:
        """Get list of genre names."""
        return [genre.name for genre in self.genres]

    @computed_field  # type: ignore
    @property
    def network_names(self) -> list[str]:
        """Get list of network names."""
        return [network.name for network in self.networks]

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class TVEpisode(BaseModel):
    """Complete TV episode representation with file, AI identification, and metadata."""

    # Core components
    media_file: MediaFile = Field(..., description="Media file information")
    ai_identification: AITVIdentification | None = Field(
        default=None, description="AI identification result"
    )
    show_info: TMDBTVShowInfo | None = Field(
        default=None, description="TMDB show information"
    )
    episode_info: Episode | None = Field(
        default=None, description="TMDB episode information"
    )

    # Organization information
    target_directory: str | None = Field(
        default=None, description="Target organization directory"
    )
    target_filename: str | None = Field(default=None, description="Target filename")

    # Processing metadata
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    @computed_field  # type: ignore
    @property
    def best_show_title(self) -> str | None:
        """Get the best available show title from all sources."""
        if self.show_info:
            return self.show_info.original_name or self.show_info.name
        if self.ai_identification:
            return self.ai_identification.best_show_title
        return None

    @computed_field  # type: ignore
    @property
    def best_episode_title(self) -> str | None:
        """Get the best available episode title from all sources."""
        if self.episode_info:
            return self.episode_info.name
        if self.ai_identification:
            return self.ai_identification.best_episode_title
        return None

    @computed_field  # type: ignore
    @property
    def best_year(self) -> int | None:
        """Get the best available year from all sources."""
        if self.show_info and self.show_info.start_year:
            return self.show_info.start_year
        if self.ai_identification and self.ai_identification.show_year:
            return self.ai_identification.show_year
        return None

    @computed_field  # type: ignore
    @property
    def season_number(self) -> int | None:
        """Get season number from best available source."""
        if self.episode_info:
            return self.episode_info.season_number
        if self.ai_identification:
            return self.ai_identification.season_number
        return None

    @computed_field  # type: ignore
    @property
    def episode_number(self) -> int | None:
        """Get episode number from best available source."""
        if self.episode_info:
            return self.episode_info.episode_number
        if self.ai_identification:
            return self.ai_identification.episode_number
        return None

    @computed_field  # type: ignore
    @property
    def episode_code(self) -> str | None:
        """Get standard episode code."""
        season = self.season_number
        episode = self.episode_number
        if season is not None and episode is not None:
            return f"S{season:02d}E{episode:02d}"
        return None

    @computed_field  # type: ignore
    @property
    def tmdb_show_id(self) -> int | None:
        """Get TMDB show ID if available."""
        return self.show_info.id if self.show_info else None

    @computed_field  # type: ignore
    @property
    def tmdb_episode_id(self) -> int | None:
        """Get TMDB episode ID if available."""
        return self.episode_info.id if self.episode_info else None

    @computed_field  # type: ignore
    @property
    def is_complete(self) -> bool:
        """Check if episode has complete information for organization."""
        return (
            self.ai_identification is not None
            and self.show_info is not None
            and self.best_show_title is not None
            and self.season_number is not None
            and self.episode_number is not None
        )

    @computed_field  # type: ignore
    @property
    def formatted_title(self) -> str:
        """Get formatted title for filename generation."""
        show_title = self.best_show_title or "Unknown Show"
        episode_code = self.episode_code or "Unknown"
        episode_title = self.best_episode_title

        if episode_title:
            return f"{show_title} {episode_code} - {episode_title}"
        return f"{show_title} {episode_code}"

    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with computed fields."""
        data = self.model_dump()
        # Add computed fields
        data.update(
            {
                "best_show_title": self.best_show_title,
                "best_episode_title": self.best_episode_title,
                "best_year": self.best_year,
                "season_number": self.season_number,
                "episode_number": self.episode_number,
                "episode_code": self.episode_code,
                "tmdb_show_id": self.tmdb_show_id,
                "tmdb_episode_id": self.tmdb_episode_id,
                "is_complete": self.is_complete,
                "formatted_title": self.formatted_title,
            }
        )
        return data

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
