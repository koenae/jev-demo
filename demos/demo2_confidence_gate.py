"""Demo 2 - Confidence gate. Usage: uv run python demos/demo2_confidence_gate.py [--record | --offline] [--threshold 0.75]"""

from __future__ import annotations

import sys

from _cli import bar, console, mode_from, origin_badge, print_error
from rich.panel import Panel
from rich.table import Table

from jevdemo.confidence_gate import DEFAULT_THRESHOLD, gate, run_confidence_gate
from jevdemo.latency import LatencyStats

def main(mode: str, threshold: float) -> None:
    console.print(
        Panel(
            f"~10 tickets -> one Jev call each. Confidence >= {threshold:.2f}: handled automatically. "
            "Below: escalated to a human.",
            title="Demo 2 - Confidence gate",
            style="cyan",
        )
    )
    result = run_confidence_gate(mode)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    summary = gate(result.decisions, threshold)

    table = Table(title=f"Per ticket (threshold {threshold:.2f})", show_lines=False)
    table.add_column("ID", style="bold")
    table.add_column("Ticket", max_width=48, no_wrap=True, overflow="ellipsis")
    table.add_column("Team")
    table.add_column("Conf.", justify="right")
    table.add_column("")
    table.add_column("Urgency")
    table.add_column("ms", justify="right")
    table.add_column("Decision")
    for d in result.decisions:
        auto = d.team.confidence >= threshold
        style = "green" if auto else "yellow"
        table.add_row(
            d.ticket_id,
            d.text,
            d.team.choice,
            f"{d.team.confidence:.2f}",
            bar(d.team.confidence, 12),
            f"{d.urgency.level} {d.urgency.label[:18]}",
            f"{d.meta.latency_ms:.0f}",
            f"[{style}]{'auto' if auto else 'ESCALATE'}[/{style}]",
        )
    console.print(table)

    stats = LatencyStats.of(result.latencies_ms)
    console.print(
        Panel(
            f"[green]{summary.auto_pct:.0f}% automatic[/green] ({summary.auto_count})   "
            f"[yellow]{summary.escalated_pct:.0f}% escalated[/yellow] ({summary.escalated_count})\n"
            f"Total API time: {summary.total_ms:.0f} ms for {len(result.decisions)} tickets  "
            f"(median {stats.median_ms:.0f} ms, p95 {stats.p95_ms:.0f} ms per call)",
            title="Summary",
            border_style="green",
        )
    )
    if mode == "record":
        console.print("[green]Recording saved to recordings/demo2_confidence_gate.json[/green]")

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description="Demo 2 - confidence gate over a ticket batch")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", action="store_true")
    group.add_argument("--offline", action="store_true")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    try:
        main(mode_from(args), args.threshold)
    except Exception as error:  # noqa: BLE001
        print_error(error)
        sys.exit(1)
