"""Movie data models using Pydantic.

This module defines data structures for representing movies,
including TMDB metadata and AI identification results.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from smart_media_organizer.models.media_file import MediaFile


class MovieGenre(BaseModel):
    """Movie genre information."""

    id: int = Field(..., description="TMDB genre ID")
    name: str = Field(..., description="Genre name")


class MovieCast(BaseModel):
    """Movie cast member information."""

    id: int = Field(..., description="TMDB person ID")
    name: str = Field(..., description="Actor name")
    character: str = Field(..., description="Character name")
    order: int = Field(..., description="Billing order")
    profile_path: str | None = Field(default=None, description="Profile image path")


class MovieCrew(BaseModel):
    """Movie crew member information."""

    id: int = Field(..., description="TMDB person ID")
    name: str = Field(..., description="Crew member name")
    job: str = Field(..., description="Job title")
    department: str = Field(..., description="Department")
    profile_path: str | None = Field(default=None, description="Profile image path")


class MovieCollection(BaseModel):
    """Movie collection information."""

    id: int = Field(..., description="TMDB collection ID")
    name: str = Field(..., description="Collection name")
    poster_path: str | None = Field(default=None, description="Collection poster path")
    backdrop_path: str | None = Field(
        default=None, description="Collection backdrop path"
    )


class ProductionCompany(BaseModel):
    """Production company information."""

    id: int = Field(..., description="TMDB company ID")
    name: str = Field(..., description="Company name")
    logo_path: str | None = Field(default=None, description="Company logo path")
    origin_country: str = Field(..., description="Origin country")


class SpokenLanguage(BaseModel):
    """Spoken language information."""

    iso_639_1: str = Field(..., description="ISO 639-1 language code")
    name: str = Field(..., description="Language name")
    english_name: str = Field(..., description="English language name")


class AIMovieIdentification(BaseModel):
    """AI identification result for a movie."""

    # Extracted information
    chinese_title: str | None = Field(default=None, description="Chinese movie title")
    english_title: str | None = Field(default=None, description="English movie title")
    year: int | None = Field(default=None, ge=1900, le=2100, description="Release year")
    edition: str | None = Field(
        default=None, description="Edition information (Director's Cut, etc.)"
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
    def best_title(self) -> str | None:
        """Get the best available title."""
        return self.chinese_title or self.english_title

    @computed_field  # type: ignore
    @property
    def has_year(self) -> bool:
        """Check if year information is available."""
        return self.year is not None

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class TMDBMovieInfo(BaseModel):
    """TMDB movie information."""

    # Core movie information
    id: int = Field(..., description="TMDB movie ID")
    imdb_id: str | None = Field(default=None, description="IMDB ID")
    title: str = Field(..., description="Movie title")
    original_title: str = Field(..., description="Original movie title")
    overview: str | None = Field(default=None, description="Movie overview/synopsis")
    tagline: str | None = Field(default=None, description="Movie tagline")

    # Release information
    release_date: date | None = Field(default=None, description="Release date")
    runtime: int | None = Field(default=None, ge=0, description="Runtime in minutes")

    # Ratings and popularity
    vote_average: float = Field(..., ge=0.0, le=10.0, description="Average vote rating")
    vote_count: int = Field(..., ge=0, description="Number of votes")
    popularity: float = Field(..., ge=0.0, description="Popularity score")

    # Media paths
    poster_path: str | None = Field(default=None, description="Poster image path")
    backdrop_path: str | None = Field(default=None, description="Backdrop image path")

    # Classification
    adult: bool = Field(default=False, description="Adult content flag")
    video: bool = Field(default=False, description="Video flag")

    # Status and budget
    status: str = Field(..., description="Movie status")
    budget: int = Field(default=0, ge=0, description="Budget in USD")
    revenue: int = Field(default=0, ge=0, description="Revenue in USD")

    # Relationships
    belongs_to_collection: MovieCollection | None = Field(
        default=None, description="Collection information"
    )
    genres: list[MovieGenre] = Field(default_factory=list, description="Movie genres")
    production_companies: list[ProductionCompany] = Field(
        default_factory=list, description="Production companies"
    )
    spoken_languages: list[SpokenLanguage] = Field(
        default_factory=list, description="Spoken languages"
    )

    # Cast and crew (if included)
    cast: list[MovieCast] = Field(default_factory=list, description="Movie cast")
    crew: list[MovieCrew] = Field(default_factory=list, description="Movie crew")

    # Processing metadata
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="Data fetch timestamp"
    )

    @computed_field  # type: ignore
    @property
    def release_year(self) -> int | None:
        """Get release year."""
        return self.release_date.year if self.release_date else None

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

    @computed_field  # type: ignore
    @property
    def directors(self) -> list[MovieCrew]:
        """Get list of directors."""
        return [member for member in self.crew if member.job == "Director"]

    @computed_field  # type: ignore
    @property
    def director_names(self) -> list[str]:
        """Get list of director names."""
        return [director.name for director in self.directors]

    @computed_field  # type: ignore
    @property
    def main_cast(self) -> list[MovieCast]:
        """Get main cast (first 10 members)."""
        return sorted(self.cast, key=lambda x: x.order)[:10]

    @computed_field  # type: ignore
    @property
    def genre_names(self) -> list[str]:
        """Get list of genre names."""
        return [genre.name for genre in self.genres]

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class Movie(BaseModel):
    """Complete movie representation with file, AI identification, and TMDB data."""

    # Core components
    media_file: MediaFile = Field(..., description="Media file information")
    ai_identification: AIMovieIdentification | None = Field(
        default=None, description="AI identification result"
    )
    tmdb_info: TMDBMovieInfo | None = Field(
        default=None, description="TMDB movie information"
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
    def best_title(self) -> str | None:
        """Get the best available title from all sources."""
        if self.tmdb_info:
            return self.tmdb_info.original_title or self.tmdb_info.title
        if self.ai_identification:
            return self.ai_identification.best_title
        return None

    @computed_field  # type: ignore
    @property
    def best_year(self) -> int | None:
        """Get the best available year from all sources."""
        if self.tmdb_info and self.tmdb_info.release_year:
            return self.tmdb_info.release_year
        if self.ai_identification and self.ai_identification.year:
            return self.ai_identification.year
        return None

    @computed_field  # type: ignore
    @property
    def imdb_id(self) -> str | None:
        """Get IMDB ID if available."""
        return self.tmdb_info.imdb_id if self.tmdb_info else None

    @computed_field  # type: ignore
    @property
    def tmdb_id(self) -> int | None:
        """Get TMDB ID if available."""
        return self.tmdb_info.id if self.tmdb_info else None

    @computed_field  # type: ignore
    @property
    def is_complete(self) -> bool:
        """Check if movie has complete information for organization."""
        return (
            self.ai_identification is not None
            and self.tmdb_info is not None
            and self.best_title is not None
            and self.best_year is not None
        )

    @computed_field  # type: ignore
    @property
    def formatted_title(self) -> str:
        """Get formatted title for filename generation."""
        title = self.best_title or "Unknown Movie"
        year = self.best_year
        if year:
            return f"{title} ({year})"
        return title

    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with computed fields."""
        data = self.model_dump()
        # Add computed fields
        data.update(
            {
                "best_title": self.best_title,
                "best_year": self.best_year,
                "imdb_id": self.imdb_id,
                "tmdb_id": self.tmdb_id,
                "is_complete": self.is_complete,
                "formatted_title": self.formatted_title,
            }
        )
        return data

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
