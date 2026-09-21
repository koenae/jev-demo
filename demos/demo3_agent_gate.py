"""Demo 3 - Agent gate. Usage: uv run python demos/demo3_agent_gate.py [--record | --offline]"""

from __future__ import annotations

from _cli import bar, console, origin_badge, run_cli
from rich.panel import Panel
from rich.table import Table

from jevdemo.agent_gate import THRESHOLD, run_agent_gate


def main(mode: str) -> None:
    console.print(
        Panel(
            "LangChain agent with simulated ops tools. Jev middleware judges EVERY tool call "
            "first: destructive? production? secrets? Nothing is executed for real.",
            title="Demo 3 - Agent gate",
            style="cyan",
        )
    )
    result = run_agent_gate(mode)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    console.print(Panel(result.task, title="Task given to the agent", border_style="blue"))

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
    run_cli("Demo 3 - Jev as a gate in front of every agent tool call", main)
