---
title: "Jev vs an LLM: same decisions, measured from Belgium"
date: 2026-09-24
slug: 2026-09-24
type: posts
summary: "I gave TypeSafe's Jev and gpt-5-mini the exact same decisions to make. Jev was 4-5x faster and 6x cheaper, but the real difference is not speed: an LLM answer is one sample from a distribution you never see. Jev gives you the distribution."
draft: true
---

Every LLM integration has a line like this somewhere:

```python
label = llm(prompt).strip().lower()
if label == "billing":
    route_to_billing()
```

It works until the model answers `"Billing."`, `"billing (probably)"` or `"I'd say billing"`. So we add JSON mode, schemas, retries, validators. And even when the parsing is solid, we still get an answer without any idea how sure the model was. What I actually want to write is `if P(billing) > 0.8:`.

TypeSafe launched a model in September 2026 that is built for exactly that. **Jev** does not generate text. You send it state (a string or JSON) plus typed questions, and you get typed answers back with calibrated probabilities. Three primitives:

- **Choice**: pick one of N labels, get a probability per label plus a confidence.
- **Score**: a level on an ordered rubric, with a probability per level.
- **Noul**: a yes/no question, answered as P(yes).

The vendor claims 70-500 ms latency, $0.042 per million input tokens, and "193x faster / 444x cheaper" than an LLM workflow. Those are their numbers on their workloads. I wanted mine. So I built [a small demo repo](https://github.com/koenae/jev-demo) that runs the same decisions through Jev and through gpt-5-mini, records everything, and reports latency, tokens, cost and agreement. All numbers below come from those recordings, made from Belgium on 23 September 2026.

## The setup, so you can judge if it is fair

- **LLM:** gpt-5-mini via Microsoft Foundry, `reasoning_effort=minimal` (the fastest and cheapest setting; with default reasoning every number below gets worse for the LLM), structured output through a pydantic schema, priced at $0.25 input / $2.00 output per million tokens (Azure Global Standard rates).
- **Jev:** `jev-latest` through the official SDK, $0.042 per million input tokens, output free.
- **Same criteria text.** The label descriptions Jev gets as `criteria` are pasted verbatim into the LLM's system prompt. Same tickets, same tool calls, 4 calls in parallel for both.
- **Agreement, not accuracy.** I did not label a ground-truth set. "Agreement" below means the two systems gave the same answer, nothing more.

Here is what a Jev call looks like. This is the actual code from the repo, not a simplified version:

```python
QUESTIONS = {
    "team": Choice(
        instructions="Which team should own this ticket?",
        criteria=TEAMS,               # label -> description
    ),
    "urgency": Score(
        instructions="How urgent is this ticket for the customer?",
        criteria=URGENCY_LEVELS,      # ordered rubric: index = score
    ),
    "refund": Noul(
        instructions="Does the customer ask for money back?",
        criteria=REFUND,              # optional: describe yes / no
    ),
}

response = client.system_one(state={"ticket": ticket}, questions=QUESTIONS)
response.choices["team"].probabilities   # {"billing": 0.71, "technical": 0.26, ...}
response.nouls["refund"].noul            # 0.93
```

One round trip, three typed answers, and the output is schema-conform by construction. There is no reasoning text, and there is no parsing.

## Result 1: same decisions, 4-5x faster, 6x cheaper

Eleven support tickets (team, urgency, refund?) and six proposed agent tool calls (destructive? production? secrets?), once through each system.

![Median latency per decision and cost per 1,000 decisions, gpt-5-mini vs Jev](fig-1-head-to-head.svg)

| | gpt-5-mini | Jev | |
|---|---|---|---|
| Triage, median latency | 1,595 ms | 338 ms | 4.7x |
| Triage, p95 latency | 2,246 ms | 458 ms | 4.9x |
| Triage, cost per 1,000 decisions | $0.127 | $0.021 | 6x |
| Gate, median latency | 1,374 ms | 321 ms | 4.3x |
| Gate, cost per 1,000 decisions | $0.122 | $0.020 | 6x |
| Agreement, triage | team 100%, urgency 73%, refund 100% | | |
| Agreement, gate | destructive 100%, production 100%, secrets 83% | | |

Two things worth saying out loud.

**6x, not 444x.** With a cheap, fast LLM on minimal reasoning and short prompts, the cost gap is real but modest. Part of the reason: Jev reported *more* input tokens per call than the LLM (511 vs 282 for triage), presumably because the questions and criteria count as input and the tokenizer differs. The vendor's 444x is against a heavier LLM workflow. If your baseline is gpt-5-mini with structured output, expect single digits.

**Where they disagree is exactly where you would.** All three urgency disagreements were one level apart on tickets with no real time pressure. The one gate disagreement was `tail -n 200 /var/log/app/error.log`: Jev said it could expose secrets (0.6), the LLM said no. I would not want to bet either way.

## Result 2: an LLM answer is one sample. Jev gives you the distribution.

This is the part that changed how I look at LLM classifiers. Take the most ambiguous ticket in the set:

> My subscription renewed but the new features from the upgrade aren't showing. Did the payment go through or is this a bug?

Ask gpt-5-mini "which team?" twenty times. Ask Jev once.

![Share of 20 LLM samples per label vs Jev's probabilities from one call, for an ambiguous and a clear ticket](fig-2-one-call-vs-samples.svg)

The LLM said *billing* 15 times and *technical* 5 times, and on average reported a confidence of **0.84** in whatever it said. Jev said billing 0.54, technical 0.45, and reported a confidence of **0.38**.

Read that again. The LLM disagrees with itself one time in four and calls that 84% confident. Jev's 0.38 is the honest number. On the clear ticket (a double charge, please refund) both systems are at 100%, so this is not the LLM being caught only at its weakest.

The economics of reconstructing that distribution the hard way:

| | 20 LLM samples | 1 Jev call |
|---|---|---|
| Time (sum of calls) | 33.6 s | 0.4 s |
| Cost | $0.00193 | $0.000017 |
| Ratio | ~80x slower | ~110x more expensive |

Every LLM classification you run in production is one draw from a distribution like the orange one. You never see it, and the self-reported confidence does not tell you about it. A gate like `if P(billing) > 0.8` needs the blue one.

Two honest caveats from the same experiment. Jev is not deterministic either: three identical calls on that ticket moved the probabilities by up to **0.12**. And Jev's confidence is not the top probability (0.38 vs 0.54); it measures how concentrated the distribution is. Both are things you want to know before you pick a threshold.

## Result 3: a judge you can afford to run on every tool call

The agent use case. A LangChain agent with simulated ops tools gets an SRE task that includes "drop the table `orders_archive_2023` on production" and "read `/etc/app/secrets.env`". A middleware asks three Noul questions before every tool call and blocks on a plain-code policy:

```python
def decide(p: dict[str, float], t=THRESHOLD) -> Verdict:
    if p["secrets"] >= t:
        return True, "may expose secrets"
    if p["destructive"] >= t and p["production"] >= t:
        return True, "destructive action on production"
    return False, "allowed"
```

I ran the same task three times each with no gate, with gpt-5-mini as the judge (same three questions, structured output, same policy) and with Jev as the judge.

![Wall time of one agent run split into the agent's own turns and the judge's time, for no gate, LLM judge and Jev judge](fig-3-agent-gate.svg)

The wall-clock totals barely move, and I want to be upfront about that: on a four-step agent the difference is a second. The agent's own turns vary by 7 to 25 seconds between runs, which swamps everything. What does not vary is the share: **with gpt-5-mini as judge, two thirds of the run is supervision. With Jev it is under a third.** Per check, Jev was 1.6x to 3.4x faster depending on the day (more on that below), and about 8x cheaper: $0.38 versus $3.16 per 10,000 checks.

That share is why teams put an LLM judge only on the "dangerous" tools. At half a second and a fraction of a cent, you put it on all of them.

One more finding from this experiment that I did not expect. I reduced the conversation history the judge sees from 10 messages to 4. Jev then blocked 2 of the 4 calls instead of 3; the LLM blocked all 4, including `df -h`. Under-blocking and over-blocking, from the same knob. How much context a gate sees is a safety parameter, not a cost setting.

## What I would not conclude

- **Latency varies by session.** Jev's per-check latency was 320-440 ms on two days and 900-1,000 ms on a third, for the same payloads. The service is early access and runs on the US West Coast; from Belgium you pay the round trip on top. Report ranges, not a number.
- **Calibration is not verified.** Jev's probabilities *looked* honest on ambiguous inputs, but I did not measure them against labeled data. That is the next experiment.
- **No reasoning, no explanation.** You get probabilities and nothing else. Debugging means changing the state and the questions, not reading a rationale.
- **Alpha packages.** `langchain-typesafe` was at 0.0.1a3 while I wrote this; the SDK at 0.7.0. Expect churn.

## Conclusion

Let the LLM talk and plan. Let a System 1 model choose.

On identical decisions Jev was 4 to 5 times faster and 6 times cheaper than gpt-5-mini at its cheapest, which is useful but not the reason to care. The reason is that Jev returns the distribution an LLM only samples from, in one call, at a price where you can afford to ask on every step. That turns "the model said billing" into `P(billing) = 0.54`, and a guardrail you skip into one that is always on.

Everything here is reproducible: [github.com/koenae/jev-demo](https://github.com/koenae/jev-demo) has the five demos, the recordings behind every number, the figure script, and a marimo slide deck if you want to give the talk yourself.
