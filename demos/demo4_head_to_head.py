"""Demo 4 - Head-to-head. Usage: uv run python demos/demo4_head_to_head.py [--record | --offline]"""

from __future__ import annotations

from _cli import console, origin_badge, run_cli
from rich.panel import Panel
from rich.table import Table

from jevdemo.head_to_head import agreement, run_head_to_head, speedup, summarize


def fmt_usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.6f}"


def main(mode: str) -> None:
    console.print(
        Panel(
            "Same tickets, same tool calls, same criteria text: once through the LLM with structured "
            "output, once through Jev. Latency, tokens, cost and how often they agree.",
            title="Demo 4 - Head-to-head: LLM vs Jev",
            style="cyan",
        )
    )
    result = run_head_to_head(mode)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    summary = summarize(result)

    table = Table(title=f"Summary  (LLM = {result.llm}, Jev = {result.jev_model}, {result.workers} calls in parallel)")
    for col in ("task", "system", "n", "median", "p95", "tokens in", "tokens out", "cost (n calls)", "cost / 1000"):
        table.add_column(col, justify="right" if col not in ("task", "system") else "left")
    for (task, system), s in summary.items():
        style = "green" if system == "jev" else ""
        table.add_row(
            task, f"[{style}]{system}[/{style}]" if style else system, str(s.n),
            f"{s.latency.median_ms:.0f} ms", f"{s.latency.p95_ms:.0f} ms",
            str(s.input_tokens), str(s.output_tokens), fmt_usd(s.cost_usd), fmt_usd(s.cost_per_1000_usd),
        )
    console.print(table)

    for task in ("triage", "gate"):
        lat, cost = speedup(summary, task)
        agree = agreement(result, task)
        agree_txt = "  ".join(f"{k}: {v:.0%}" for k, v in agree.items())
        console.print(
            f"[bold]{task}[/bold]: Jev is [green]{lat:.1f}x faster[/green] (median)"
            + (f" and [green]{cost:.0f}x cheaper[/green]" if cost else " (cost factor n/a)")
            + f"   agreement -> {agree_txt}"
        )

    detail = Table(title="Per item", show_lines=False)
    for col in ("item", "LLM answer", "ms", "Jev answer", "ms", "same?"):
        detail.add_column(col, justify="right" if col == "ms" else "left")
    by = {(s.task, s.system, s.item_id): s for s in result.samples}
    for task in ("triage", "gate"):
        ids = sorted({s.item_id for s in result.samples if s.task == task})
        for i in ids:
            l, j = by.get((task, "llm", i)), by.get((task, "jev", i))
            if not l or not j:
                continue
            same = l.answer == j.answer
            detail.add_row(
                i, ", ".join(f"{k}={v}" for k, v in l.answer.items()), f"{l.latency_ms:.0f}",
                ", ".join(f"{k}={v}" for k, v in j.answer.items()), f"{j.latency_ms:.0f}",
                "[green]yes[/green]" if same else "[yellow]no[/yellow]",
            )
    console.print(detail)
    if result.llm_usd_per_mtok is None:
        console.print("[yellow]Tip: set LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK in .env for the cost columns.[/yellow]")
    if mode == "record":
        console.print("[green]Recording saved to recordings/demo4_head_to_head.json[/green]")


if __name__ == "__main__":
    run_cli("Demo 4 - LLM vs Jev on identical decisions", main)
