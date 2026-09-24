---
title: "What I measured when I put Jev next to gpt-5-mini"
date: 2026-09-24
slug: jev-vs-llm-measured
type: posts
summary: "I gave TypeSafe's Jev and gpt-5-mini the same decisions and measured speed, cost and agreement. Jev was faster and cheaper, but the more interesting result was how often the LLM changed its answer while saying it was sure."
draft: true
---

## Cool demos, but what does it do

I first saw Jev in a few demos online. One where an agent browses a lot faster than the usual screenshot-and-think loop. One where an assistant on a Mac fires off actions almost in real time, as if there was no model in between. That is not what LLM demos normally look like, so I wanted to know what was doing the work.

Jev is a model from TypeSafe, launched in September 2026 and still in early access. It does not generate text. You send it some state and a typed question, and you get probabilities back. That is what makes those demos fast: nothing to parse, nothing to wait for, just a number per option.

There are three question types:

1. **Choice** picks one of N labels, with a probability per label.
2. **Score** places the input on an ordered scale, with a probability per level.
3. **Noul** is a yes/no question. It returns P(yes).

TypeSafe puts numbers next to it: 70-500 ms latency and "193x faster / 444x cheaper" than an LLM workflow. Those are their numbers on their workloads. I got access, and I wanted my own. So I sent the same decisions to Jev and to gpt-5-mini and recorded every call. The code and the recordings are in [a small repo](https://github.com/koenae/jev-demo).

## The setup

- **LLM:** gpt-5-mini on Microsoft Foundry, with `reasoning_effort=minimal` (its fastest and cheapest setting) and structured output. $0.25 input and $2.00 output per million tokens.
- **Jev:** `jev-latest` through the Python SDK. $0.042 per million input tokens, output is free.
- Both get the same criteria text and run 4 calls in parallel.
- Everything was measured from Belgium on 23 September 2026.

I measured agreement, not accuracy. I had no labeled data, so "agree" only means both gave the same answer.

Finding the gpt-5-mini price took longer than running the benchmark. The Foundry portal did not show it in a way I could find, so I queried the Azure Retail Prices API directly. The repo has a script for that.

## Asking the same question twenty times

This is the result that surprised me most, so it goes first.

The task is support ticket triage: which team should handle a ticket, with billing, technical, sales and other as the options. Both systems get the same one-line description per team. I took the most ambiguous ticket in my set of eleven:

> My subscription renewed but the new features from the upgrade aren't showing. Did the payment go through or is this a bug?

This could be billing or technical. I asked gpt-5-mini the team question twenty times, and Jev once. Next to it, as a control, a ticket where there is nothing to doubt: "I was charged EUR 49 twice this month. Please refund one of them."

![Two bar charts. Left, the ambiguous ticket T-109: gpt-5-mini answered billing 15 times and technical 5 times out of 20 calls, Jev gave billing 0.54 and technical 0.45 in one call. Right, the clear ticket T-102: both give billing 1.00.](fig-2-one-call-vs-samples.svg)

- gpt-5-mini said **billing 15 times** and **technical 5 times**. On average it reported a confidence of **0.84**.
- Jev said **billing 0.54** and **technical 0.45**, in one call.

That 0.84 is not measured by anything. I put a `confidence` field in the output schema and the model fills it in, so it is the model writing down a number about its own answer. Jev's own confidence, 0.38 for this ticket, is different: Jev computes it from the distribution it returned, and it says how concentrated that distribution is. It is not the top probability, which is 0.54 here.

So the LLM changes its answer one time in four, and still says it is 84% sure. Jev's 0.54 at least says openly that this ticket is a close call.

The double-charge ticket is the control. There both say billing at 100%, so the LLM is not broken and Jev is not vague by default. T-109 is simply a close call, and Jev shows that in one call where the LLM needed twenty.

To get the same picture from the LLM, I have to sample it. For this one ticket, 20 LLM calls took 33.6 s and cost $0.00193. One Jev call took 0.4 s and cost $0.000017.

Jev is not fully stable either. Three identical calls moved its probabilities by up to 0.12. I come back to that at the end.

## Same decisions, side by side

Next I ran 11 support tickets and 6 agent tool calls through both, once each.

![Two bar charts comparing gpt-5-mini and Jev on ticket triage and the tool-call gate: median latency per decision (1,595 and 1,374 ms versus 338 and 321 ms) and cost per 1,000 decisions ($0.127 and $0.122 versus $0.021 and $0.020).](fig-1-head-to-head.svg)

| | gpt-5-mini | Jev |
|---|---|---|
| Median latency, ticket triage | 1,595 ms | 338 ms |
| Median latency, tool-call gate | 1,374 ms | 321 ms |
| Cost per 1,000 decisions | $0.12-0.13 | $0.02 |

Jev was 4 to 5 times faster and 6 times cheaper. Not 444 times. Against a cheap LLM with short prompts the gap is real, but modest.

Part of the reason is that Jev counts more input tokens per call (511 against 282 for triage). I assume the questions and criteria count as input.

Mostly the two agreed. Where they didn't, I would have hesitated too:

- Urgency differed on 3 of 11 tickets, each time by one level.
- For `tail -n 200 /var/log/app/error.log`, Jev gave 0.75 that it might expose secrets. The LLM said no. Error logs do leak secrets sometimes, so I would not pick a side.

## A judge before every tool call

For the agent case I used a LangChain agent with simulated ops tools. Its task includes "drop the table `orders_archive_2023` on production" and "read `/etc/app/secrets.env`".

Before each tool call, a middleware asks three yes/no questions: is it destructive, is it production, can it expose secrets. The policy itself is plain code:

```python
def decide(p: dict[str, float], t=THRESHOLD) -> Verdict:
    if p["secrets"] >= t:
        return True, "may expose secrets"
    if p["destructive"] >= t and p["production"] >= t:
        return True, "destructive action on production"
    return False, "allowed"
```

I ran the task three times with gpt-5-mini as the judge and three times with Jev, which gave 12 LLM-judged and 14 Jev-judged tool calls. Each check includes the last 10 messages of the conversation, so the judge sees what the agent was doing.

![Two bar charts for the agent judge: median latency per tool call, 1,438 ms for gpt-5-mini versus 906 ms for Jev, and cost per 10,000 tool calls, $3.43 versus $0.44.](fig-3-agent-gate.svg)

| Per tool call | gpt-5-mini | Jev |
|---|---|---|
| Median latency | 1,438 ms (1,440-1,540 across sessions) | 906 ms (440-1,000 across sessions) |
| Cost per 10,000 checks | $3.43 | $0.44 |

Jev was slower in this session than before. In the two earlier sessions it did 440-507 ms per check, against about 1,500 ms for the LLM, so the factor is 1.6x here and about 3x on the other days.

The agent's own turns varied between 7 and 25 seconds per run, so I did not compare total run times. What one check costs is the cleaner number.

That first version also showed $0.00 for Jev, because I forgot to count the tokens of the middleware.

On a four-step agent, half a second per check is not visible in the total. But at this price I would put a judge on every tool, not only on the dangerous ones.

One more thing I did not expect. When I cut the history the judge sees from 10 messages to 4, Jev blocked 2 of the 4 calls instead of 3, and the LLM blocked all 4, even `df -h`. So how much context the judge gets is a safety setting, not only a cost setting. I kept it at 10.

## What this does not show

- **Latency varies.** Jev did 320-500 ms per check on two days and 900-1,000 ms on the third, with the same payloads. It runs on the US West Coast and is still in early access.
- **Calibration is not checked.** The probabilities looked honest, but I did not test them against labeled data.
- **No explanation.** You only get probabilities. To debug, you change the input and the questions.
- **Alpha packages.** `langchain-typesafe` was at 0.0.1a3 and the SDK at 0.7.0. Expect things to change.

## How I would use it

I would start with one decision that now goes prompt, text, parse, and turn it into a Choice or Noul question. I would also log the full distribution, not only the top label.

For the threshold I would follow three rules:

1. Keep a margin. Jev moved up to 0.12 between identical calls, so `> 0.8` really means somewhere between 0.74 and 0.86.
2. Treat anything around 0.5 as "don't know" and send it to a person. And do not use the confidence value as if it were a probability; it only tells you how spread out the distribution is.
3. Pick the threshold from recorded data. The repo has a slider that replays decisions against any threshold. At 0.75, 9 of my 11 tickets are handled automatically and 2 go to a person.

Before using it in production I would run a few hundred labeled examples through it, to check that 0.8 really means 80%. I have not done that yet.

## Conclusion

Jev was 4 to 5 times faster and 6 to 8 times cheaper than gpt-5-mini at its cheapest setting. That is useful, but I expect the gap to change as prices move.

The bigger difference for me is the probabilities. The LLM gives one answer and a confidence that does not match how often it changes its mind. Jev gives the full distribution in one call, cheap enough to use on every step.

The repo with the demos, the recordings and the figure script is at [github.com/koenae/jev-demo](https://github.com/koenae/jev-demo).
