# Speaker notes · TypeSafe Jev, "een if-statement dat je code niet kan schrijven"

20 minuten: ~9 min slides, ~9 min demo's, ~2 min buffer. Alles vanuit `presentation/talk.py`.

> **Status van de data in deze repo (21 sept 2026):** de recordings en de latency-tabel zijn
> **synthetische placeholders**. In de omgeving waarin dit project gebouwd is waren
> `api.typesafe.ai`, `docs.typesafe.ai`, `docs.langchain.com`, `docs.marimo.io` en
> `api.openai.com` geblokkeerd door de egress-proxy en was er geen `TYPESAFE_API_KEY`.
> Zie "Afwijkingen van de opdracht" onderaan voor wat je zelf nog moet doen.

## Per slide

1. **Titel.** Zeg wat het publiek gaat zien: drie demo's, allemaal live, met een offline-vangnet. Wijs de schakelaar aan; laat hem aan staan als preflight groen was.
2. **Hook.** Iedereen heeft dit ooit geschreven: prompt → tekst → `.strip().lower()` → bidden. Het probleem is niet het LLM, het is dat tekst geen type is en geen kans meegeeft. Wat we willen is `if P(billing) > 0.8:`.
3. **System 1 vs System 2.** Kahneman: snel/intuïtief vs traag/bewust. LLM's zijn System 2 die we misbruiken voor System 1-werk. Jev is System 1 voor je code: herkennen, inschatten, kiezen, in milliseconden.
4. **Jev vs LLM.** Input is state + getypeerde vragen, output is getypeerd + kansen, schema-conform gegarandeerd, geen reasoning. Meerdere vragen over dezelfde state in één call, parallel beantwoord. De latency/prijs-cijfers zijn vendor-claims, dat zeg je er meteen bij.
5. **Primitives.** Dit is de echte code van demo 1. Choice: verdeling over labels + confidence. Score: geordende rubriek, `.score` is het gewogen gemiddelde, kan tussen niveaus vallen. Noul: één kans, 0.5 = "weet het niet", geen aparte confidence. Confidence = concentratie van de verdeling, niet correctheid.
6. **Demo 1.** Zie hieronder.
7. **Demo 2.** Zie hieronder. Druk → voor het fragment met de tabel; dan de slider.
8. **Agent-loop.** Vier plekken: routing (welk model/agent, `ModelRouterMiddleware`), gates (mag deze tool call, `AutoModeMiddleware` of eigen middleware), compaction (wat is nog relevant), evals (is dit antwoord ok, per turn in ms). Code houdt de controle.
9. **Demo 3.** Zie hieronder. Het hoogtepunt van de talk.
10. **Claims vs metingen.** Vendor: 70–500 ms, $0.042/MTok input, output gratis, "193.6× / 444.6×" op hun eigen workflow-evals (bovengrens, zeggen ze zelf), US West Coast. Daarnaast jouw metingen. Rode badge = nog niet gemeten.
11. **Kanttekeningen.** Early access; vendor-benchmarks; EU-latency (RTT naar de westkust komt er bovenop); alpha-packages (`langchain-typesafe` 0.0.1a3, eerste release 17 sept 2026); geen reasoning-output; gecalibreerd ≠ correct; confidence is geen toestemming.
12. **Takeaway.** Laat het LLM praten en plannen, laat System 1 kiezen. Begin met één smart if in een bestaande flow. Repo-link.

## Per demo

### Demo 1 · Smart if (`jevdemo/smart_if.py`)
- **Wat het publiek moet zien:** één ticket, één call, drie getypeerde antwoorden. Wijs op de volledige verdeling (billing vs technical: het ticket gaat over beide), de confidence, `refund` als kans, en de latency in ms. Zeg hardop: hier staat geen regex.
- **Als live faalt:** de cel toont een rode callout met de reden en de hint. Zet de schakelaar op de titelslide uit → de opname verschijnt met een gele (echte opname) of rode (placeholder) badge. CLI-alternatief: `uv run python demos/demo1_smart_if.py --offline`.

