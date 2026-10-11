"""
DharmaFlow AI — Structured Logging Setup
Rotating file handler + coloured console output.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


_CONFIGURED = False


def setup_logging(
    level: str = "INFO",
    logs_dir: Path | None = None,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(_ColourFormatter(log_format))

    handlers: list[logging.Handler] = [console]

    # Rotating file handler
    if logs_dir:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "dharmaflow.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    logging.basicConfig(level=numeric_level, handlers=handlers, force=True)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "PIL", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class _ColourFormatter(logging.Formatter):
    """ANSI colour codes for console output."""
    _COLOURS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname}{self._RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call setup_logging() first."""
    return logging.getLogger(name)
