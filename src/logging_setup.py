"""One shared logging helper for console + logs/ plain-text files."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(name: str = "wnba-props") -> logging.Logger:
    """Configure root project logging once; return the named logger."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_dir / "wnba-props.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(console)

    logger.propagate = False
    return logger
