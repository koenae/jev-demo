"""Generate the blog figures (SVG) from the real recordings.

    uv run python scripts/blog_figures.py            # writes blog/jev-vs-llm/fig-*.svg (+ .png previews)

The SVGs carry a <style> with prefers-color-scheme rules, so text, gridlines and bars
adapt to a dark blog theme. Colors: validated two-slot categorical palette
(blue = Jev, orange = LLM), grey for the non-data context.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REC = ROOT / "recordings"
OUT = ROOT / "blog" / "jev-vs-llm"

# Sentinel colors: replaced by CSS variables in the SVG post-processing step.
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
JEV, LLM, GREY = "#2a78d6", "#eb6834", "#b8b7b2"
DARK = {INK: "#f2f0ea", INK2: "#c3c2b7", GRID: "#3a3a38", JEV: "#3987e5", LLM: "#d95926", GREY: "#6e6d68"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK, "text.color": INK, "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
})


def load(name: str) -> dict:
    return json.loads((REC / f"{name}.json").read_text(encoding="utf-8"))["data"]


def rounded_bar(ax, y, width, height, color, left=0.0):
    """Thin bar from the baseline (plain rectangle: rounding in data units distorts on non-square scales)."""
    ax.barh(y, width, height=height, left=left, color=color, linewidth=0, zorder=3)


def style_axes(ax, xmax):
    ax.set_xlim(0, xmax)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def finish(fig, name: str):
    svg = OUT / f"{name}.svg"
    fig.savefig(svg, format="svg", bbox_inches="tight", pad_inches=0.15)
    fig.savefig(OUT / f"{name}.png", format="png", dpi=110, bbox_inches="tight", pad_inches=0.15, facecolor=SURF)
    plt.close(fig)
    text = svg.read_text(encoding="utf-8")
    for light, dark in DARK.items():
        text = text.replace(light, f"var(--c{light[1:]})")
    css = ":root{" + "".join(f"--c{k[1:]}:{k};" for k in DARK) + "}"
    css += "@media (prefers-color-scheme: dark){:root{" + "".join(f"--c{k[1:]}:{v};" for k, v in DARK.items()) + "}}"
    text = re.sub(r"(<svg[^>]*>)", r"\1<style>" + css + "</style>", text, count=1)
    svg.write_text(text, encoding="utf-8")
    print("wrote", svg.relative_to(ROOT))


def legend(ax, entries, loc=(0.0, 1.02), ncol=None):
    handles = [Patch(facecolor=c, edgecolor="none", label=l) for l, c in entries]
    leg = ax.legend(handles=handles, loc="lower left", bbox_to_anchor=loc, ncol=ncol or len(entries), frameon=False,
                    fontsize=9.5, handlelength=1.2, handleheight=0.9, columnspacing=1.4, borderaxespad=0)
    for t in leg.get_texts():
        t.set_color(INK2)


# --- Figure 1: same decisions, two systems --------------------------------------------------

def fig_head_to_head():
    d = load("demo4_head_to_head")
    prices = d["llm_usd_per_mtok"]
    groups: dict[tuple[str, str], list[dict]] = {}
    for s in d["samples"]:
        groups.setdefault((s["task"], s["system"]), []).append(s)

    def stats(task, system):
        rows = groups[(task, system)]
        lat = [r["latency_ms"] for r in rows]
        tin = sum(r["input_tokens"] or 0 for r in rows)
        tout = sum(r["output_tokens"] or 0 for r in rows)
        cost = tin * 0.042 / 1e6 if system == "jev" else (tin * prices[0] + tout * prices[1]) / 1e6
        return median(lat), cost / len(rows) * 1000

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 3.6), gridspec_kw={"wspace": 0.55})
    tasks = [("triage", "Ticket triage\n(team, urgency, refund)"), ("gate", "Tool-call gate\n(destructive, production, secrets)")]
    ys = []
    for i, (task, _label) in enumerate(tasks):
        for j, (system, color) in enumerate((("llm", LLM), ("jev", JEV))):
            y = i * 1.0 + (0.22 if j else -0.22)
            ys.append(y)
            lat, cost = stats(task, system)
            rounded_bar(a1, y, lat, 0.34, color)
            a1.text(lat + 40, y, f"{lat:,.0f} ms", va="center", fontsize=10, color=INK)
            rounded_bar(a2, y, cost, 0.34, color)
            a2.text(cost + 0.004, y, f"${cost:.3f}", va="center", fontsize=10, color=INK)
    for ax, title, xmax, fmt in ((a1, "Median latency per decision", 2400, "{x:,.0f}"), (a2, "Cost per 1,000 decisions (USD)", 0.19, "${x:.2f}")):
        ax.set_yticks([0, 1]); ax.set_yticklabels([t[1] for t in tasks], fontsize=10)
        ax.set_ylim(-0.7, 1.7); ax.invert_yaxis()
        style_axes(ax, xmax)
        ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter(fmt))
        ax.set_title(title, loc="left", fontsize=11, pad=8)
    legend(a1, [("gpt-5-mini, structured output", LLM), ("Jev", JEV)], loc=(0.0, 1.14))
    fig.text(0.0, -0.06, "Same 11 tickets and 6 tool calls, same criteria text. gpt-5-mini via Microsoft Foundry, reasoning effort minimal, "
             "$0.25 / $2.00 per M tokens; Jev $0.042 per M input tokens. 4 calls in parallel, from Belgium, 23 Sep 2026.",
             fontsize=8.5, color=INK2, wrap=True)
    finish(fig, "fig-1-head-to-head")


# --- Figure 2: one call vs twenty samples --------------------------------------------------

def fig_samples():
    d = load("demo5_one_call_vs_samples")
    labels = ["billing", "technical", "sales", "other"]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), gridspec_kw={"wspace": 0.45})
    for ax, t in zip(axes, d["tickets"]):
        counts = Counter(s["team"] for s in t["llm_samples"])
        n = len(t["llm_samples"])
        jev = t["jev_calls"][0]
        for i, label in enumerate(labels):
            share = counts.get(label, 0) / n
            prob = jev["probabilities"].get(label, 0.0)
            rounded_bar(ax, i - 0.2, share, 0.32, LLM)
            rounded_bar(ax, i + 0.2, prob, 0.32, JEV)
            if share >= 0.005:
                ax.text(share + 0.02, i - 0.2, f"{share:.2f}", va="center", fontsize=9.5, color=INK)
            if prob >= 0.005:
                ax.text(prob + 0.02, i + 0.2, f"{prob:.2f}", va="center", fontsize=9.5, color=INK)
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
        ax.set_ylim(-0.6, len(labels) - 0.4); ax.invert_yaxis()
        style_axes(ax, 1.25)
        ax.set_xticks([0, 0.5, 1.0])
        llm_conf = sum(s["confidence"] for s in t["llm_samples"]) / n
        agree = max(counts.values()) / n
        ax.set_title(f"{t['ticket_id']}: {'ambiguous' if t['ticket_id'] == 'T-109' else 'clear'} ticket", loc="left", fontsize=11, pad=8)
        ax.text(0, -0.2, f"LLM agrees with itself {agree:.0%} of the time, reports {llm_conf:.2f} confidence\n"
                         f"Jev confidence {jev['confidence']:.2f}, one call", transform=ax.transAxes, fontsize=9, color=INK2, va="top")
    legend(axes[0], [(f"gpt-5-mini: share of {n} samples", LLM), ("Jev: probability, 1 call", JEV)], loc=(0.0, 1.14))
    fig.text(0.0, -0.22, 'T-109: "My subscription renewed but the new features from the upgrade aren\'t showing. Did the payment go through or is this a bug?"   '
             'T-102: "I was charged EUR 49 twice this month. Please refund one of them."', fontsize=8.5, color=INK2, wrap=True)
    finish(fig, "fig-2-one-call-vs-samples")


# --- Figure 3: who judges the agent's tool calls -------------------------------------------

def fig_gate():
    d = load("demo3_gate_comparison")
    rows = []
    for kind, label in (("none", "No gate"), ("llm", "gpt-5-mini as judge"), ("jev", "Jev as judge")):
        runs = d["runs"][kind]
        gate = median(sum(x["latency_ms"] for x in r["decisions"]) for r in runs)
        total = median(r["total_ms"] for r in runs)
        per_call = [x["latency_ms"] for r in runs for x in r["decisions"]]
        rows.append((label, kind, (total - gate) / 1000, gate / 1000, median(per_call) / 1000 if per_call else None, gate / total))
    fig, ax = plt.subplots(figsize=(9.5, 2.9))
    for i, (label, kind, agent_s, gate_s, per_call, share) in enumerate(rows):
        rounded_bar(ax, i, agent_s, 0.42, GREY)
        if gate_s:
            color = LLM if kind == "llm" else JEV
            rounded_bar(ax, i, gate_s, 0.42, color, left=agent_s + 0.06)
            ax.text(agent_s + gate_s + 0.25, i, f"judge: {gate_s:.1f} s = {share:.0%} of the run · {per_call * 1000:.0f} ms per check",
                    va="center", fontsize=9.5, color=INK)
        else:
            ax.text(agent_s + 0.25, i, f"{agent_s:.1f} s", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4); ax.invert_yaxis()
    style_axes(ax, 20)
    ax.set_xlabel("Wall time of one agent run, seconds (median of 3 runs)", fontsize=9.5)
    legend(ax, [("Agent's own LLM turns", GREY), ("gpt-5-mini judging each tool call", LLM), ("Jev judging each tool call", JEV)], loc=(0.0, 1.02))
    fig.text(0.0, -0.16, "Same 4-step SRE task, same three questions per tool call (destructive? production? secrets?), same block policy. "
             "Agent turns vary 7-25 s between runs; the judge time is the part the gate controls.", fontsize=8.5, color=INK2, wrap=True)
    finish(fig, "fig-3-agent-gate")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_head_to_head()
    fig_samples()
    fig_gate()
    sys.exit(0)
