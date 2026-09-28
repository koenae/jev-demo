"""Generate the blog figures (SVG) from the recordings.

    uv run python scripts/blog_figures.py            # writes blog/jev-vs-llm/fig-*.svg

Each figure is a self-contained light card with fixed colors, so it renders the same in
every viewer, light or dark. The layout is deliberately minimal: category labels, bars and
the value printed next to each bar. No axis ticks, no grid, no subtitles. Context and
captions live in the post text, not in the image.
Colors: validated two-slot categorical palette (blue = Jev, orange = LLM).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REC = ROOT / "recordings"
OUT = ROOT / "blog" / "jev-vs-llm"

INK, INK2, SURF = "#1a1a19", "#77766f", "#fbfaf8"
JEV, LLM = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12, "text.color": INK, "axes.titlecolor": INK,
    "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.spines.bottom": False,
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
})


def load(name: str) -> dict:
    return json.loads((REC / f"{name}.json").read_text(encoding="utf-8"))["data"]


def bar(ax, y, width, color, h=0.5):
    ax.barh(y, width, height=h, color=color, linewidth=0, zorder=3)


def label(ax, x, y, text, pad, muted=False):
    ax.text(x + pad, y, text, va="center", ha="left", fontsize=11.5 if not muted else 10.5,
            color=INK2 if muted else INK, zorder=4)


def style(ax, xmax):
    """No ticks, no grid: the value is printed next to each bar."""
    ax.set_xlim(0, xmax)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, labelsize=12, pad=8)


def title(ax, text):
    ax.set_title(text, loc="left", fontsize=13, fontweight="bold", pad=14)


def legend(fig, entries):
    handles = [Patch(facecolor=c, edgecolor="none", label=l) for l, c in entries]
    leg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.04, 0.985), ncol=len(entries),
                     frameon=False, fontsize=11.5, handlelength=1.0, handleheight=1.0, columnspacing=2.0,
                     borderaxespad=0)
    for t in leg.get_texts():
        t.set_color(INK2)


def card(fig):
    """Soft rounded background behind the whole figure, no border line."""
    fig.patches.append(FancyBboxPatch((0.0, 0.0), 1.0, 1.0, boxstyle="round,pad=0,rounding_size=0.025",
                                      transform=fig.transFigure, facecolor=SURF, edgecolor="none", zorder=-1))
    fig.patch.set_alpha(0)


def finish(fig, name: str):
    fig.savefig(OUT / f"{name}.svg", format="svg", bbox_inches="tight", pad_inches=0.1, transparent=True)
    plt.close(fig)
    print("wrote", (OUT / f"{name}.svg").relative_to(ROOT))


# --- Figure 1: same decisions, two systems --------------------------------------------------

def fig_head_to_head():
    d = load("demo4_head_to_head")
    prices = d["llm_usd_per_mtok"]
    groups: dict[tuple[str, str], list[dict]] = {}
    for s in d["samples"]:
        groups.setdefault((s["task"], s["system"]), []).append(s)

    def stats(task, system):
        rows = groups[(task, system)]
        lat = median(r["latency_ms"] for r in rows)
        tin = sum(r["input_tokens"] or 0 for r in rows)
        tout = sum(r["output_tokens"] or 0 for r in rows)
        cost = tin * 0.042 / 1e6 if system == "jev" else (tin * prices[0] + tout * prices[1]) / 1e6
        return lat, cost / len(rows) * 1000

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4),
                                 gridspec_kw={"wspace": 0.5, "top": 0.76, "bottom": 0.1, "left": 0.17, "right": 0.96})
    card(fig)
    tasks = [("triage", "Ticket triage"), ("gate", "Tool-call gate")]
    for i, (task, _) in enumerate(tasks):
        for j, (system, color) in enumerate((("llm", LLM), ("jev", JEV))):
            y = i + (0.22 if j else -0.22)
            lat, cost = stats(task, system)
            bar(a1, y, lat, color, h=0.38)
            label(a1, lat, y, f"{lat:,.0f} ms", 40)
            bar(a2, y, cost, color, h=0.38)
            label(a2, cost, y, f"${cost:.3f}", 0.004)
    for ax, text, xmax in ((a1, "Median latency per decision", 2700), (a2, "Cost per 1,000 decisions", 0.21)):
        ax.set_yticks([0, 1]); ax.set_yticklabels([t[1] for t in tasks])
        ax.set_ylim(-0.6, 1.6); ax.invert_yaxis()
        style(ax, xmax)
        title(ax, text)
    legend(fig, [("gpt-5-mini", LLM), ("Jev", JEV)])
    finish(fig, "fig-1-head-to-head")


# --- Figure 2: one call vs twenty samples --------------------------------------------------

def fig_samples():
    d = load("demo5_one_call_vs_samples")
    labels = ["billing", "technical", "sales", "other"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7),
                             gridspec_kw={"wspace": 0.4, "top": 0.78, "bottom": 0.05, "left": 0.11, "right": 0.96})
    card(fig)
    n = 0
    for ax, t in zip(axes, d["tickets"]):
        counts = Counter(s["team"] for s in t["llm_samples"])
        n = len(t["llm_samples"])
        jev = t["jev_calls"][0]
        for i, lab in enumerate(labels):
            share = counts.get(lab, 0) / n
            prob = jev["probabilities"].get(lab, 0.0)
            bar(ax, i - 0.2, share, LLM, h=0.34)
            bar(ax, i + 0.2, prob, JEV, h=0.34)
            label(ax, share, i - 0.2, f"{counts.get(lab, 0)} of {n}" if share >= 0.005 else "0", 0.02, muted=share < 0.005)
            label(ax, prob, i + 0.2, f"{prob:.2f}", 0.02, muted=prob < 0.005)
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
        ax.set_ylim(-0.6, len(labels) - 0.4); ax.invert_yaxis()
        style(ax, 1.3)
        title(ax, "Upgrade ticket, ambiguous" if t["ticket_id"] == "T-109" else "Double charge, clear")
    legend(fig, [(f"gpt-5-mini, answers out of {n} calls", LLM), ("Jev, probability from 1 call", JEV)])
    finish(fig, "fig-2-one-call-vs-samples")


# --- Figure 3: what one check by the judge costs ------------------------------------------

def fig_gate():
    d = load("demo3_gate_comparison")
    stats = {}
    for kind in ("llm", "jev"):
        runs = d["runs"][kind]
        per_call = [x["latency_ms"] for r in runs for x in r["decisions"]]
        tin = sum(r["gate_input_tokens"] for r in runs)
        tout = sum(r["gate_output_tokens"] for r in runs)
        cost = (tin * 0.25 + tout * 2.0) / 1e6 if kind == "llm" else tin * 0.042 / 1e6
        stats[kind] = (median(per_call), cost / len(per_call) * 10_000)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 2.7),
                                 gridspec_kw={"wspace": 0.5, "top": 0.78, "bottom": 0.1, "left": 0.14, "right": 0.96})
    card(fig)
    for i, (kind, color) in enumerate((("llm", LLM), ("jev", JEV))):
        ms, usd = stats[kind]
        bar(a1, i, ms, color, h=0.48)
        label(a1, ms, i, f"{ms:,.0f} ms", 30)
        bar(a2, i, usd, color, h=0.48)
        label(a2, usd, i, f"${usd:.2f}", 0.08)
    for ax, text, xmax in ((a1, "Judge latency per tool call", 2100), (a2, "Judge cost per 10,000 tool calls", 4.8)):
        ax.set_yticks([0, 1]); ax.set_yticklabels(["gpt-5-mini", "Jev"])
        ax.set_ylim(-0.65, 1.65); ax.invert_yaxis()
        style(ax, xmax)
        title(ax, text)
    finish(fig, "fig-3-agent-gate")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_head_to_head()
    fig_samples()
    fig_gate()
    sys.exit(0)
