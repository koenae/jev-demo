"""Demo 1 - Smart if. Usage: uv run python demos/demo1_smart_if.py [--record | --offline]"""

from __future__ import annotations

from _cli import bar, console, origin_badge, run_cli
from rich.panel import Panel
from rich.table import Table

from jevdemo.smart_if import run_smart_if


def main(mode: str) -> None:
    console.print(
        Panel(
            "One support ticket -> ONE call to Jev -> Choice (team), Score (urgency), Noul (refund?)",
            title="Demo 1 - Smart if",
            style="cyan",
        )
    )
    result = run_smart_if(mode)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    console.print(Panel(result.ticket, title="Ticket", border_style="blue"))

    answers = Table(title="Typed answers (one API call)", show_lines=True)
    answers.add_column("Question", style="bold")
    answers.add_column("Answer")
    answers.add_column("Confidence / P(yes)")
    answers.add_row(
        "team (Choice)", result.team.choice, f"{result.team.confidence:.2f} confidence"
    )
    answers.add_row(
        "urgency (Score)",
        f"level {result.urgency.level} - {result.urgency.label}  (score {result.urgency.score:.2f})",
        f"{result.urgency.confidence:.2f} confidence",
    )
    answers.add_row(
        "refund (Noul)", "yes" if result.refund.yes else "no", f"P(yes) = {result.refund.noul:.2f}"
    )
    console.print(answers)

    dist = Table(title="Full probability distributions")
    dist.add_column("Question")
    dist.add_column("Option")
    dist.add_column("Probability", justify="right")
    dist.add_column("")
    for option, p in sorted(result.team.probabilities.items(), key=lambda kv: -kv[1]):
        dist.add_row("team", option, f"{p:.3f}", bar(p))
    for level, p in sorted(result.urgency.probabilities.items()):
        dist.add_row("urgency", f"{level}: {result.urgency.legend[level]}", f"{p:.3f}", bar(p))
    dist.add_row("refund", "yes", f"{result.refund.noul:.3f}", bar(result.refund.noul))
    dist.add_row("refund", "no", f"{1 - result.refund.noul:.3f}", bar(1 - result.refund.noul))
    console.print(dist)

    meta = result.meta
    console.print(
        f"[bold]Latency:[/bold] {meta.latency_ms:.0f} ms   [bold]Model:[/bold] {meta.model}   "
        f"[bold]Tokens:[/bold] in={meta.input_tokens} out={meta.output_tokens}"
    )
    if mode == "record":
        console.print("[green]Recording saved to recordings/demo1_smart_if.json[/green]")


if __name__ == "__main__":
    run_cli("Demo 1 - one ticket, one call, three typed answers", main)
