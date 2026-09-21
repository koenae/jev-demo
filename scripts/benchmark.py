"""Measure Jev latency from where you sit: median and p95 over N calls per demo.

    uv run python scripts/benchmark.py --calls 10 --location "Belgium (Ghent), fibre"

Writes recordings/latency_benchmark.json, which slide 10 and TALK_NOTES.md use.
Demo 3's number is the gate classification only (one TypeSafe call per tool call),
measured through langchain-typesafe's TypeSafeClassifier, not the LLM round-trip.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from demos._cli import print_error  # noqa: E402
from jevdemo import agent_gate, confidence_gate, smart_if  # noqa: E402
from jevdemo.jev import make_client, timed_system_one  # noqa: E402
from jevdemo.latency import LatencyStats  # noqa: E402
from jevdemo.recording import save_recording  # noqa: E402

BENCHMARK = "latency_benchmark"
console = Console()


def bench_demo1(client, calls: int) -> list[float]:
    return [
        timed_system_one(client, {"ticket": smart_if.TICKET}, smart_if.QUESTIONS)[1]
        for _ in range(calls)
    ]


def bench_demo2(client, calls: int) -> list[float]:
    tickets = confidence_gate.TICKETS
    return [
        timed_system_one(client, {"ticket": tickets[i % len(tickets)].text}, confidence_gate.QUESTIONS)[1]
        for i in range(calls)
    ]


def bench_demo3(calls: int) -> list[float]:
    from langchain_typesafe import TypeSafeClassifier

    from jevdemo.config import typesafe_api_key

    classifier = TypeSafeClassifier(api_key=typesafe_api_key(), timeout=15.0)
    state = {
        "tool_call": {"name": "run_sql", "args": {"query": "DROP TABLE orders_archive_2023", "database": "orders-production"}},
        "tool_description": agent_gate.run_sql.description,
        "recent_messages": [{"role": "user", "content": agent_gate.TASK}],
    }
    out = []
    for _ in range(calls):
        started = perf_counter()
        classifier.invoke({"state": state, "questions": agent_gate.GATE_QUESTIONS})
        out.append((perf_counter() - started) * 1000)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", type=int, default=10, help="calls per demo (>= 10 for the notes)")
    parser.add_argument("--location", default="", help='e.g. "Belgium (Ghent), fibre, no VPN"')
    args = parser.parse_args()
    try:
        with make_client() as client:
            console.print("warming up...")
            timed_system_one(client, {"ticket": "warm-up"}, {"x": smart_if.QUESTIONS["refund"]})
            results = {}
            for name, fn in (
                ("demo1_smart_if", lambda: bench_demo1(client, args.calls)),
                ("demo2_confidence_gate", lambda: bench_demo2(client, args.calls)),
                ("demo3_agent_gate", lambda: bench_demo3(args.calls)),
            ):
                console.print(f"measuring {name} ({args.calls} calls)...")
                values = fn()
                results[name] = {"samples_ms": [round(v, 1) for v in values], **LatencyStats.of(values).to_dict()}
    except Exception as error:  # noqa: BLE001
        print_error(error)
        return 1

    table = Table(title=f"Jev latency from {args.location or 'here'}")
    for col in ("demo", "n", "median ms", "p95 ms", "min ms", "max ms"):
        table.add_column(col, justify="right" if col != "demo" else "left")
    for name, r in results.items():
        table.add_row(name, str(r["n"]), f"{r['median_ms']:.0f}", f"{r['p95_ms']:.0f}", f"{r['min_ms']:.0f}", f"{r['max_ms']:.0f}")
    console.print(table)
    path = save_recording(BENCHMARK, {"location": args.location, "calls_per_demo": args.calls, "results": results})
    console.print(f"[green]saved {path}[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
