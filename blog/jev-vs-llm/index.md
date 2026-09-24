---
title: "What I measured when I put Jev next to gpt-5-mini"
date: 2026-09-24
slug: jev-vs-llm-measured
type: posts
summary: "I gave TypeSafe's Jev and gpt-5-mini the same decisions to make and measured everything from Belgium. Jev was faster and cheaper, but the interesting number is a different one: asked twenty times, the LLM changed its answer one time in four while reporting 84% confidence. Jev said 0.54 in one call."
draft: true
---

## The if-statement problem

Somewhere in every LLM integration I have built, there is a line like this:

```python
label = llm(prompt).strip().lower()
if label == "billing":
    route_to_billing()
```

It works until the model answers `"Billing."`, or `"billing (probably)"`, or `"I'd say billing"`. Then you add JSON mode, a schema, retries, a validator. And when the parsing finally holds, you still have an answer without any idea how sure the model was about it. What I actually wanted to write all along is `if P(billing) > 0.8:`.

In September 2026 TypeSafe launched a model for exactly this. Jev does not generate text. You send it state (a string or JSON) and typed questions, and you get typed answers back with probabilities. There are three question types. Choice picks one of N labels and returns a probability per label. Score places the input on an ordered rubric, with a probability per level. Noul, which is TypeSafe's name for a yes/no judgment, returns P(yes) and nothing else.

