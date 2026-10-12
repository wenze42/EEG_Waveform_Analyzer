"""Shared logging helper built on the standard library logging module."""

import logging
import sys

from config import LOG_FORMAT, LOG_LEVEL


def _configure_root() -> logging.Logger:
    root = logging.getLogger("eeg")
    if root.handlers:
        return root

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=LOG_FORMAT,
        stream=sys.stdout,
    )
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    return root


logger = _configure_root()
