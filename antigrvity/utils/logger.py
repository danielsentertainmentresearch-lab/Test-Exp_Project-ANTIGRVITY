"""Structured logging utilities for Project ANTIGRVITY."""

import logging
import sys
import os
import json
from datetime import datetime
from typing import Optional

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# Check if colors should be enabled
USE_COLORS = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


class AntigrvityFormatter(logging.Formatter):
    """Custom formatter with subsystem tags and colorization."""

    LEVEL_COLORS = {
        logging.DEBUG: DIM,
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: f"{BOLD}{RED}",
    }

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        subsystem = getattr(record, "subsystem", record.name.split(".")[-1].upper())
        level_name = record.levelname.ljust(5)

        if USE_COLORS:
            color = self.LEVEL_COLORS.get(record.levelno, RESET)
            prefix = f"{DIM}{timestamp}{RESET} {color}[{level_name}]{RESET} {BOLD}{BLUE}[{subsystem}]{RESET}"
            message = f"{color}{record.getMessage()}{RESET}"
        else:
            prefix = f"{timestamp} [{level_name}] [{subsystem}]"
            message = record.getMessage()

        if record.exc_info:
            text = f"{prefix} {message}\n{self.formatException(record.exc_info)}"
        else:
            text = f"{prefix} {message}"
        return text


class JsonFormatter(logging.Formatter):
    """JSON output formatter for automated telemetry and logs."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "subsystem": getattr(record, "subsystem", record.name),
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def get_logger(name: str = "antigrvity", json_mode: bool = False, level: int = logging.INFO) -> logging.Logger:
    """Obtain or configure a logger for a specific subsystem."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter() if json_mode else AntigrvityFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
