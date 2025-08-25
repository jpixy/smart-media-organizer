"""Structured logging configuration using structlog and Rich.

This module provides a modern, structured logging setup that can output
to console (with Rich formatting) or JSON for production environments.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
import structlog

from smart_media_organizer.models.config import LogFormat, Settings


def setup_logging(settings: Settings) -> None:
    """Set up structured logging with the specified configuration.

    Args:
        settings: Application settings containing logging configuration
    """
    # Configure standard library logging
    logging.basicConfig(
        level=settings.get_logging_level(),
        format="%(message)s",
        handlers=[],
    )

    # Set up processors based on format
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add custom context processor
    processors.append(_add_context_processor)

    # Configure output format
    if settings.log_format == LogFormat.JSON or settings.structured_logging:
        # JSON output for production/structured logging
        processors.append(structlog.processors.JSONRenderer())
        handler = _create_json_handler(settings)
    else:
        # Rich console output for development
        processors.append(_create_rich_renderer())
        handler = _create_rich_handler(settings)

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def _create_rich_handler(settings: Settings) -> RichHandler:
    """Create a Rich console handler for beautiful terminal output."""
    console = Console(
        stderr=True,
        force_terminal=True,
        width=120,
    )

    return RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=settings.debug,
        rich_tracebacks=True,
        tracebacks_show_locals=settings.debug,
        markup=True,
    )


def _create_json_handler(settings: Settings) -> logging.Handler:
    """Create a JSON handler for structured output."""
    if settings.log_file:
        # Log to file
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(settings.log_file)
    else:
        # Log to stderr
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def _create_rich_renderer() -> Any:
    """Create a Rich renderer for colored console output."""

    def rich_renderer(
        _logger: Any, _method_name: str, event_dict: dict[str, Any]
    ) -> str:
        """Render log entry with Rich formatting."""
        # Extract standard fields
        level = event_dict.pop("level", "info").upper()
        timestamp = event_dict.pop("timestamp", "")
        logger_name = event_dict.pop("logger", "")
        event = event_dict.pop("event", "")

        # Color coding for levels
        level_colors = {
            "DEBUG": "dim blue",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = level_colors.get(level, "white")

        # Build message parts
        parts = []

        # Add timestamp if available
        if timestamp:
            parts.append(f"[dim]{timestamp}[/dim]")

        # Add level with color
        parts.append(f"[{color}]{level:8}[/{color}]")

        # Add logger name
        if logger_name:
            parts.append(f"[dim]{logger_name}[/dim]")

        # Add main event message
        parts.append(f"[bold]{event}[/bold]")

        # Add extra context fields
        if event_dict:
            context_parts = []
            for key, value in event_dict.items():
                if key not in ("exc_info", "stack_info"):
                    context_parts.append(f"[cyan]{key}[/cyan]=[yellow]{value}[/yellow]")

            if context_parts:
                parts.append(f"[dim]({', '.join(context_parts)})[/dim]")

        return " ".join(parts)

    return rich_renderer


def _add_context_processor(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add application context to log entries."""
    # Add application info
    event_dict["app"] = "smart-media-organizer"
    event_dict["version"] = "0.1.0"

    return event_dict


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller's module name)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def setup_development_logging() -> None:
    """Quick setup for development with Rich console output."""
    from smart_media_organizer.models.config import LogFormat, LogLevel

    # Create minimal settings for development
    class DevSettings:
        log_level = LogLevel.DEBUG
        log_format = LogFormat.CONSOLE
        log_file = None
        structured_logging = False
        debug = True

        def get_logging_level(self) -> int:
            return logging.DEBUG

    setup_logging(DevSettings())


# Convenience logger for immediate use
logger = structlog.get_logger(__name__)
