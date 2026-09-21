"""Shared bits for the thin CLI wrappers: argument parsing, badges and error panels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python demos/x.py` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from jevdemo.errors import DemoError  # noqa: E402
from jevdemo.recording import Mode, parse_mode  # noqa: E402

console = Console()


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--record", action="store_true", help="call the API and save the response to recordings/"
    )
    group.add_argument(
        "--offline", action="store_true", help="replay the saved recording, no network needed"
    )
    return parser.parse_args()


def mode_from(args: argparse.Namespace) -> Mode:
    return parse_mode(record=args.record, offline=args.offline)


def origin_badge(origin: str) -> Text:
    if origin == "live":
        return Text(" LIVE ", style="bold white on green")
    if origin == "recording":
        return Text(" OFFLINE: recorded API response ", style="bold black on yellow")
    return Text(" OFFLINE: SYNTHETIC PLACEHOLDER, not real API data ", style="bold white on red")


def print_error(error: Exception) -> None:
    if isinstance(error, DemoError):
        body = Text(error.message, style="bold red")
        if error.hint:
            body.append("\n\n" + error.hint, style="yellow")
    else:
        body = Text(f"{type(error).__name__}: {error}", style="bold red")
        body.append("\n\nTip: run with --offline to replay the recording.", style="yellow")
    console.print(Panel(body, title="Demo failed", border_style="red"))


def bar(probability: float, width: int = 20) -> str:
    filled = round(probability * width)
    return "█" * filled + "░" * (width - filled)


def run_cli(description: str, main) -> None:
    """Parse args, run `main(mode)`, and turn exceptions into a clean panel + exit code 1."""
    args = parse_args(description)
    try:
        main(mode_from(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:  # noqa: BLE001 - the CLI must never dump a traceback on stage
        print_error(error)
        sys.exit(1)
