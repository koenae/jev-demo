"""Run this right before the talk. Checks keys, connectivity, latency and recordings.

    uv run python scripts/preflight.py            # everything
    uv run python scripts/preflight.py --no-llm   # skip the LLM check (demo 3 offline)

Exit code 0 = all green, 1 = something to fix (details in the table).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from jevdemo import agent_gate, confidence_gate, smart_if  # noqa: E402
from jevdemo.config import ENV_FILE, ROOT, load_env, llm_settings, package_versions  # noqa: E402
from jevdemo.errors import DemoError  # noqa: E402
from jevdemo.jev import make_client, timed_system_one  # noqa: E402
from jevdemo.latency import LatencyStats  # noqa: E402
from jevdemo.recording import SOURCE_PLACEHOLDER, recording_path  # noqa: E402

console = Console()
Row = tuple[str, bool, str]  # (check, ok, detail)


def check_env() -> list[Row]:
    load_env()
    rows: list[Row] = [(".env file", ENV_FILE.exists(), str(ENV_FILE) if ENV_FILE.exists() else "missing (copy .env.example)")]
    rows.append(("TYPESAFE_API_KEY", bool(os.environ.get("TYPESAFE_API_KEY", "").strip()), "set" if os.environ.get("TYPESAFE_API_KEY") else "missing"))
    try:
        settings = llm_settings()
        rows.append(("LLM config (demo 3)", True, settings.label))
    except DemoError as error:
        rows.append(("LLM config (demo 3)", False, error.message))
    return rows


def check_typesafe(calls: int) -> list[Row]:
    rows: list[Row] = []
    try:
        with make_client(timeout=10.0) as client:
            started = perf_counter()
            models = client.models.list()
            ms = (perf_counter() - started) * 1000
            names = ", ".join(m.name for m in models.models)
            rows.append(("TypeSafe /v1/models", True, f"{ms:.0f} ms - {names}"))
            samples = [
                timed_system_one(client, {"ticket": smart_if.TICKET}, smart_if.QUESTIONS)[1]
                for _ in range(calls)
            ]
            stats = LatencyStats.of(samples)
            rows.append(
                ("TypeSafe /v1/systemone", stats.p95_ms < 2000,
                 f"{calls} calls: median {stats.median_ms:.0f} ms, p95 {stats.p95_ms:.0f} ms")
            )
    except Exception as error:  # noqa: BLE001
        rows.append(("TypeSafe API", False, str(error).splitlines()[0]))
    return rows


def check_llm() -> list[Row]:
    try:
        from jevdemo.config import build_chat_model

        settings = llm_settings()
        llm = build_chat_model(settings)
        started = perf_counter()
        reply = llm.invoke("Reply with the single word: pong")
        ms = (perf_counter() - started) * 1000
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        return [(f"LLM {settings.label}", True, f"{ms:.0f} ms - {text.strip()[:40]!r}")]
    except Exception as error:  # noqa: BLE001
        return [("LLM (demo 3)", False, str(error).splitlines()[0][:100])]


def check_recordings() -> list[Row]:
    rows: list[Row] = []
    for name in (
        smart_if.RECORDING, confidence_gate.RECORDING, agent_gate.RECORDING, agent_gate.COMPARISON,
        "demo4_head_to_head", "demo5_one_call_vs_samples", "latency_benchmark",
    ):
        path = recording_path(name)
        if not path.exists():
            rows.append((f"recording {name}", False, "missing - run the demo with --record"))
            continue
        envelope = json.loads(path.read_text(encoding="utf-8"))
        placeholder = envelope.get("source") == SOURCE_PLACEHOLDER
        rows.append(
            (f"recording {name}", not placeholder,
             "SYNTHETIC PLACEHOLDER - record the real thing" if placeholder
             else f"real, recorded {envelope.get('recorded_at', '?')}")
        )
    return rows


def check_exports() -> list[Row]:
    rows = []
    for name in ("talk.html", "talk.pdf"):
        path = ROOT / "exports" / name
        rows.append((f"export {name}", path.exists(), f"{path.stat().st_size // 1024} kB" if path.exists() else "missing (see README: export)"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="pre-talk checks")
    parser.add_argument("--no-llm", action="store_true", help="skip the LLM round-trip")
    parser.add_argument("--calls", type=int, default=5, help="TypeSafe latency samples")
    args = parser.parse_args()

    rows = check_env()
    rows += check_typesafe(args.calls)
    rows += [] if args.no_llm else check_llm()
    rows += check_recordings()
    rows += check_exports()

    table = Table(title="Preflight", show_lines=False)
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for name, ok, detail in rows:
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]", detail)
    console.print(table)
    versions = ", ".join(f"{k} {v}" for k, v in package_versions().items())
    console.print(f"[dim]{versions}[/dim]")
    failed = [r for r in rows if not r[1]]
    if failed:
        console.print(f"[red]{len(failed)} check(s) failed.[/red] Offline mode still works if the recordings are real.")
        return 1
    console.print("[green]All clear. Break a leg.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
