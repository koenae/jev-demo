# Jev next to gpt-5-mini

Code and raw results behind the post
[What I measured when I put Jev next to gpt-5-mini](https://koenaerts.com/posts/jev-vs-llm-measured/).

[Jev](https://typesafe.ai) is a model from TypeSafe that answers typed questions (pick one
option, place on a scale, yes/no) with a probability per option instead of text. This repo
sends the same decisions to Jev and to gpt-5-mini, records every call, and compares speed,
cost and agreement. Nothing here executes real commands: the agent tools are simulated.

```
jevdemo/      the demo logic, plain functions that return data
demos/        one CLI per demo, each with --record and --offline
recordings/   the recorded API responses the post and figures are based on
blog/         the post, its figures and the script that draws them
scripts/      self-test, price lookup, figure scripts
```

## Setup

1. Install [uv](https://docs.astral.sh/uv/) and sync (Python 3.12 is fetched automatically):
   ```bash
   uv sync --all-groups
   ```
2. Create `.env` from the example and fill in the keys:
   ```bash
   cp .env.example .env
   ```
   `TYPESAFE_API_KEY` is needed for every demo. Demos 3, 4 and 5 also need an LLM:
   set `LLM_PROVIDER` (`openai`, `anthropic` or `azure_openai`), `LLM_MODEL` and the matching
   key. For a model on Microsoft Foundry use `LLM_PROVIDER=openai`, the API key from
   "Call gpt-5-mini in code" and `OPENAI_BASE_URL=https://<project>.services.ai.azure.com/openai/v1`.
3. For the cost columns, set `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK`
   (USD per million tokens). For Azure OpenAI or Foundry this looks them up:
   ```bash
   uv run python scripts/llm_prices.py --model gpt-5-mini
   ```

## The demos

| Demo | What it does | Command |
|---|---|---|
| 1 Smart if | one ticket, one Jev call: a Choice, a Score and a Noul, with the distribution and confidence | `uv run python demos/demo1_smart_if.py` |
| 2 Confidence gate | 11 tickets; handle automatically above a threshold, escalate below it | `uv run python demos/demo2_confidence_gate.py [--threshold 0.75]` |
| 3 Agent gate | a LangChain agent with simulated ops tools; a judge (Jev or the LLM) checks every tool call: destructive? production? secrets? | `uv run python demos/demo3_agent_gate.py [--gate none\|llm\|jev]` |
| 3 Gate comparison | the same agent task with no gate, the LLM as judge and Jev as judge; latency and cost per check | `uv run python demos/demo3_agent_gate.py --compare --runs 3` |
| 4 Head-to-head | 11 tickets and 6 tool calls through both systems with the same criteria text; median/p95 latency, tokens, cost per 1,000 decisions, agreement | `uv run python demos/demo4_head_to_head.py` |
| 5 One call vs N samples | ask the LLM the same question 20 times and Jev once; one ambiguous ticket and one clear one | `uv run python demos/demo5_one_call_vs_samples.py [--samples 20]` |

## Recording and replaying

Every demo takes the same two flags:

- `--record`: call the APIs and save the responses to `recordings/<demo>.json`
- `--offline`: replay the saved responses, no network or keys needed

The recordings in this repo are the real calls the post is based on. The single-gate
variants of demo 3 (`--gate llm`, `--gate none`) have no recording, so they need `--record`
before `--offline` works.

## Other scripts

- `scripts/selftest.py`: runs every demo against a fake transport, no keys or network
- `scripts/llm_prices.py`: looks up Azure OpenAI prices through the public Retail Prices API
- `scripts/blog_figures.py`: draws the three figures in `blog/jev-vs-llm/` from the recordings

See `blog/README.md` for how the post and figures go into the Hugo site.
