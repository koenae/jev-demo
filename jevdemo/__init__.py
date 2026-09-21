"""Shared demo logic for the TypeSafe Jev talk.

Every demo lives here as plain, synchronous functions that return data.
Printing and layout are left to `demos/` (rich CLI) and `presentation/` (marimo).
"""

from jevdemo.errors import DemoError, MissingKeyError, RecordingMissingError
from jevdemo.recording import Mode

__all__ = ["DemoError", "MissingKeyError", "Mode", "RecordingMissingError"]
