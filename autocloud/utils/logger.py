"""Logging setup for AutoCloud."""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class AutoCloudLogger:
    """Custom logger for AutoCloud."""

    def __init__(self, name: str = "autocloud", log_dir: Optional[Path] = None):
        """Initialize logger."""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.log_dir = log_dir

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(message)s"  # Simple format for console
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def add_file_handler(self, log_file: Path, level: int = logging.DEBUG) -> None:
        """Add file handler for detailed logging."""
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self.logger


def get_project_logger(project_dir: Path, log_type: str = "deployment") -> logging.Logger:
    """Get a logger for a specific project."""
    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{log_type}_{timestamp}.log"

    logger = AutoCloudLogger(f"autocloud.{project_dir.name}")
    logger.add_file_handler(log_file)

    return logger.get_logger()


def get_logger(name: str = "autocloud") -> logging.Logger:
    """Get a basic logger instance."""
    logger = AutoCloudLogger(name)
    return logger.get_logger()
