"""
Structured logging configuration for AegisHealth backend.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
) -> None:
    """
    Configure root logger with structured format.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        format_string: Optional custom format. Default includes timestamp, level, name, message.
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
