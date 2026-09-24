"""Generate the blog figures (SVG + PNG preview) from the real recordings.

    uv run python scripts/blog_figures.py            # writes blog/jev-vs-llm/fig-*.svg

Each figure is a self-contained light card with fixed colors, so it renders the same in
every viewer, light or dark. Context and captions live in the post text, not in the image.
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

INK, INK2, GRID, SURF = "#1a1a19", "#6b6a66", "#e8e7e3", "#fbfaf8"
JEV, LLM = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK, "text.color": INK, "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.spines.bottom": False,
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
})


def load(name: str) -> dict:
    return json.loads((REC / f"{name}.json").read_text(encoding="utf-8"))["data"]


def bar(ax, y, width, color, left=0.0, h=0.5):
    ax.barh(y, width, height=h, left=left, color=color, linewidth=0, zorder=3)


def style(ax, xmax, ticks=None):
    ax.set_xlim(0, xmax)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=11)
    if ticks is not None:
        ax.set_xticks(ticks)


def legend(fig, entries, y=0.97):
    handles = [Patch(facecolor=c, edgecolor="none", label=l) for l, c in entries]
    leg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.06, y), ncol=len(entries), frameon=False,
                     fontsize=11, handlelength=1.1, handleheight=0.9, columnspacing=1.6, borderaxespad=0)
    for t in leg.get_texts():
        t.set_color(INK2)


def card(fig):
    """Rounded card background behind the whole figure."""
    fig.patches.append(FancyBboxPatch((0.01, 0.01), 0.98, 0.98, boxstyle="round,pad=0,rounding_size=0.02",
                                      transform=fig.transFigure, facecolor=SURF, edgecolor=GRID, linewidth=1, zorder=-1))
    fig.patch.set_alpha(0)


def finish(fig, name: str):
    fig.savefig(OUT / f"{name}.svg", format="svg", bbox_inches="tight", pad_inches=0.05, transparent=True)
    fig.savefig(OUT / f"{name}.png", format="png", dpi=120, bbox_inches="tight", pad_inches=0.05, transparent=True)
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

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"wspace": 0.6, "top": 0.72, "bottom": 0.16, "left": 0.2, "right": 0.97})
    card(fig)
    tasks = [("triage", "Ticket triage"), ("gate", "Tool-call gate")]
    for i, (task, _) in enumerate(tasks):
        for j, (system, color) in enumerate((("llm", LLM), ("jev", JEV))):
            y = i + (0.24 if j else -0.24)
            lat, cost = stats(task, system)
            bar(a1, y, lat, color, h=0.4)
            a1.text(lat + 40, y, f"{lat:,.0f} ms", va="center", fontsize=11, color=INK)
            bar(a2, y, cost, color, h=0.4)
            a2.text(cost + 0.004, y, f"${cost:.3f}", va="center", fontsize=11, color=INK)
    for ax, title, xmax, ticks, fmt in ((a1, "Median latency per decision", 2500, [0, 1000, 2000], "{x:,.0f} ms"),
                                       (a2, "Cost per 1,000 decisions", 0.2, [0, 0.1, 0.2], "${x:.2f}")):
        ax.set_yticks([0, 1]); ax.set_yticklabels([t[1] for t in tasks], fontsize=12)
        ax.set_ylim(-0.75, 1.75); ax.invert_yaxis()
        style(ax, xmax, ticks)
        ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter(fmt))
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=10)
    legend(fig, [("gpt-5-mini", LLM), ("Jev", JEV)], y=0.95)
    finish(fig, "fig-1-head-to-head")


# --- Figure 2: one call vs twenty samples --------------------------------------------------

def fig_samples():
    d = load("demo5_one_call_vs_samples")
    labels = ["billing", "technical", "sales", "other"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), gridspec_kw={"wspace": 0.45, "top": 0.74, "bottom": 0.14, "left": 0.13, "right": 0.97})
    card(fig)
    for ax, t in zip(axes, d["tickets"]):
        counts = Counter(s["team"] for s in t["llm_samples"])
        n = len(t["llm_samples"])
        jev = t["jev_calls"][0]
        for i, label in enumerate(labels):
            share = counts.get(label, 0) / n
            prob = jev["probabilities"].get(label, 0.0)
            bar(ax, i - 0.21, share, LLM, h=0.36)
            bar(ax, i + 0.21, prob, JEV, h=0.36)
            if share >= 0.005:
                ax.text(share + 0.02, i - 0.21, f"{share:.2f}", va="center", fontsize=11, color=INK)
            if prob >= 0.005:
                ax.text(prob + 0.02, i + 0.21, f"{prob:.2f}", va="center", fontsize=11, color=INK)
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=12)
        ax.set_ylim(-0.65, len(labels) - 0.35); ax.invert_yaxis()
        style(ax, 1.22, [0, 0.5, 1.0])
        kind = "ambiguous ticket" if t["ticket_id"] == "T-109" else "clear ticket"
        llm_conf = sum(s["confidence"] for s in t["llm_samples"]) / n
        ax.set_title(f"{t['ticket_id']}, {kind}", loc="left", fontsize=13, fontweight="bold", pad=24)
        ax.text(0, 1.03, f"LLM self-reported confidence {llm_conf:.2f}  ·  Jev confidence {jev['confidence']:.2f}",
                transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom")
    legend(fig, [(f"gpt-5-mini, share of {n} answers", LLM), ("Jev, probability from 1 call", JEV)], y=0.95)
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
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 2.9), gridspec_kw={"wspace": 0.55, "top": 0.72, "bottom": 0.2, "left": 0.16, "right": 0.97})
    card(fig)
    for i, (kind, color) in enumerate((("llm", LLM), ("jev", JEV))):
        ms, usd = stats[kind]
        bar(a1, i, ms, color, h=0.5)
        a1.text(ms + 30, i, f"{ms:,.0f} ms", va="center", fontsize=11, color=INK)
        bar(a2, i, usd, color, h=0.5)
        a2.text(usd + 0.08, i, f"${usd:.2f}", va="center", fontsize=11, color=INK)
    for ax, title, xmax, ticks, fmt in ((a1, "Judge latency per tool call", 2100, [0, 1000, 2000], "{x:,.0f} ms"),
                                       (a2, "Judge cost per 10,000 tool calls", 4.8, [0, 2, 4], "${x:.0f}")):
        ax.set_yticks([0, 1]); ax.set_yticklabels(["gpt-5-mini", "Jev"], fontsize=12)
        ax.set_ylim(-0.7, 1.7); ax.invert_yaxis()
        style(ax, xmax, ticks)
        ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter(fmt))
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=10)
    legend(fig, [("gpt-5-mini as judge", LLM), ("Jev as judge", JEV)], y=0.95)
    finish(fig, "fig-3-agent-gate")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_head_to_head()
    fig_samples()
    fig_gate()
    sys.exit(0)
