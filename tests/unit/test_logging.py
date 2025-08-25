"""Unit tests for logging system.

This module tests the structlog logging configuration.
"""

from __future__ import annotations

import structlog

from smart_media_organizer.utils.logging import get_logger, setup_development_logging


class TestLoggingSetup:
    """Test logging system setup."""

    def test_setup_development_logging(self) -> None:
        """Test development logging setup."""
        setup_development_logging()

        # Check that structlog is configured
        logger = structlog.get_logger("test")
        assert logger is not None

        # Check that we can log messages
        logger.info("Test message", test_key="test_value")

    def test_get_logger(self) -> None:
        """Test getting a logger instance."""
        setup_development_logging()

        logger = get_logger("test_module")
        assert logger is not None

        # Test logging with context
        logger.debug("Debug message", context="test")
        logger.info("Info message", user_id=123)
        logger.warning("Warning message", status="warning")
        logger.error("Error message", error_code=500)

    def test_logger_context(self) -> None:
        """Test logger context preservation."""
        setup_development_logging()

        logger = get_logger("context_test")

        # Test with various data types
        test_contexts = [
            {"string_key": "string_value"},
            {"int_key": 42},
            {"float_key": 3.14},
            {"bool_key": True},
            {"list_key": [1, 2, 3]},
            {"dict_key": {"nested": "value"}},
        ]

        for context in test_contexts:
            logger.info("Context test", **context)

    def test_logger_with_exception(self) -> None:
        """Test logging with exception information."""
        setup_development_logging()

        logger = get_logger("exception_test")

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("An error occurred", exc_info=True)

    def test_logging_levels(self) -> None:
        """Test different logging levels."""
        setup_development_logging()

        logger = get_logger("level_test")

        # Test all logging levels
        logger.debug("Debug level message")
        logger.info("Info level message")
        logger.warning("Warning level message")
        logger.error("Error level message")
        logger.critical("Critical level message")


class TestLoggerIntegration:
    """Test logger integration with application components."""

    def test_logger_in_function(self) -> None:
        """Test using logger in a function."""
        setup_development_logging()

        def sample_function(value: int) -> int:
            logger = get_logger(__name__)
            logger.info(
                "Function called", function="sample_function", input_value=value
            )

            result = value * 2
            logger.debug("Calculation result", result=result)

            return result

        result = sample_function(21)
        assert result == 42

    def test_logger_performance(self) -> None:
        """Test logger performance with many messages."""
        setup_development_logging()

        logger = get_logger("performance_test")

        # Log many messages quickly
        for i in range(100):
            logger.debug(f"Message {i}", iteration=i, batch="performance_test")

    def test_logger_with_rich_formatting(self) -> None:
        """Test logger with Rich formatting features."""
        setup_development_logging()

        logger = get_logger("rich_test")

        # Test with various message formats
        logger.info("✅ Success message", status="success")
        logger.warning("⚠️ Warning message", status="warning")
        logger.error("❌ Error message", status="error")

        # Test with progress-like messages
        logger.info("Processing files", completed=5, total=10, progress=0.5)


class TestLoggingConfiguration:
    """Test logging configuration options."""

    def test_logger_name_handling(self) -> None:
        """Test logger name handling."""
        setup_development_logging()

        # Test with module name
        logger1 = get_logger("smart_media_organizer.test")
        logger1.info("Module logger test")

        # Test with simple name
        logger2 = get_logger("simple")
        logger2.info("Simple logger test")

        # Test with None (should work)
        logger3 = get_logger(None)
        logger3.info("None logger test")

    def test_context_preservation(self) -> None:
        """Test that context is preserved across log calls."""
        setup_development_logging()

        logger = get_logger("context_preservation")

        # Test that each log call is independent
        logger.info("First message", request_id="123", user="alice")
        logger.info("Second message", request_id="456", user="bob")
        logger.info("Third message", session="abc", action="login")

    def test_structured_data_types(self) -> None:
        """Test logging with various structured data types."""
        setup_development_logging()

        logger = get_logger("structured_test")

        # Test complex data structures
        complex_data = {
            "user": {
                "id": 123,
                "name": "Test User",
                "preferences": ["dark_mode", "notifications"],
            },
            "metadata": {
                "timestamp": "2024-01-01T00:00:00Z",
                "version": "1.0.0",
                "environment": "test",
            },
        }

        logger.info("Complex data test", data=complex_data)

        # Test with lists
        file_list = ["movie1.mkv", "movie2.mp4", "show.s01e01.mkv"]
        logger.info("File processing", files=file_list, count=len(file_list))


class TestErrorScenarios:
    """Test error scenarios and edge cases."""

    def test_logging_with_none_values(self) -> None:
        """Test logging with None values."""
        setup_development_logging()

        logger = get_logger("none_test")

        logger.info("None value test", value=None, result=None)

    def test_logging_with_empty_values(self) -> None:
        """Test logging with empty values."""
        setup_development_logging()

        logger = get_logger("empty_test")

        logger.info("Empty value test", empty_string="", empty_list=[], empty_dict={})

    def test_logging_without_context(self) -> None:
        """Test logging without additional context."""
        setup_development_logging()

        logger = get_logger("minimal_test")

        logger.info("Minimal message")
        logger.error("Error without context")
        logger.debug("Debug without context")
