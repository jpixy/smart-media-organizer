"""Smart Media Organizer - AI-powered media file organizer.

A modern Python application that uses AI to intelligently organize
movie and TV show files with proper metadata and directory structure.
"""

__version__ = "0.1.0"
__author__ = "Smart Media Organizer Team"
__email__ = "contact@example.com"

# Package-level imports for convenience
from smart_media_organizer.models.config import Settings, get_settings

__all__ = ["Settings", "get_settings", "__version__"]
