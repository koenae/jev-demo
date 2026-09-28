"""Demo 5 - One call vs N samples. Usage: uv run python demos/demo5_one_call_vs_samples.py [--record | --offline] [--samples 20]"""

from __future__ import annotations

import argparse
import sys

from _cli import bar, console, mode_from, origin_badge, print_error
from rich.panel import Panel
from rich.table import Table

from jevdemo.one_call_vs_samples import run_one_call_vs_samples
from jevdemo.questions import TEAMS


def main(mode: str, samples: int | None) -> None:
    console.print(
        Panel(
            "Ask the LLM the same question N times: every answer is ONE sample from a distribution you "
            "never see. Ask Jev once: you get the distribution.",
            title="Demo 5 - One call vs N samples",
            style="cyan",
        )
    )
    result = run_one_call_vs_samples(mode, samples=samples)  # type: ignore[arg-type]
    console.print(origin_badge(result.origin))
    for t in result.tickets:
        console.print(Panel(t.text, title=f"{t.ticket_id}", border_style="blue"))
        table = Table(title=f"{result.samples} LLM samples ({result.llm})  vs  1 Jev call ({result.jev_model})")
        table.add_column("team")
        table.add_column("LLM: share of samples", justify="right")
        table.add_column("")
        table.add_column("Jev: probability", justify="right")
        table.add_column("")
        dist = t.llm_distribution
        for label in TEAMS:
            table.add_row(label, f"{dist[label]:.2f}", bar(dist[label], 16), f"{t.jev.probabilities[label]:.2f}", bar(t.jev.probabilities[label], 16))
        console.print(table)
        llm_cost, jev_cost = result.costs(t)
        cost_txt = f"${llm_cost:.5f} vs ${jev_cost:.6f}" if llm_cost is not None else f"n/a vs ${jev_cost:.6f} (set LLM_PRICE_*)"
        console.print(
            f"LLM: majority [bold]{t.llm_majority}[/bold] in {t.llm_agreement:.0%} of samples, "
            f"self-reported confidence [bold]{t.llm_mean_confidence:.2f}[/bold] on average, "
            f"{t.llm_total_ms / 1000:.1f} s of calls\n"
            f"Jev: [bold]{t.jev.team}[/bold] with confidence {t.jev.confidence:.2f}, "
            f"{t.jev.latency_ms:.0f} ms, max spread over {len(t.jev_calls)} repeats {t.jev_spread:.3f}\n"
            f"Cost of {result.samples} samples vs 1 call: {cost_txt}\n"
        )
    if mode == "record":
        console.print("[green]Recording saved to recordings/demo5_one_call_vs_samples.json[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo 5 - what an LLM answer is, next to what Jev returns")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", action="store_true")
    group.add_argument("--offline", action="store_true")
    parser.add_argument("--samples", type=int, default=None, help="LLM samples per ticket (default 20 or LLM_SAMPLES)")
    args = parser.parse_args()
    try:
        main(mode_from(args), args.samples)
    except Exception as error:  # noqa: BLE001
        print_error(error)
        sys.exit(1)
