from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import logs_dir


def setup_logging(name: str = "mynewsalarm") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_file: Path = logs_dir() / "mynewsalarm.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    stderr = logging.StreamHandler()
    stderr.setFormatter(formatter)
    logger.addHandler(stderr)

    return logger