### Demo 2 · Confidence gate (`jevdemo/confidence_gate.py`)
- **Wat het publiek moet zien:** 11 tickets (T-105, T-109, T-111 bewust ambigu), tabel per ticket met team, confidence-balk, urgency, ms en beslissing; daarna de samenvatting (x% automatisch, y% escalatie, totale API-tijd, mediaan/p95). Schuif de slider: alleen de verdeling verandert, er gaat geen call de deur uit. De gate (`gate()`) is vijf regels pure code.
- **Als live faalt:** zelfde vangnet. Let op: live duurt ~11 sequentiële calls (verwacht 4–8 s); vertel intussen wat de tickets zijn. Parallel batchen is triviaal maar bewust niet gedaan zodat de per-call latency zichtbaar blijft.

### Demo 3 · Agent gate (`jevdemo/agent_gate.py`)
- **Wat het publiek moet zien:** de taak vraagt de agent om o.a. `DROP TABLE … in orders-production` en `/etc/app/secrets.env` te lezen. De middleware stelt per tool call drie Noul-vragen (destructief? productie? secrets?) en het beleid staat in `decide()`: secrets ≥ 0.5 of (destructief ≥ 0.5 én productie ≥ 0.5) → blokkeren. `df -h` en de SELECT gaan door; de DROP en het secrets-bestand worden geblokkeerd, het LLM krijgt een error-ToolMessage en rapporteert dat netjes. Tools zijn gesimuleerd: er wordt niets uitgevoerd.
- **Als live faalt:** het LLM is de grootste onzekerheid (traag, rate limits, andere tool calls dan verwacht). Offline speelt de **volledige** opgenomen trace af (beslissingen, transcript, eindrapport). Als het LLM live andere calls doet: prima, de gate-beslissingen zijn dan gewoon anders; het punt is dat de DROP op productie geblokkeerd wordt. Blokkeert Jev niets (kansen < 0.5)? Toon de kansen en zeg dat het beleid in code zit: één regel aanpassen. CLI: `uv run python demos/demo3_agent_gate.py --offline`.

## Gemeten latencies vanuit België

**Nog niet gemeten.** `recordings/latency_benchmark.json` bevat placeholderwaarden
(`"source": "synthetic-placeholder"`); slide 10 toont daarvoor een rode badge.

Meet zelf, minstens 10 calls per demo, en vul de tabel hieronder in:

```bash
uv run python scripts/benchmark.py --calls 10 --location "België (Gent), glasvezel, geen VPN"
```

| Demo | n | mediaan (ms) | p95 (ms) | opmerking |
|---|---|---|---|---|
| 1 · smart if (3 vragen, 1 call) | | | | |
| 2 · confidence gate (2 vragen per ticket) | | | | |
| 3 · agent gate (3 Noul-vragen per tool call, via `TypeSafeClassifier`) | | | | |

Context om te vermelden: de service draait aan de US West Coast; RTT vanuit België naar
Californië is doorgaans ~140–160 ms (meet het zelf met `ping`/`curl -w` naar
`api.typesafe.ai`), dus de vloer vanuit de EU ligt boven de vendor-vloer van 70 ms.

## Gebruikte versies (exact gepind in `pyproject.toml`)

| Package | Versie | Opmerking |
|---|---|---|
| typesafe-sdk | 0.7.0 | released 2026-09-18 (PyPI); eerdere: 0.0.1a0 (09-09), 0.5.7 (09-11), 0.6.0 (09-15) |
| langchain-typesafe[experimental] | 0.0.1a3 | released 2026-09-20; a1 en a2 op 2026-09-17 |
| langchain | 1.4.2 | `create_agent`, `AgentMiddleware.wrap_tool_call` |
| langchain-core | 1.6.3 | (transitief; langchain-typesafe eist ≥ 1.6.2) |
| langgraph | 1.2.11 | (transitief) |
| langchain-openai | 1.6.2 | OpenAI en Azure OpenAI |
| langchain-anthropic | 1.7.2 | |
| marimo | 0.24.2 | slides-layout, `export html`, `export pdf --as=slides` |
| rich | 15.0.0 | |
| python-dotenv | 1.2.3 | |
| nbformat / nbconvert / playwright | 5.10.4 / 7.16.6 / 1.58.0 | alleen voor de PDF-export (`export`-group) |
| Python | 3.12 | `.python-version` |

## Valkuilen en API-eigenaardigheden

