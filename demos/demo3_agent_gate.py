"""Demo 3 - Agent gate.

Usage: uv run python demos/demo3_agent_gate.py [--record | --offline] [--gate none|llm|jev] [--compare]
"""

from __future__ import annotations

import argparse
import sys

from _cli import bar, console, mode_from, origin_badge, print_error
from rich.panel import Panel
from rich.table import Table

from jevdemo.agent_gate import THRESHOLD, compare, run_agent_gate, run_gate_comparison


def fmt_usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.5f}"


def main_compare(mode: str, runs: int) -> None:
    console.print(
        Panel(
            "Same task with three gates: none, the LLM as judge on every tool call, Jev as judge. "
            "The agent's own turns vary a lot between runs, so look at the gate columns first; "
            "use --runs 3 or more for medians.",
            title="Demo 3 - Gate comparison",
            style="cyan",
        )
    )
    result = run_gate_comparison(mode, runs=runs)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    rows = compare(result)
    table = Table(title=f"none vs LLM gate vs Jev gate (medians over {rows[0].runs if rows else 0} run(s) each)")
    for col in ("gate", "gate / call", "gate time", "share of run", "agent run", "agent w/o gate", "tool calls", "blocked", "agent cost", "gate cost", "total cost"):
        table.add_column(col, justify="left" if col == "gate" else "right")
    for row in rows:
        style = "green" if row.gate == "jev" else ""
        table.add_row(
            f"[{style}]{row.gate}[/{style}]" if style else row.gate,
            "-" if row.gate_ms_per_call is None else f"{row.gate_ms_per_call:.0f} ms",
            f"{row.gate_ms / 1000:.1f} s", f"{row.gate_share:.0%}",
            f"{row.total_ms / 1000:.1f} s", f"{row.agent_ms / 1000:.1f} s",
            f"{row.tool_calls:g}", f"{row.blocked:g}",
            fmt_usd(row.agent_cost_usd), fmt_usd(row.gate_cost_usd), fmt_usd(row.total_cost_usd),
        )
    console.print(table)
    by = {r.gate: r for r in rows}
    if "llm" in by and "jev" in by and by["jev"].gate_ms_per_call:
        console.print(
            f"Per judged tool call: LLM gate {by['llm'].gate_ms_per_call:.0f} ms vs Jev gate {by['jev'].gate_ms_per_call:.0f} ms "
            f"-> [green]{by['llm'].gate_ms_per_call / by['jev'].gate_ms_per_call:.1f}x[/green]. "
            "The 'agent run' totals include the agent's own LLM turns, which differ per run (different paths, reasoning time)."
        )
    if result.llm_usd_per_mtok is None:
        console.print("[yellow]Tip: set LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK in .env for the cost columns.[/yellow]")
    if mode == "record":
        console.print("[green]Recordings saved: demo3_gate_comparison.json (+ demo3_agent_gate.json refreshed)[/green]")


def main(mode: str, gate: str = "jev") -> None:
    console.print(
        Panel(
            "LangChain agent with simulated ops tools. Jev middleware judges EVERY tool call "
            "first: destructive? production? secrets? Nothing is executed for real.",
            title="Demo 3 - Agent gate",
            style="cyan",
        )
    )
    result = run_agent_gate(mode, gate=gate)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    console.print(Panel(result.task, title=f"Task given to the agent (gate: {result.gate})", border_style="blue"))

    table = Table(title=f"Gate decisions (block threshold {THRESHOLD:.2f})", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Tool call", max_width=44)
    table.add_column("destructive", justify="right")
    table.add_column("production", justify="right")
    table.add_column("secrets", justify="right")
    table.add_column("ms", justify="right")
    table.add_column("Decision")
    for i, d in enumerate(result.decisions, 1):
        args = ", ".join(f"{k}={str(v)[:38] + ('…' if len(str(v)) > 38 else '')!r}" for k, v in d.args.items())
        p = d.probabilities
        verdict = f"[red bold]BLOCKED[/red bold]\n{d.reason}" if d.blocked else "[green]allowed[/green]"
        table.add_row(
            str(i),
            f"{d.tool}({args})",
            f"{p['destructive']:.2f} {bar(p['destructive'], 8)}",
            f"{p['production']:.2f} {bar(p['production'], 8)}",
            f"{p['secrets']:.2f} {bar(p['secrets'], 8)}",
            f"{d.latency_ms:.0f}",
            verdict,
        )
    console.print(table)
    console.print(Panel(result.final_answer, title="Agent's final report", border_style="green"))
    console.print(
        f"[bold]LLM:[/bold] {result.llm}   [bold]Gate model:[/bold] {result.gate_model}   "
        f"[bold]Tool calls:[/bold] {len(result.decisions)}  "
        f"[bold]Blocked:[/bold] {len(result.blocked)}   [bold]Total:[/bold] {result.total_ms / 1000:.1f} s"
    )
    if mode == "record":
        console.print("[green]Recording saved to recordings/demo3_agent_gate.json[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo 3 - a gate in front of every agent tool call")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", action="store_true")
    group.add_argument("--offline", action="store_true")
    parser.add_argument("--gate", choices=("none", "llm", "jev"), default="jev", help="who judges the tool calls")
    parser.add_argument("--compare", action="store_true", help="run all three gates and compare time and cost")
    parser.add_argument("--runs", type=int, default=1, help="with --compare: runs per gate kind (medians)")
    args = parser.parse_args()
    try:
        if args.compare:
            main_compare(mode_from(args), args.runs)
        else:
            main(mode_from(args), args.gate)
    except Exception as error:  # noqa: BLE001
        print_error(error)
        sys.exit(1)
