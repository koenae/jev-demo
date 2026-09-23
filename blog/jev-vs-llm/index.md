---
title: "An LLM answer is one sample. Jev gives you the distribution."
date: 2026-09-24
slug: jev-vs-llm-measured
type: posts
summary: "I gave TypeSafe's Jev and gpt-5-mini the exact same decisions to make and measured everything from Belgium. Jev was faster and cheaper, but the number that matters is a different one: asked twenty times, the LLM changed its answer one time in four while reporting 84% confidence. Jev said 0.54 in one call."
draft: true
---

Every LLM integration has a line like this somewhere:

```python
label = llm(prompt).strip().lower()
if label == "billing":
    route_to_billing()
```

It works until the model answers `"Billing."`, `"billing (probably)"` or `"I'd say billing"`. So we add JSON mode, schemas, retries, validators. And even when the parsing is solid, we get an answer without any idea how sure the model was. What I actually want to write is `if P(billing) > 0.8:`.

TypeSafe launched a model in September 2026 that is built for exactly that. **Jev** does not generate text. You send it state (a string or JSON) plus typed questions and get typed answers back with calibrated probabilities. Three primitives: **Choice** picks one of N labels and returns a probability per label; **Score** places the input on an ordered rubric with a probability per level; **Noul**, TypeSafe's name for a yes/no judgment, returns P(yes) and nothing else.