**typesafe-sdk**
- `TypeSafeClient.system_one(state=..., questions=...)`; antwoorden via `response.choices[...]`, `.scores[...]`, `.nouls[...]` (dicts per type) of `response.answers`.
- `Score.criteria` is een geordende lijst: **index = score**. `ScoreAnswer.score` is het kansgewogen gemiddelde (bv. 1.77), niet een niveau; het niveau in de demo's is de argmax van `probabilities` (`ScoreView.level`). `legend`/`probabilities` hebben integer-keys in de SDK, string-keys op de wire.
- `Noul` heeft geen confidence; `NoulAnswer.noul` is P(ja). `NoulCriteria(true=..., false=...)` is optioneel.
- Choice-criteria mogen `None` als beschrijving hebben (label alleen).
- Default model is de alias `jev-latest` (env `TYPESAFE_DEFAULT_MODEL`); `response.model` kan een concrete naam zijn.
- Default timeout 10 s, `RetryPolicy(max_retries=2)` met backoff: een dode verbinding geeft dus pas na enkele seconden een fout. Retries zijn ook op 429/5xx.
- `response.usage.output_tokens`: output-tokens zijn volgens de schema-docs gratis.
- `TypeSafeAPIConnectionError` erft van `ConnectionError`; auth-fout is `TypeSafeAuthenticationError` (401).
- Testen zonder key: `TypeSafeClient(api_key="x", transport=httpx2.MockTransport(...))` (zie `jevdemo/testing.py`). Let op: het SDK gebruikt **`httpx2`**, niet `httpx`.

**langchain-typesafe 0.0.1a3**
- `TypeSafeClassifier.invoke({"state": ..., "questions": {...}})` met `Choice/Noul/Score` uit `langchain_typesafe` (eigen pydantic-types, niet die van typesafe-sdk). `Choice.criteria` moet ≥ 1 item hebben, `Score.criteria` ≥ 2.
- LangChain-`BaseMessage`s mogen in de state staan (worden naar role/content-JSON omgezet); handig voor `recent_messages` in de gate.
- De klasse is `@beta`: import geeft `LangChainBetaWarning`; in `agent_gate.py` gedempt zodat hij niet op het scherm komt.
- `AutoModeMiddleware` stelt **één** Noul ("is_risky") met een vaste drempel 0.5 en alleen voor expliciet opgegeven tools. De opdracht wil drie aparte vragen met eigen beleid, vandaar de custom `JevToolGate` (zelfde mechaniek: `wrap_tool_call`, error-`ToolMessage` bij blokkering, fail-closed bij een API-fout).
- `ModelRouterMiddleware` bestaat ook (Choice kiest een model); wordt alleen genoemd op slide 8.
- Default timeout van de classifier is 30 s (SDK: 10 s).

**LangChain 1.4 / langgraph**
- `create_agent(model, tools=..., system_prompt=..., middleware=[...])`; `ToolCallRequest` heeft `.tool_call` (dict met `id/name/args`), `.tool` (BaseTool), `.state`, `.runtime`.
- Middleware-`wrap_tool_call` moet een `ToolMessage` (of `Command`) teruggeven; `status="error"` laat het LLM weten dat de call mislukte.
- Anthropic-modellen geven `content` als lijst van blokken; `_text()` in `agent_gate.py` vangt dat op.
- Azure: `init_chat_model(deployment, model_provider="azure_openai", azure_deployment=..., azure_endpoint=..., api_version=..., api_key=...)`.
- Microsoft Foundry (nieuwe `…services.ai.azure.com/openai/v1`-endpoint) is OpenAI-compatibel: `LLM_PROVIDER=openai` + `OPENAI_BASE_URL`; niet het `azure_openai`-pad (dat verwacht een api-version).

