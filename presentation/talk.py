import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="full",
    app_title="TypeSafe Jev - een if-statement dat je code niet kan schrijven",
    layout_file="layouts/talk.slides.json",
    css_file="talk.css",
)


@app.cell(hide_code=True)
def setup_imports():
    import html as _html
    import sys
    from pathlib import Path

    import marimo as mo

    try:
        ROOT = Path(__file__).resolve().parent.parent
    except NameError:  # pragma: no cover - older marimo without __file__
        ROOT = Path(mo.notebook_dir()).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from jevdemo import agent_gate, confidence_gate, head_to_head, questions, smart_if, snippets
    from jevdemo.config import load_env, package_versions
    from jevdemo.errors import DemoError
    from jevdemo.latency import LatencyStats
    from jevdemo.recording import load_recording

    load_env()
    CSS = (ROOT / "presentation" / "talk.css").read_text(encoding="utf-8")
    esc = _html.escape
    return (
        CSS,
        DemoError,
        LatencyStats,
        ROOT,
        agent_gate,
        confidence_gate,
        esc,
        head_to_head,
        load_recording,
        mo,
        package_versions,
        questions,
        smart_if,
        snippets,
    )


@app.cell(hide_code=True)
def setup_helpers(CSS, DemoError, esc, mo):
    def slide(title, *parts, h="h2"):
        body = "".join(p if isinstance(p, str) else p.text for p in parts)
        return mo.Html(f'<div class="jev-slide"><{h}>{title}</{h}>{body}</div>')

    def md(text):
        return mo.md(text).text

    def code(src, lang="python", size="1.2rem"):
        return f'<div class="jev-code" style="font-size:{size}">' + mo.md(f"```{lang}\n{src}\n```").text + "</div>"

    def badge(origin):
        label = {
            "live": "LIVE - net opgehaald bij api.typesafe.ai",
            "recording": "OFFLINE - opgenomen API-antwoord",
            "placeholder": "OFFLINE - SYNTHETISCHE PLACEHOLDER, geen echte Jev-output",
        }[origin]
        return f'<span class="jev-badge {origin}">{label}</span>'

    def bar(p, cls=""):
        width = max(0, min(100, round(p * 100)))
        return (
            f'<span class="jev-bar-track"><span class="jev-bar {cls}" '
            f'style="width:{width}%"></span></span> <span class="jev-mono">{p:.2f}</span>'
        )

    def table(headers, rows, cls=""):
        head = "".join(f"<th>{h}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return f'<table class="jev-table {cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'

    def stat(value, label):
        return f'<div class="jev-stat"><div class="v">{value}</div><div class="l">{label}</div></div>'

    def error_view(error):
        if isinstance(error, DemoError):
            message, hint = error.message, error.hint
        else:
            message, hint = f"{type(error).__name__}: {error}", None
        hint = hint or "Zet de schakelaar op de titelslide op OFFLINE en probeer opnieuw."
        return mo.callout(
            mo.md(
                f"### Demo kon niet live draaien\n\n{esc(message)}\n\n"
                f"**Wat nu?** {esc(hint)}  \n"
                "Schakel bovenaan naar **offline** (recordings/) om de opgenomen antwoorden te tonen."
            ),
            kind="danger",
        )

    style_tag = f"<style>{CSS}</style>"
    return badge, bar, code, error_view, md, slide, stat, style_tag, table


@app.cell(hide_code=True)
def slide_01_title(mo, style_tag):
    import os

    _args = mo.cli_args()
    _default_live = bool(os.environ.get("TYPESAFE_API_KEY")) and not _args.get("offline", False)
    mode_switch = mo.ui.switch(value=_default_live, label="**LIVE API** (uit = offline, recordings/)")
    rerun = mo.ui.run_button(label="opnieuw uitvoeren")

    mo.vstack(
        [
            mo.Html(
                style_tag
                + """
<div class="jev-slide" style="text-align:center; padding-top:3rem">
  <h1>Een if-statement dat je code niet kan schrijven</h1>
  <p class="jev-sub">TypeSafe <b>Jev</b>: een "System One"-model dat getypeerde beslissingen geeft, geen tekst</p>
  <p class="jev-dim" style="margin-top:2rem">20 minuten · slides + live demo · alles in één marimo-notebook</p>
</div>"""
            ),
            mo.hstack([mode_switch, rerun], justify="center", gap=2),
        ]
    )
    return mode_switch, rerun


@app.cell(hide_code=True)
def setup_mode(mode_switch):
    mode = "live" if mode_switch.value else "offline"
    return (mode,)


@app.cell(hide_code=True)
def slide_02_hook(code, md, slide):
    slide(
        "De hook: LLM-output parsen is fragiel",
        '<div class="jev-cols" style="grid-template-columns: 1.3fr 0.7fr">',
        code(
            'prompt = f"""Classify this ticket as billing, technical or sales.\n'
            'Answer with ONLY the label.\n\n{ticket}"""\n'
            "label = llm(prompt).strip().lower()\n\n"
            'if label == "billing":          # "Billing.", "billing (probably)",\n'
            "    route_to_billing()          # \"I'd say billing\", ...\n"
            "else:\n"
            "    ...                         # en hoe zeker was het model eigenlijk?",
            size="1.15rem",
        ),
        md(
            "- Tekst → string-parsing → **retries, regexes, JSON-mode, schema-validators**\n"
            "- Je krijgt een antwoord, maar **geen kans** dat het klopt\n"
            "- 1–3 s en een paar cent per beslissing"
        ),
        "</div>",
        '<p class="jev-big" style="margin-top:1.5rem">Wat we eigenlijk willen: <span class="jev-mono">if P(billing) &gt; 0.8:</span></p>',
    )
    return


@app.cell(hide_code=True)
def slide_03_system1_vs_2(md, slide):
    slide(
        "System 1 vs System 2 (Kahneman)",
        '<div class="jev-cols">',
        '<div class="jev-card ok"><h3>System 1 · snel, intuïtief</h3>',
        md(
            "- Herkennen, inschatten, kiezen\n"
            "- Milliseconden, geen redenering\n"
            "- *\"Dit is een billing-ticket, en dringend\"*\n\n"
            "**→ Jev** (System One-model)"
        ),
        "</div>",
        '<div class="jev-card"><h3>System 2 · traag, bewust</h3>',
        md(
            "- Redeneren, plannen, schrijven\n"
            "- Seconden, stap voor stap\n"
            "- *\"Laat me dit ticket eens goed lezen en een antwoord opstellen\"*\n\n"
            "**→ LLM** (GPT, Claude, ...)"
        ),
        "</div></div>",
        md("Beide heb je nodig. De vraag is: **welke beslissingen laat je System 2 nemen die eigenlijk System 1-werk zijn?**"),
    )
    return


@app.cell(hide_code=True)
def slide_04_jev_vs_llm(slide, table):
    slide(
        "Jev vs LLM",
        table(
            ["", "LLM", "Jev"],
            [
                ["Input", "prompt (tekst)", "<b>state</b> (string/JSON) + <b>getypeerde vragen</b>"],
                ["Output", "tekst, hopelijk in het juiste formaat", "<b>getypeerd antwoord + kansen</b>, schema-conform gegarandeerd"],
                ["Redenering", "chain-of-thought, uitleg", "<b>geen</b> (er komt geen reasoning terug)"],
                ["Latency", "1–10 s", "70–500 ms <span class='jev-dim'>(vendor-claim)</span>"],
                ["Prijs", "€ per M tokens in + uit", "$0.042 / M input-tokens, output gratis <span class='jev-dim'>(vendor)</span>"],
                ["Goed in", "genereren, redeneren", "kiezen, scoren, ja/nee — <b>gecalibreerd</b>"],
            ],
        ),
        '<p style="margin-top:1rem">Meerdere vragen over dezelfde state gaan in <b>één call</b> en worden parallel beantwoord.</p>',
    )
    return


@app.cell(hide_code=True)
def slide_05_primitives(code, md, questions, slide, smart_if, snippets):
    slide(
        "Drie primitives + confidence",
        md("**Confidence** = hoe geconcentreerd de verdeling is. Niet: hoe *juist* het antwoord is."),
        '<div class="jev-cols" style="grid-template-columns: 1.3fr 1fr">',
        "<div>"
        + code(snippets.constant_source(smart_if, "QUESTIONS"), size="1.1rem")
        + code(snippets.constant_source(questions, "URGENCY_LEVELS"), size="1.1rem")
        + "</div>",
        '<div class="jev-cols-3" style="grid-template-columns:1fr; gap:0.8rem">',
        '<div class="jev-card"><h3>Choice</h3>',
        md("kies één optie → `.choice`, `.probabilities` (som ≈ 1), `.confidence`"),
        '</div><div class="jev-card"><h3>Score</h3>',
        md("niveau op een geordende rubriek → `.score` (gewogen), `.probabilities` per niveau, `.confidence`"),
        '</div><div class="jev-card"><h3>Noul</h3>',
        md("ja/nee → `.noul` = P(ja). Geen aparte confidence: 0.5 betekent *weet het niet*"),
        "</div></div></div>",
    )
    return


@app.cell(hide_code=True)
def slide_06_demo1(badge, bar, code, error_view, esc, md, mode, rerun, slide, smart_if, snippets, stat, table):
    rerun.value  # re-run when the button on the title slide is clicked
    try:
        r1 = smart_if.run_smart_if(mode)
    except Exception as error:  # noqa: BLE001 - never show a traceback on stage
        r1 = None
        _out = error_view(error)
    if r1 is not None:
        _p = r1.team.probabilities
        _team_rows = [[k, bar(v, "win" if k == r1.team.choice else "")] for k, v in sorted(_p.items(), key=lambda kv: -kv[1])]
        _urg_rows = [[f"{lvl} · {r1.urgency.legend[lvl].split(';')[0]}", bar(v, "win" if lvl == r1.urgency.level else "")] for lvl, v in sorted(r1.urgency.probabilities.items())]
        _out = slide(
            "Demo 1 · Smart if",
            badge(r1.origin),
            f'<p class="jev-dim" style="margin:0.4rem 0 0.6rem 0">{esc(r1.ticket)}</p>',
            '<div class="jev-cols" style="grid-template-columns: 1.3fr 0.7fr">',
            "<div>",
            code(snippets.source_of(smart_if.smart_if), size="1.05rem"),
            md(f"**{r1.meta.latency_ms:.0f} ms** · één call · model `{r1.meta.model}` · {r1.meta.input_tokens} input-tokens"),
            "</div><div>",
            '<div class="jev-cols-3">',
            stat(r1.team.choice, f"team · conf. {r1.team.confidence:.2f}"),
            stat(f"{r1.urgency.level}/2", f"urgency · {r1.urgency.legend[r1.urgency.level].split(';')[0]}"),
            stat("ja" if r1.refund.yes else "nee", f"refund? · P(ja) {r1.refund.noul:.2f}"),
            "</div>",
            table(["team", "P"], _team_rows, cls="compact"),
            table(["urgency", "P"], _urg_rows, cls="compact"),
            "</div></div>",
        )
    _out
    return


@app.cell(hide_code=True)
def slide_07_demo2(badge, code, confidence_gate, error_view, md, mo, mode, rerun, slide, snippets):
    rerun.value
    threshold_slider = mo.ui.slider(
        start=0.5, stop=0.99, step=0.01, value=confidence_gate.DEFAULT_THRESHOLD,
        show_value=True, full_width=True,
    )
    try:
        gate_result = confidence_gate.run_confidence_gate(mode)
        _top = slide(
            "Demo 2 · Confidence gate",
            badge(gate_result.origin),
            code(snippets.source_of(confidence_gate.gate), size="1.3rem"),
            md(
                f"{len(gate_result.decisions)} tickets, één call per ticket · confidence ≥ drempel → **automatisch** · "
                "eronder → **mens** kijkt mee · de slider herrekent **zonder** nieuwe API-calls"
            ),
        )
    except Exception as error:  # noqa: BLE001
        gate_result = None
        _top = error_view(error)
    mo.vstack([_top, mo.hstack([mo.md("**confidence-drempel**"), threshold_slider], align="center", gap=1, widths=[1, 8])])
    return gate_result, threshold_slider


@app.cell(hide_code=True)
def frag_07_demo2_table(LatencyStats, bar, confidence_gate, esc, mo, gate_result, stat, table, threshold_slider):
    mo.stop(gate_result is None, mo.md("*(geen resultaten - zie foutmelding hierboven)*"))
    _t = threshold_slider.value
    _summary = confidence_gate.gate(gate_result.decisions, _t)
    _rows = []
    for _d in gate_result.decisions:
        _auto = _d.team.confidence >= _t
        _rows.append([
            _d.ticket_id,
            esc(_d.text[:58] + ("…" if len(_d.text) > 58 else "")),
            _d.team.choice,
            bar(_d.team.confidence, "win" if _auto else "red"),
            f"{_d.urgency.level}",
            f"{_d.meta.latency_ms:.0f}",
            '<span class="jev-auto">auto</span>' if _auto else '<span class="jev-escalate">ESCALATIE</span>',
        ])
    _stats = LatencyStats.of(gate_result.latencies_ms)
    mo.Html(
        '<div class="jev-slide">'
        + '<div class="jev-cols-3">'
        + stat(f"{_summary.auto_pct:.0f}%", f"automatisch ({_summary.auto_count})").replace("jev-stat", "jev-stat small")
        + stat(f"{_summary.escalated_pct:.0f}%", f"escalatie ({_summary.escalated_count})").replace("jev-stat", "jev-stat small")
        + stat(f"{_summary.total_ms / 1000:.1f} s", f"totale API-tijd · mediaan {_stats.median_ms:.0f} ms / p95 {_stats.p95_ms:.0f} ms").replace("jev-stat", "jev-stat small")
        + "</div>"
        + table(["", "ticket", "team", f"confidence (drempel {_t:.2f})", "urg.", "ms", "beslissing"], _rows, cls="compact")
        + "</div>"
    )
    return


@app.cell(hide_code=True)
def slide_08_agent_loop(md, slide):
    slide(
        "Waar Jev in een agent-loop past",
        '<div class="jev-flow">'
        '<span class="box">user</span><span class="arrow">→</span>'
        '<span class="box jev">Jev: routing</span><span class="arrow">→</span>'
        '<span class="box">LLM plant</span><span class="arrow">→</span>'
        '<span class="box jev">Jev: gate</span><span class="arrow">→</span>'
        '<span class="box">tool</span><span class="arrow">→</span>'
        '<span class="box jev">Jev: eval</span><span class="arrow">↺</span>'
        "</div>",
        '<div class="jev-cols" style="margin-top:1.5rem">',
        md(
            "**Routing** · welk model / welke agent / welke tool-set?  \n"
            "`ModelRouterMiddleware` in langchain-typesafe\n\n"
            "**Gates** · mag deze tool call? is dit klaar? moet een mens kijken?  \n"
            "`AutoModeMiddleware` (1 risk-vraag) of je eigen middleware"
        ),
        md(
            "**Compaction** · welke berichten zijn nog relevant voor de context?\n\n"
            "**Evals** · is dit antwoord correct / veilig / on-topic? — per turn, in ms\n\n"
            "Code houdt de controle; Jev levert *programmable common sense*"
        ),
        "</div>",
    )
    return


@app.cell(hide_code=True)
def slide_09_demo3(agent_gate, badge, bar, code, error_view, esc, md, mode, rerun, slide, snippets, table):
    rerun.value
    try:
        r3 = agent_gate.run_agent_gate(mode)
    except Exception as error:  # noqa: BLE001
        r3 = None
        _out = error_view(error)
    if r3 is not None:
        _rows = []
        for _i, _d in enumerate(r3.decisions, 1):
            _args = ", ".join(f"{k}={(str(v)[:30] + ('…' if len(str(v)) > 30 else ''))!r}" for k, v in _d.args.items())
            _p = _d.probabilities
            _verdict = (
                f'<span class="jev-blocked">GEBLOKKEERD</span> <span class="jev-dim">{esc(_d.reason)}</span>'
                if _d.blocked else '<span class="jev-allowed">toegelaten</span>'
            )
            _rows.append([
                _i,
                f'<span class="jev-mono">{esc(_d.tool)}({esc(_args)})</span>',
                bar(_p["destructive"], "red" if _p["destructive"] >= 0.5 else ""),
                bar(_p["production"], "red" if _p["production"] >= 0.5 else ""),
                bar(_p["secrets"], "red" if _p["secrets"] >= 0.5 else ""),
                f"{_d.latency_ms:.0f}",
                _verdict,
            ])
        _out = slide(
            "Demo 3 · Agent gate — Jev keurt elke tool call vooraf",
            badge(r3.origin),
            '<div class="jev-cols" style="grid-template-columns: 1.2fr 0.8fr">',
            code(snippets.source_of(agent_gate.JevToolGate.wrap_tool_call, max_lines=16), size="0.95rem"),
            code(snippets.source_of(agent_gate.decide, max_lines=9), size="0.95rem"),
            "</div>",
            table(["#", "tool call", "destructief?", "productie?", "lekt secrets?", "ms", "beslissing"], _rows, cls="compact"),
            md(
                f"LLM: `{r3.llm}` · {len(r3.decisions)} tool calls, **{len(r3.blocked)} geblokkeerd** · "
                f"agent-run {r3.total_ms / 1000:.1f} s · tools zijn gesimuleerd, er wordt niets uitgevoerd"
            ),
            f'<p class="jev-dim" style="margin-top:0.3rem"><b>Rapport van de agent:</b> {esc(r3.final_answer[:260])}{"…" if len(r3.final_answer) > 260 else ""}</p>',
        )
    _out
    return


@app.cell(hide_code=True)
def slide_10_claims_vs_measured(badge, esc, load_recording, md, slide, smart_if, table):
    try:
        _bench = load_recording("latency_benchmark")
        _data = _bench["data"]
        _origin = "placeholder" if _bench.get("source") == "synthetic-placeholder" else "recording"
        _rows = []
        for _name, _r in _data["results"].items():
            _rows.append([_name.replace("_", " "), _r["n"], f"{_r['median_ms']:.0f} ms", f"{_r['p95_ms']:.0f} ms", f"{_r['min_ms']:.0f}–{_r['max_ms']:.0f} ms"])
        _measured = table(["demo", "n", "mediaan", "p95", "min–max"], _rows)
        _where = _data.get("location") or "locatie onbekend"
        if _origin == "placeholder":
            _where = "nog niet gemeten (run scripts/benchmark.py)"
        _bench_badge = badge(_origin)
    except Exception as error:  # noqa: BLE001
        _measured = f"<p>geen benchmark gevonden ({error})</p>"
        _where, _bench_badge = "-", ""
    _tokens = 236
    try:
        _tokens = smart_if.run_smart_if("offline").meta.input_tokens or _tokens
    except Exception:  # noqa: BLE001
        pass
    slide(
        "Vendor-claims vs wat ik vanuit België mat",
        '<div class="jev-cols">',
        '<div class="jev-card"><h3>Claims van TypeSafe</h3>',
        md(
            "- latency **70–500 ms**\n"
            "- input **$0.042 / M tokens**, output gratis\n"
            "- *\"193.6× sneller / 444.6× goedkoper\"* dan een LLM-workflow, op hun **eigen** workflow-evals — zelf noemen ze dat de bovengrens\n"
            "- service draait aan de **US West Coast**"
        ),
        "</div>",
        f'<div class="jev-card ok"><h3>Gemeten vanuit België</h3><p class="jev-dim">{esc(_where)}</p>',
        _bench_badge,
        _measured,
        md(
            f"Demo 1 kost ~{_tokens} input-tokens → **${_tokens * 0.042 / 1_000_000:.6f}** per beslissing. "
            "Amsterdam–Californië alleen al is ~140 ms RTT: de vloer voor EU-gebruikers ligt hoger dan de vendor-vloer."
        ),
        "</div></div>",
    )
    return


@app.cell(hide_code=True)
def slide_10b_head_to_head(badge, error_view, head_to_head, md, mode, rerun, slide, stat, table):
    rerun.value
    try:
        r4 = head_to_head.run_head_to_head(mode)
    except Exception as error:  # noqa: BLE001
        r4 = None
        _out = error_view(error)
    if r4 is not None:
        _sum = head_to_head.summarize(r4)
        _rows = []
        for (_task, _system), _s in _sum.items():
            _cost = "n/a" if _s.cost_per_1000_usd is None else f"${_s.cost_per_1000_usd:.4f}"
            _cls = "jev-auto" if _system == "jev" else ""
            _rows.append([
                _task, f'<span class="{_cls}">{_system}</span>', _s.n,
                f"{_s.latency.median_ms:.0f} ms", f"{_s.latency.p95_ms:.0f} ms",
                f"{_s.input_tokens} / {_s.output_tokens}", _cost,
            ])
        _stats = ""
        for _task in ("triage", "gate"):
            _lat, _cost = head_to_head.speedup(_sum, _task)
            _agree = head_to_head.agreement(r4, _task)
            _agree_txt = ", ".join(f"{k} {v:.0%}" for k, v in _agree.items())
            _mean = sum(_agree.values()) / len(_agree) if _agree else 0.0
            _stats += stat(f"{_lat:.1f}×" if _lat else "–", f"{_task}: sneller (mediaan)")
            _stats += stat(f"{_cost:.0f}×" if _cost else "n/a", f"{_task}: goedkoper")
            _stats += stat(f"{_mean:.0%}", f"{_task}: zelfde antwoord ({_agree_txt})")
        _out = slide(
            "Head-to-head · dezelfde beslissingen door het LLM en door Jev",
            badge(r4.origin),
            f'<div class="jev-cols-3" style="grid-template-columns: repeat(6, 1fr)">{_stats}</div>',
            table(["taak", "systeem", "n", "mediaan", "p95", "tokens in / uit", "kost per 1000"], _rows, cls="compact"),
            md(
                f"LLM: `{r4.llm}` met structured output en **dezelfde criteria-tekst** · "
                f"Jev: `{r4.jev_model}` · {r4.workers} calls parallel · "
                "kost: Jev $0.042 / M input-tokens (vendor), LLM volgens `LLM_PRICE_*` in `.env` · "
                "*zelfde antwoord* is overeenstemming tussen de twee, geen ground truth"
            ),
        )
    _out
    return


@app.cell(hide_code=True)
def slide_11_caveats(md, package_versions, slide):
    _v = package_versions()
    slide(
        "Kanttekeningen",
        '<div class="jev-cols">',
        md(
            "- **Early access**: API en modelnamen kunnen nog bewegen (`jev-latest` is een alias)\n"
            "- **Vendor-benchmarks**: 193×/444× zijn hun cijfers op hun workflows\n"
            "- **Latency vanuit de EU**: server aan de US West Coast, reken op de RTT er bovenop\n"
            "- **Alpha-packages**: `langchain-typesafe` "
            f"{_v.get('langchain-typesafe')}, eerste release 17 sept 2026; `typesafe-sdk` {_v.get('typesafe-sdk')}"
        ),
        md(
            "- **Geen reasoning-output**: je krijgt kansen, geen *waarom* — debuggen = state en vragen aanpassen\n"
            "- **Gecalibreerd ≠ correct**: typed output garandeert de interface, niet de waarheid; valideer op je eigen data\n"
            "- **Confidence** meet concentratie van de verdeling, geen toestemming om te handelen\n"
            "- Drempels zijn **beleid in code**: evalueer ze op je eigen consequenties"
        ),
        "</div>",
    )
    return


@app.cell(hide_code=True)
def slide_12_takeaway(md, slide):
    slide(
        "Takeaway",
        '<p class="jev-big">Laat het LLM praten en plannen. Laat System 1 kiezen.</p>',
        md(
            "- Beslissingen die nu via *prompt → tekst → parse* lopen, zijn kandidaten voor **Choice / Score / Noul**\n"
            "- Kansen + drempel in **jouw** code = een gate die je kan testen, loggen en bijsturen\n"
            "- Begin met één *smart if* in een bestaande flow; meet latency en kwaliteit op je eigen data"
        ),
        '<p style="margin-top:2rem" class="jev-big jev-mono">github.com/koenae/jev-demo</p>',
        '<p class="jev-dim">alle demo\'s: <span class="jev-mono">uv run python demos/demo1_smart_if.py --offline</span> · slides: <span class="jev-mono">uv run marimo run presentation/talk.py</span></p>',
    )
    return


if __name__ == "__main__":
    app.run()
