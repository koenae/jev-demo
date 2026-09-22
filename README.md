# TypeSafe Jev demo + talk

Demo-project en presentatie (20 min) over **TypeSafe Jev**, het "System One"-model dat
getypeerde beslissingen met gecalibreerde kansen teruggeeft in plaats van tekst.
De hele talk draait vanuit één marimo-notebook in slides-layout: geen PowerPoint.

```
jevdemo/        gedeelde demo-logica (sync functies die data teruggeven)
demos/          dunne CLI-wrappers met rich-output, elk met --record / --offline
presentation/   talk.py (marimo, slides-layout), talk.css, layouts/talk.slides.json
recordings/     opgenomen API-antwoorden voor offline-modus
scripts/        preflight.py, benchmark.py, selftest.py, helpers
exports/        talk.html en talk.pdf als fallback
```

> **Let op:** de bestanden in `recordings/` zijn op dit moment **synthetische placeholders**
> (`"source": "synthetic-placeholder"`). CLI en slides tonen daarvoor een rode badge.
> Vervang ze door echte opnames met de `--record`-commando's hieronder vóór de talk.

## Setup in 3 stappen

1. Installeer [uv](https://docs.astral.sh/uv/) en sync de omgeving (Python 3.12 wordt automatisch opgehaald):
   ```bash
   uv sync --all-groups
   ```
2. Maak `.env` aan en vul de keys in:
   ```bash
   cp .env.example .env
   # TYPESAFE_API_KEY=...            (demo 1, 2, 3)
   # LLM_PROVIDER=openai|anthropic|azure_openai, LLM_MODEL=..., + bijhorende key (demo 3)
   ```
   Alleen demo 3 gebruikt het LLM (de agent die tool calls plant); demo 1 en 2 praten enkel met
   TypeSafe. Heb je het model via **Microsoft Foundry**? Gebruik dan `LLM_PROVIDER=openai`,
   `OPENAI_API_KEY=<API Key uit "Call gpt-5-mini in code">` en
   `OPENAI_BASE_URL=https://<project>.services.ai.azure.com/openai/v1`.
3. Controleer alles:
   ```bash
   uv run python scripts/preflight.py
   ```

## De demo's

| Demo | Wat | Commando |
|---|---|---|
| 1 · Smart if | één ticket → één call → Choice + Score + Noul, met verdeling, confidence en latency | `uv run python demos/demo1_smart_if.py` |
| 2 · Confidence gate | 11 tickets, automatisch afhandelen boven de drempel, anders escaleren | `uv run python demos/demo2_confidence_gate.py [--threshold 0.75]` |
| 3 · Agent gate | LangChain-agent met gesimuleerde tools; Jev-middleware keurt elke tool call vooraf (destructief? productie? secrets?) | `uv run python demos/demo3_agent_gate.py` |
| 4 · Head-to-head | dezelfde 11 tickets en 6 tool calls door het LLM (structured output, zelfde criteria-tekst) én door Jev: mediaan/p95, tokens, kost per 1000 beslissingen, overeenstemming | `uv run python demos/demo4_head_to_head.py` |

Elke demo heeft dezelfde vlaggen:

- `--record` : roept de API aan én bewaart het antwoord in `recordings/<demo>.json`
- `--offline`: speelt de opname af, zonder netwerk of key

Demo 4 heeft het LLM én TypeSafe nodig. Zet `LLM_PRICE_INPUT_PER_MTOK` en
`LLM_PRICE_OUTPUT_PER_MTOK` (USD per miljoen tokens, van de prijspagina van je provider) in
`.env` voor de kostenkolommen; voor gpt-5-modellen is `LLM_REASONING_EFFORT=minimal` de
eerlijkste snelheidsvergelijking. De calls lopen 4 tegelijk.

Voor demo 3 wordt niets echt uitgevoerd: de shell-, SQL- en file-tools zijn nep en geven
vaste tekst terug. De LLM (OpenAI, Anthropic of Azure OpenAI, zie `.env.example`) plant
de tool calls, Jev beoordeelt ze.

## De talk starten (presentatiemodus)

```bash
uv run marimo run presentation/talk.py
```

Dit opent het notebook als app in de **slides-layout** (`presentation/layouts/talk.slides.json`):
pijltjestoetsen navigeren, demo 2 heeft een fragment (nog eens → drukken).
Bovenaan de titelslide staat de globale schakelaar **LIVE API** (aan = echte calls,
uit = `recordings/`) en een knop om de demo's opnieuw uit te voeren.
De schakelaar staat standaard aan wanneer `TYPESAFE_API_KEY` gezet is; forceer offline met:

```bash
uv run marimo run presentation/talk.py -- --offline
```

Om aan de slides te werken: `uv run marimo edit presentation/talk.py` (kies rechtsboven
de slides-layout; de app-view zonder code is de presentatieweergave).
Zet de browser fullscreen (F11) op de projector.

## Exporteren naar HTML / PDF (fallback)

```bash
uv run marimo export html presentation/talk.py -o exports/talk.html --force --no-include-code -- --offline
uv run marimo export pdf  presentation/talk.py -o exports/talk.pdf --as=slides --no-include-inputs --raster-server=live -- --offline
```

De PDF-export gebruikt nbconvert + Playwright (in de `export`-dependency-group). Als
Playwright zijn browser mist: `uv run playwright install chromium`.

## Offline-modus gebruiken

1. Neem, terwijl je online bent, alles op:
   ```bash
   uv run python demos/demo1_smart_if.py --record
   uv run python demos/demo2_confidence_gate.py --record
   uv run python demos/demo3_agent_gate.py --record
   uv run python demos/demo4_head_to_head.py --record
   uv run python scripts/benchmark.py --calls 10 --location "België (…), …"
   ```
2. Op de dag zelf: `uv run python scripts/preflight.py`. Faalt het netwerk, zet dan de
   schakelaar op de titelslide uit (of start met `-- --offline`); de CLI-demo's draaien
   met `--offline`.

`scripts/make_placeholder_recordings.py` schrijft synthetische placeholders (duidelijk
gemarkeerd) zodat de slides ook zonder echte opnames renderen; echte opnames overschrijft
het niet zonder `--force`.

## Verdere scripts

- `scripts/preflight.py` : keys, connectiviteit, latency naar TypeSafe en het LLM, recordings, exports
- `scripts/benchmark.py` : mediaan / p95 over N calls per demo → `recordings/latency_benchmark.json` (slide 10)
- `scripts/selftest.py`  : draait alle demo-codepaden tegen een nep-transport, zonder key of netwerk
- `scripts/make_slides_layout.py` : genereert `layouts/talk.slides.json` uit de celnamen in `talk.py`

Speaker notes, gemeten latencies, versies en valkuilen: zie [TALK_NOTES.md](TALK_NOTES.md).