**marimo 0.24.2**
- Slides-layout = `marimo.App(layout_file="layouts/talk.slides.json")` met `{"type":"slides","data":{"cells":[{"type": "slide"|"sub-slide"|"fragment"|"skip", "speakerNotes": "...", "showCode": bool}, ...], "deck": {"transition": ..., "verticalAlign": ...}}}`; één entry per notebook-cel, **op volgorde**. `scripts/make_slides_layout.py` genereert dit uit de celnamen (`setup_*` → skip, `frag_*` → fragment). Formaat afgeleid uit de frontend-source van het package (docs waren onbereikbaar); controleer in `marimo edit` of de layout-dropdown "Slides" hem correct inleest.
- Een UI-element (slider) moet in een andere cel gedefinieerd worden dan waar `.value` gelezen wordt; daarom staat de tabel van demo 2 in een fragment-cel.
- Cellen die output geven worden slides; import/helper-cellen staan op `skip`.
- `mo.cli_args()` leest `-- --offline`; de schakelaar start dan uit.
- Eigen CSS: `css_file="talk.css"` én inline `<style>` in de titelslide (de export-PDF logt "CSS file talk.css does not exist" omdat hij vanuit een tijdelijke kopie rendert; dankzij de inline style is dat onschuldig). marimo's `.prose`/`.codehilite` zetten hun eigen font-size op codeblokken; je moet ze met `!important` en hogere specificiteit overschrijven (zie `talk.css`).
- `marimo export pdf --as=slides` vereist nbconvert + playwright; `--raster-server=live` geeft betere aspect-ratio. Als playwright een andere Chromium-build wil dan geïnstalleerd: `uv run playwright install chromium`.
- `marimo run` herlaadt het notebook niet bij wijzigingen (wel `--watch`); jevdemo-modules worden per sessie opnieuw geïmporteerd.

## Afwijkingen van de opdracht (en wat jij nog moet doen)

1. **Docs niet gelezen, wel de source.** `docs.typesafe.ai`, `docs.langchain.com/.../typesafe` en `docs.marimo.io` waren geblokkeerd. Alle API-gebruik is gebaseerd op de geïnstalleerde source van `typesafe-sdk 0.7.0` (incl. de gegenereerde OpenAPI-schema's), `langchain-typesafe 0.0.1a3`, `langchain 1.4.2`, `marimo 0.24.2`, de PyPI-README's en TypeSafe's agent-skill (`github.com/typesafe-ai/skills`, die zelf zegt: bij ontbrekende docs de SDK-types gebruiken en dat vermelden). **Te doen:** loop `https://docs.typesafe.ai/llms.txt` (primitives, confidence, api, sdk/python) en de LangChain-providerpagina na op afwijkingen, vooral rond confidence-semantiek en aanbevolen drempels.
2. **Geen echte API-calls gedaan, dus geen echte recordings en geen metingen.** Er was geen key en `api.typesafe.ai` was onbereikbaar. `recordings/*.json` zijn synthetische placeholders (`scripts/make_placeholder_recordings.py`), overal gemarkeerd. **Te doen:** de vier `--record`/benchmark-commando's uit de README draaien, daarna `scripts/preflight.py` (alles moet groen zijn) en de tabel hierboven invullen. Herexporteer daarna `exports/`.
3. **Demo 3 gebruikt een custom middleware**, niet `AutoModeMiddleware` (één gecombineerde vraag past niet bij "aparte Noul-vragen"). Toegestaan door de opdracht.
4. **Demo 2 heeft 11 tickets** i.p.v. ~10 (drie bewust ambigu).
5. **Slide 5 toont 14 + 5 regels code** (QUESTIONS en URGENCY_LEVELS, uit `jevdemo/`), iets meer dan "max ~15" in totaal, zodat alle drie de primitives zichtbaar zijn. Andere fragmenten zijn ≤ 15 regels.
6. **Demo 3 offline** speelt de volledige opgenomen trace af (ook het LLM-deel): LLM-output is niet deterministisch, dus "alleen de Jev-antwoorden" replayen zou geen zin hebben.
7. **Tickets en prompts zijn in het Engels.** Waarschijnlijk de veiligste keuze voor het model; test één Nederlands ticket voor de talk als je dat wil tonen (staat niet in de demo's).
8. **PDF-export** in deze omgeving vereiste een symlink naar de voorgeïnstalleerde Chromium-build; op je eigen machine volstaat `uv run playwright install chromium`.
9. **Slide 10** bevat de RTT-schatting "~140 ms Amsterdam–Californië" als vuistregel; vervang door je eigen `ping`-meting.
10. Vendor-datums (Jev-lancering 15 sept 2026, langchain-typesafe eerste release 17 sept) komen uit de opdracht; PyPI bevestigt 17 sept voor `langchain-typesafe 0.0.1a1/a2` en 15 sept voor `typesafe-sdk 0.6.0`.
