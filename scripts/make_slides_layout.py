"""Generate presentation/layouts/talk.slides.json from the cell names in talk.py.

marimo's slides layout lists one entry per notebook cell, in order. Cell names decide
the type: `setup_*` -> skip, `frag_*` -> fragment (same slide as the previous cell),
everything else -> a new slide. Speaker notes come from NOTES below.

    uv run python scripts/make_slides_layout.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "presentation" / "talk.py"
LAYOUT = ROOT / "presentation" / "layouts" / "talk.slides.json"

NOTES = {
    "slide_01_title": "Schakelaar: LIVE aan = echte API-calls; uit = recordings/. Knop 'opnieuw' herhaalt de demo's.",
    "slide_02_hook": "Iedereen heeft dit geschreven. Het probleem is niet het LLM, het is dat tekst geen type is.",
    "slide_03_system1_vs_2": "Kahneman: snel/intuïtief vs traag/bewust. Jev is System 1 voor je code.",
    "slide_04_jev_vs_llm": "Geen tekst, wel kansen. Meerdere vragen per call, parallel beantwoord.",
    "slide_05_primitives": "Dit is de echte code uit demo 1. Choice/Score hebben confidence; Noul is zelf een kans.",
    "slide_06_demo1": "Live: één call, drie antwoorden. Wijs op de verdeling en de latency.",
    "slide_07_demo2": "Elf tickets, een paar bewust ambigu. Dan de slider: geen nieuwe API-calls.",
    "slide_08_agent_loop": "Routing, gates, compaction, evals. Code houdt de controle.",
    "slide_09_demo3": "Het hoogtepunt: DROP TABLE op productie en het secrets-bestand worden geblokkeerd.",
    "slide_10_claims_vs_measured": "Vendor-claims naast eigen metingen. Rode badge = placeholder, nog niet gemeten.",
    "slide_10b_head_to_head": "Zelfde tickets en tool calls, zelfde criteria-tekst, twee systemen. Snelheid, kost en hoe vaak ze het eens zijn.",
    "slide_11_caveats": "Early access, alpha-packages, geen reasoning, calibratie is geen correctheid.",
    "slide_12_takeaway": "Laat het LLM praten en plannen, laat System 1 kiezen. Repo-link.",
}


def main() -> int:
    names = re.findall(r"^def (\w+)\(", NOTEBOOK.read_text(encoding="utf-8"), flags=re.M)
    cells = []
    for name in names:
        if name.startswith("setup_"):
            entry = {"type": "skip"}
        elif name.startswith("frag_"):
            entry = {"type": "fragment"}
        else:
            entry = {"type": "slide"}
        if name in NOTES:
            entry["speakerNotes"] = NOTES[name]
        cells.append(entry)
    layout = {"type": "slides", "data": {"cells": cells, "deck": {"transition": "none", "verticalAlign": "top"}}}
    LAYOUT.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT.write_text(json.dumps(layout, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{LAYOUT}: {len(cells)} cells, {sum(c['type'] == 'slide' for c in cells)} slides")
    return 0


if __name__ == "__main__":
    sys.exit(main())
