"""Render the LinkedIn cover image for the Jev post: a book-cover style card in the spirit of
"Thinking, Fast and Slow", with FAST and SLOW struck through and replaced by System 1 / System 2.

    uv run --group blog python scripts/linkedin_cover.py   # writes blog/jev-vs-llm/linkedin-cover.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "blog" / "jev-vs-llm" / "linkedin-cover.png"
INK, INK2, PAPER, BG = "#1a1a19", "#77766f", "#fbfaf8", "#e9e6df"
JEV, LLM = "#2a78d6", "#eb6834"

W, H = 1200, 627
fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
fig.patch.set_facecolor(BG)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

# the book: a plain cover with a spine shadow, wide enough to hold the corrections
ax.add_patch(Rectangle((252, 44), 710, 540, facecolor="#cfcbc2", edgecolor="none"))
ax.add_patch(FancyBboxPatch((240, 52), 710, 540, boxstyle="round,pad=0,rounding_size=6",
                            facecolor=PAPER, edgecolor="#d6d3cb", linewidth=1.5))
ax.add_patch(Rectangle((240, 52), 14, 540, facecolor="#e2dfd7", edgecolor="none"))

serif = {"family": "DejaVu Serif", "color": INK}
ax.text(300, 500, "THINKING,", fontsize=40, fontweight="bold", ha="left", **serif)
ax.text(300, 385, "FAST", fontsize=64, fontweight="bold", ha="left", **serif)
ax.text(300, 318, "AND", fontsize=30, ha="left", **serif)
ax.text(300, 225, "SLOW", fontsize=64, fontweight="bold", ha="left", **serif)

# marker strike through the word, and the correction written to the right of it, slightly tilted
for y, color, word, note, x1 in ((385, JEV, "System 1", "Jev, 338 ms", 530),
                                 (225, LLM, "System 2", "gpt-5-mini, 1,595 ms", 562)):
    mid = y + 30
    ax.plot([292, x1], [mid - 6, mid + 4], color=color, linewidth=10, solid_capstyle="round", alpha=0.9)
    ax.text(640, mid + 14, word, fontsize=34, fontweight="bold", fontstyle="italic", color=color,
            family="DejaVu Sans", ha="left", va="center", rotation=-4)
    ax.text(642, mid - 30, note, fontsize=15, color=INK2, family="DejaVu Sans", ha="left", va="center")

ax.text(300, 100, "Same decisions, sent to both. Median latency per decision.", fontsize=16, color=INK2, family="DejaVu Sans", ha="left")

fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
