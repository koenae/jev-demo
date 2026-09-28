"""Errors with a human-readable hint, so the CLI can show a clean message."""

from __future__ import annotations


class DemoError(Exception):
    """A demo could not run. `hint` tells the presenter what to do next."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message if not self.hint else f"{self.message}\nHint: {self.hint}"


class MissingKeyError(DemoError):
    """A required API key or setting is not configured."""


class RecordingMissingError(DemoError):
    """Offline mode was requested but no recording exists for this demo."""