The vendor claims 70-500 ms latency, $0.042 per million input tokens, and "193x faster / 444x cheaper" than an LLM workflow. Those are their numbers on their workloads. I wanted to see mine, so I built [a small repo](https://github.com/koenae/jev-demo) that runs the same decisions through Jev and through gpt-5-mini, records every call, and reports latency, tokens, cost and how often the two agree. Everything below comes from those recordings, made from Belgium on 23 September 2026.

## The setup

I tried to make this fair, and I want to be clear about where it is not.

- LLM: gpt-5-mini via Microsoft Foundry with `reasoning_effort=minimal`. That is its fastest and cheapest setting. With default reasoning every LLM number below gets worse. Structured output through a pydantic schema. Priced at $0.25 input and $2.00 output per million tokens (Azure Global Standard).
- Jev: `jev-latest` through the official Python SDK. $0.042 per million input tokens, output free.
- Same criteria text. The label descriptions Jev gets as `criteria` are pasted verbatim into the LLM's system prompt.
- Both run 4 calls in parallel.
- Agreement, not accuracy. I did not label a ground-truth set. "Agree" below means the two systems gave the same answer. It says nothing about who was right.

Finding the gpt-5-mini prices took longer than running the benchmark. The Foundry portal links to a pricing page that did not list the model in a form I could find, so I ended up querying the Azure Retail Prices API directly. The repo has a script for that.

## Twenty answers to one question

This is the part that changed how I look at LLM classifiers, so it goes first.

The most ambiguous ticket in my set of eleven:

> My subscription renewed but the new features from the upgrade aren't showing. Did the payment go through or is this a bug?

Billing or technical. I asked gpt-5-mini twenty times. I asked Jev once (three times actually, to see if it moved).

![Two bar charts. Left, the ambiguous ticket T-109: gpt-5-mini answered billing in 75% and technical in 25% of 20 samples, Jev gave billing 0.54 and technical 0.45 in one call. Right, the clear ticket T-102: both give billing 1.00.](fig-2-one-call-vs-samples.svg)

The LLM said billing 15 times and technical 5 times. Each answer also came with a confidence, because I put a `confidence` field in the output schema and asked the model to fill it in. That number is not measured by anything; it is the model writing down a figure about its own answer. The average over the twenty samples was 0.84. Jev's single answer was billing 0.54, technical 0.45, and the confidence field it returns, the 0.38 in the figure, is computed from that distribution rather than reported by the model.

So the LLM disagrees with itself one time in four and calls that 84% confident. Jev's number is the one I would want in my code. On the clear ticket next to it (a double charge, please refund) both sit at 100%, so this is not the LLM being caught only at its weakest.

The way I read this: every LLM classification is one draw from a distribution you never see, and the confidence it reports is not about that distribution. Reconstructing it by sampling costs, on this one ticket:

| | 20 gpt-5-mini samples | 1 Jev call | 20 samples vs 1 Jev call |
|---|---|---|---|
| Time, sum of calls | 33.6 s | 0.4 s | ~80x |
| Cost | $0.00193 | $0.000017 | ~110x |

Two things from the same experiment that I did not expect. Jev is not deterministic either: three identical calls on this ticket moved the probabilities by up to 0.12. And Jev's confidence is not the top probability (0.38 next to 0.54). It measures how concentrated the whole distribution is. Both matter when you pick a threshold, I come back to that at the end.

## The same decisions side by side

Eleven tickets (team, urgency, refund?) and six proposed agent tool calls (destructive? production? secrets?), once through each system.

![Two bar charts comparing gpt-5-mini and Jev on ticket triage and the tool-call gate: median latency per decision (1,595 and 1,374 ms versus 338 and 321 ms) and cost per 1,000 decisions ($0.127 and $0.122 versus $0.021 and $0.020).](fig-1-head-to-head.svg)

| | gpt-5-mini | Jev | |
|---|---|---|---|
| Triage, median latency | 1,595 ms | 338 ms | 4.7x |
| Triage, p95 latency | 2,246 ms | 458 ms | 4.9x |
| Triage, cost per 1,000 decisions | $0.127 | $0.021 | 6x |
| Gate, median latency | 1,374 ms | 321 ms | 4.3x |
| Gate, cost per 1,000 decisions | $0.122 | $0.020 | 6x |
| Same answer, triage | team 11 of 11, urgency 8 of 11, refund 11 of 11 | | |
| Same answer, gate | destructive 6 of 6, production 6 of 6, secrets 5 of 6 | | |

6x cheaper, not 444x. With a cheap LLM on minimal reasoning and short prompts the gap is real but modest. Part of the reason is that Jev reported more input tokens per call than the LLM (511 against 282 for triage). I assume the questions and criteria count as input and the tokenizer is different. The vendor's 444x is against a heavier LLM workflow. Against gpt-5-mini with structured output I would expect single digits, and these numbers will be stale in a few months anyway. The sampling result above will not.

The disagreements are where I would have hesitated too. The three urgency disagreements were each one level apart: two on low-pressure sales questions, and one on a bare "hello?? still waiting", which Jev rated same-day (0.94) and the LLM "within a few days". The one gate disagreement was `tail -n 200 /var/log/app/error.log`. Jev put the chance of exposing secrets at 0.75, the LLM said no. Error logs do leak secrets, so I would not bet either way.

## A judge in front of every tool call

The agent case. A LangChain agent with simulated ops tools gets an SRE task that includes "drop the table `orders_archive_2023` on production" and "read `/etc/app/secrets.env`". A middleware asks three Noul questions before every tool call and blocks on a policy that is plain code:

```python
def decide(p: dict[str, float], t=THRESHOLD) -> Verdict:
    if p["secrets"] >= t:
        return True, "may expose secrets"
    if p["destructive"] >= t and p["production"] >= t:
        return True, "destructive action on production"
    return False, "allowed"
```

I ran the same task with gpt-5-mini as the judge (same three questions, structured output, same policy) and with Jev as the judge, three runs each.

The first version of this section compared the total run times, and had a statistic about what share of the run was spent judging. A reviewer pointed out that the agent's own turns varied between 7 and 25 seconds per run, so that share said more about how fast the agent happened to be that time than about the judge. He was right, and I dropped it. What is clean is what one check costs:

![Two bar charts for the agent judge: median latency per tool call, 1,438 ms for gpt-5-mini versus 906 ms for Jev, and cost per 10,000 tool calls, $3.43 versus $0.44.](fig-3-agent-gate.svg)

| Per judged tool call | gpt-5-mini | Jev | |
|---|---|---|---|
| Median latency | 1,438 ms (1,440-1,540 across sessions) | 906 ms (440-1,000 across sessions) | 1.6x this session, ~3x on the other two |
| Cost per 10,000 checks | $3.43 | $0.44 | 8x |

The cost ratio is 8x here and 6x above. Each check now carries ten messages of conversation history, which lifts the LLM's input to about 1,140 tokens per check, the same order as Jev's 1,050. Jev's fixed overhead per question stops mattering and the ratio moves toward the raw price ratio of the input tokens.

The first version of the cost column showed $0.00 for Jev, because I had forgotten to count the tokens of the Jev middleware. Worth mentioning, since "free" would have been a nice number to believe.

On a four-step agent, a check that is half a second faster is invisible in the total. What changes is the decision of where to put a judge at all. At half a second and four hundredths of a cent per check, I would put one on every tool, instead of picking the dangerous ones.

Something I did not expect: when I cut the history the judge sees from 10 messages to 4, Jev blocked 2 of the 4 calls instead of 3, and the LLM blocked all 4, including `df -h`. Under-blocking and over-blocking from the same knob. How much context a gate gets is a safety setting, not a cost setting. I left it at 10.

## What this does not show

- Latency varies by session. Jev's per-check latency was 320-500 ms on two days and 900-1,000 ms on the third, for the same payloads. I first suspected my own prompt, but cutting the history did not change it. The service is early access and runs on the US West Coast, and from Belgium the round trip comes on top. I would report ranges rather than a number.
- Calibration is not verified. Jev's probabilities looked honest on ambiguous inputs. I did not check them against labeled data. That is the next experiment.
- No reasoning, no explanation. You get probabilities and nothing else. Debugging means changing the state and the questions, not reading a rationale.
- Alpha packages. `langchain-typesafe` was at 0.0.1a3 when I wrote this, the SDK at 0.7.0. The docs site was unreachable from the sandbox I built the repo in, so the API surface came from the installed source. Expect things to move.

## How I would use it

I would start with one decision that currently goes prompt, text, parse, and ask it as a Choice or a Noul instead. And log the whole distribution, not just the top label, because that is the thing you cannot get back later.

Then the threshold, from data instead of taste. The repo has a slider that replays recorded decisions against any threshold without new calls; on my eleven tickets, a threshold of 0.75 automates 9 and escalates 2, and one of the two escalated ones is the ticket from the sampling section. Three rules I would apply, all three coming from the numbers above. Give the threshold a margin, since Jev moved by up to 0.12 between identical calls, so `> 0.8` behaves more like "somewhere between 0.74 and 0.86". Treat anything near 0.5 as "don't know" and route it to a person; a 0.54 is a coin flip the model is being honest about, not a weak yes. And do not use `confidence` as a probability, but as a flag for distributions spread over several labels, where the top probability alone would mislead.

Before trusting any of it in production I would run a couple of hundred labeled examples through it and check that 0.8 means 80%. I have not done that yet.

## Conclusion

On identical decisions Jev was 4 to 5 times faster and 6 to 8 times cheaper than gpt-5-mini at its cheapest setting. Useful, and probably temporary.

The part I expect to keep is the other one. An LLM classifier gives me one sample and a confidence number that is not about the sampling. Jev gives me the distribution in one call, at a price where I can ask on every step. That is what makes `if P(billing) > 0.8` a line I can actually write, and it makes a guardrail I used to skip into one that stays on.

The repo with the demos, the recordings behind every number, the figure script and a marimo slide deck is at [github.com/koenae/jev-demo](https://github.com/koenae/jev-demo).
