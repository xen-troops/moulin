# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 EPAM Systems


import logging
import sys


class ColoredFormatter(logging.Formatter):
    # Define color codes
    COLORS = {
        'DEBUG': '\033[94m',      # Blue
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[1;91m'  # Bold Red
    }
    RESET = '\033[0m'  # Reset color

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)

        if sys.stderr.isatty():
            return f"{log_color}{message}{self.RESET}"
        else:
            return message


def build_handlers(log_format: str) -> list:
    formatter = ColoredFormatter(log_format)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return [handler]
