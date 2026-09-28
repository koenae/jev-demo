"""Shared logic for the Jev vs gpt-5-mini demos.

Every demo lives here as plain, synchronous functions that return data.
Printing is left to the CLIs in `demos/`.
"""

from jevdemo.errors import DemoError, MissingKeyError, RecordingMissingError
from jevdemo.recording import Mode

__all__ = ["DemoError", "MissingKeyError", "Mode", "RecordingMissingError"]