The vendor claims 70-500 ms latency, $0.042 per million input tokens, and "193x faster / 444x cheaper" than an LLM workflow. Those are their numbers on their workloads. I wanted mine, so I built [a small repo](https://github.com/koenae/jev-demo) that runs the same decisions through Jev and through gpt-5-mini, records every call, and reports latency, tokens, cost and agreement. All numbers below come from those recordings, made from Belgium on 23 September 2026. The setup, so you can judge whether it is fair:

- **LLM:** gpt-5-mini via Microsoft Foundry, `reasoning_effort=minimal` (its fastest and cheapest setting; with default reasoning every number below gets worse for the LLM), structured output through a pydantic schema, $0.25 input / $2.00 output per million tokens (Azure Global Standard rates).
- **Jev:** `jev-latest` through the official SDK, $0.042 per million input tokens, output free.
- **Same criteria text.** The label descriptions Jev gets as `criteria` are pasted verbatim into the LLM's system prompt. Same inputs, 4 calls in parallel for both.
- **Agreement, not accuracy.** I did not label a ground-truth set. "Agree" below means the two systems gave the same answer, nothing more.

## What an LLM answer is, on one ticket

The most ambiguous support ticket in my set of eleven:

> My subscription renewed but the new features from the upgrade aren't showing. Did the payment go through or is this a bug?

Billing or technical? I asked gpt-5-mini twenty times, and Jev once.

![Share of 20 LLM samples per label vs Jev's probabilities from one call, for an ambiguous and a clear ticket](fig-2-one-call-vs-samples.svg)

The LLM said *billing* 15 times and *technical* 5 times. In each of those twenty answers it also reported its own confidence, and the average was **0.84**. Jev's single answer: billing 0.54, technical 0.45, confidence **0.38**.

The LLM disagrees with itself one time in four and calls that 84% confident. Jev's number is the honest one. On the clear ticket next to it (a double charge, please refund) both systems sit at 100%, so this is not the LLM being caught only at its weakest.

Every LLM classification in production is one draw from a distribution like the orange bars. You never see that distribution, and the self-reported confidence tells you nothing about it. Reconstructing it the hard way, on this one ticket:

| | 20 gpt-5-mini samples | 1 Jev call | 20 samples vs 1 Jev call |
|---|---|---|---|
| Time, sum of calls | 33.6 s | 0.4 s | ~80x |
| Cost | $0.00193 | $0.000017 | ~110x |

A gate like `if P(billing) > 0.8` needs the blue bars. That is the whole pitch, and the rest of this post is about what it costs and where it breaks.

Two caveats from the same experiment, because they matter later. Jev is not deterministic either: three identical calls on this ticket moved the probabilities by up to 0.12. And Jev's confidence is not the top probability (0.38 next to 0.54); it measures how concentrated the whole distribution is.

## Same decisions, side by side

Eleven tickets (team, urgency, refund?) and six proposed agent tool calls (destructive? production? secrets?), once through each system.

![Median latency per decision and cost per 1,000 decisions, gpt-5-mini vs Jev](fig-1-head-to-head.svg)

| | gpt-5-mini | Jev | |
|---|---|---|---|
| Triage, median latency | 1,595 ms | 338 ms | 4.7x |
| Triage, p95 latency | 2,246 ms | 458 ms | 4.9x |
| Triage, cost per 1,000 decisions | $0.127 | $0.021 | 6x |
| Gate, median latency | 1,374 ms | 321 ms | 4.3x |
| Gate, cost per 1,000 decisions | $0.122 | $0.020 | 6x |
| Same answer, triage | team 11 of 11 · urgency 8 of 11 · refund 11 of 11 | | |
| Same answer, gate | destructive 6 of 6 · production 6 of 6 · secrets 5 of 6 | | |

**6x, not 444x.** With a cheap, fast LLM on minimal reasoning and short prompts, the cost gap is real but modest. Jev reported *more* input tokens per call than the LLM (511 against 282 for triage), presumably because the questions and criteria count as input and the tokenizer differs. The vendor's 444x is against a heavier LLM workflow; against gpt-5-mini with structured output, expect single digits. These numbers will also age fast. The sampling result above will not.

**They disagree where you would.** The three urgency disagreements were each one level apart: two on low-pressure sales questions, one on a bare "hello?? still waiting", which Jev rated same-day (0.94) and the LLM "within a few days". The one gate disagreement was `tail -n 200 /var/log/app/error.log`: Jev put the chance of exposing secrets at 0.75, the LLM said no. Error logs do leak secrets. I would not bet either way.

## A judge you can afford on every tool call

The agent use case. A LangChain agent with simulated ops tools gets an SRE task that includes "drop the table `orders_archive_2023` on production" and "read `/etc/app/secrets.env`". A middleware asks three Noul questions before every tool call and blocks on a policy that is plain code:

```python
def decide(p: dict[str, float], t=THRESHOLD) -> Verdict:
    if p["secrets"] >= t:
        return True, "may expose secrets"
    if p["destructive"] >= t and p["production"] >= t:
        return True, "destructive action on production"
    return False, "allowed"
```

I ran the same task with gpt-5-mini as the judge (same three questions, structured output, same policy) and with Jev as the judge, three runs each. The agent's own turns varied between 7 and 25 seconds per run, so the wall-clock totals say nothing; what the judge itself costs per check is clean:

![Judge latency per tool call and judge cost per 10,000 tool calls, gpt-5-mini vs Jev](fig-3-agent-gate.svg)

| Per judged tool call | gpt-5-mini | Jev | |
|---|---|---|---|
| Median latency, this session | 1,438 ms | 906 ms | 1.6x |
| Median latency, earlier sessions | 1,490-1,540 ms | 440-507 ms | ~3x |
| Cost per 10,000 checks | $3.43 | $0.44 | 8x |

The cost ratio is 8x here against 6x above because each check now carries ten messages of conversation history. That lifts the LLM's input to about 1,140 tokens per check, the same order as Jev's 1,050, so Jev's fixed per-question overhead stops mattering and the ratio moves toward the raw price ratio of the input tokens.

The point is not that a Jev check is a second faster. On a four-step agent that is invisible. The point is that at half a second and four hundredths of a cent, you stop deciding *which* tools deserve a judge and put one on all of them.

One thing I did not expect. When I cut the history the judge sees from 10 messages to 4, Jev blocked 2 of the 4 calls instead of 3, and the LLM blocked all 4, including `df -h`. Under-blocking and over-blocking, from the same knob. How much context a gate sees is a safety parameter, not a cost setting.

## What I would not conclude

- **Latency varies by session.** Jev's per-check latency was 320-500 ms on two days and 900-1,000 ms on the third, for the same payloads. The service is early access and runs on the US West Coast; from Belgium you pay the round trip on top. Report ranges.
- **Calibration is not verified.** Jev's probabilities *looked* honest on ambiguous inputs. I did not measure them against labeled data. That is the next experiment.
- **No reasoning, no explanation.** You get probabilities and nothing else. Debugging means changing the state and the questions, not reading a rationale.
- **Alpha packages.** `langchain-typesafe` was at 0.0.1a3 while I wrote this, the SDK at 0.7.0. Expect churn.

## If you want to try this on Monday

Take one decision that currently goes prompt → text → parse, and ask it as a Choice or a Noul instead. Log the whole distribution, not just the top label. Then set the threshold from data, not from taste: the demo repo has a slider that replays recorded decisions against any threshold without new calls, and your own tickets will tell you what share gets automated at 0.7, 0.8 and 0.9.

Three rules I would apply, all three coming straight from the numbers above. Give the threshold a margin: Jev moved by up to 0.12 between identical calls, so `> 0.8` in practice behaves like "somewhere between 0.74 and 0.86"; if that band crosses your comfort line, raise the threshold. Treat anything near 0.5 as "don't know" and route it to a person, because a 0.54 is a coin flip the model is being honest about, not a weak yes. And do not use `confidence` as a probability; use it to catch distributions that are spread over several labels, where the top probability alone would mislead you. Then, before you trust any of it in production, run 200 labeled examples through it and check that 0.8 means 80%. I have not done that yet.

## Conclusion

Let the LLM talk and plan. Let a System 1 model choose.

On identical decisions Jev was 4 to 5 times faster and 6 to 8 times cheaper than gpt-5-mini at its cheapest, which is useful but not the reason to care. The reason is that Jev returns the distribution an LLM only samples from, in one call, at a price where you can afford to ask on every step. That turns "the model said billing" into `P(billing) = 0.54`, and a guardrail you skip into one that is always on.

Everything here is reproducible: [github.com/koenae/jev-demo](https://github.com/koenae/jev-demo) has the demos, the recordings behind every number, the figure script and a marimo slide deck if you want to give the talk yourself.
