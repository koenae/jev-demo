---
title: "What I measured when I put Jev next to gpt-5-mini"
date: 2026-09-29
slug: jev-vs-llm-measured
type: posts
summary: "I ran the same support tickets and agent tool calls through Jev and gpt-5-mini. On one ambiguous ticket, asked twenty times, gpt-5-mini answered billing fifteen times and technical five. Jev returned both probabilities in one call."
draft: true
---

## Cool demos, but what does it do

I first saw Jev in a few demos online. One where an agent browses a lot faster than the usual screenshot-and-think loop. One where an assistant on a Mac fires off actions almost in real time, as if there was no model in between. That triggered me into finding out what this Jev thing is all about.

Jev is a model from TypeSafe, launched this month. It does not generate text. You send it some state and a typed question, and you get probabilities back. That is what makes those demos fast: nothing to parse, nothing to wait for, just a number per option.

There are three question types:

1. **Choice** picks one of N labels, with a probability per label.
2. **Score** places the input on an ordered scale, with a probability per level.
3. **Noul** is a yes/no question. It returns P(yes).

TypeSafe puts numbers next to it: 70-500 ms latency and "193x faster / 444x cheaper" than an LLM workflow. Those are their numbers on their workloads. There is now public access for the API for everyone to play around with it. So I built [a small repo](https://github.com/koenae/jev-demo) that sends the same decisions to Jev and to gpt-5-mini and records every call.

## The setup

- **LLM:** gpt-5-mini on Microsoft Foundry, with `reasoning_effort=minimal` (its fastest and cheapest setting) and structured output. $0.25 input and $2.00 output per million tokens.
- **Jev:** `jev-latest` through the Python SDK. $0.042 per million input tokens, output is free.
- Both get the same criteria text and run 4 calls in parallel.

I measured agreement, not accuracy. I had no labeled data, so "agree" only means both gave the same answer.

Finding the gpt-5-mini price took longer than running the benchmark. The Foundry portal did not show it in a way I could find, so I queried the Azure Retail Prices API directly. The repo has a script for that.

## Asking the same question twenty times

The task is support ticket triage: which team should handle a ticket, with billing, technical, sales and other as the options. Both systems get the same one-line description per team. I took the most ambiguous ticket in my set of eleven:

> My subscription renewed but the new features from the upgrade aren't showing. Did the payment go through or is this a bug?

This could be billing or technical. I asked gpt-5-mini the team question twenty times, and Jev once. Next to it, as a control, a ticket where there is nothing to doubt: "I was charged EUR 49 twice this month. Please refund one of them."

![Two bar charts. Left, the ambiguous upgrade ticket: gpt-5-mini answered billing 15 times and technical 5 times out of 20 calls, Jev gave billing 0.54 and technical 0.45 in one call. Right, the clear double-charge ticket: both give billing 1.00.](/fig-2-one-call-vs-samples.svg)

- gpt-5-mini said **billing 15 times** and **technical 5 times**. On average it reported a confidence of **0.84**.
- Jev said **billing 0.54** and **technical 0.45**, in one call.

That 0.84 is not measured by anything. I put a confidence field in the output schema and the model fills it in, so it is the model writing down a number about its own answer. Jev's own confidence, 0.38 for this ticket, is different: Jev computes it from the distribution it returned, and it says how concentrated that distribution is. It is not the top probability, which is 0.54 here.

So the LLM changes its answer one time in four, and still says it is 84% sure. Jev's 0.54 at least says openly that this ticket is a close call.

The double-charge ticket is the control. There both say billing at 100%, so the LLM is not broken and Jev is not vague by default. The upgrade ticket is simply a close call, and Jev shows that in one call where the LLM needed twenty.

Getting that split from the LLM is slow and expensive. It gives one answer per call, so I needed 20 calls. Together they took 33.6 s and cost $0.00193. One Jev call took 0.4 s and cost $0.000017.

Jev was not fully stable during my testing. Three identical calls moved its probabilities by up to 0.12, so a threshold on these numbers needs some margin.

## Same decisions, side by side

Next I gave both the same two tasks, once per item:

1. **Ticket triage.** For 11 support tickets: which team, how urgent, and does the customer ask for a refund.
2. **Tool-call gate.** For 6 commands an agent could want to run, like dropping a database table or reading a log file: is it destructive, does it touch production, can it expose secrets. Each command is checked on its own, without any conversation around it.

![Two bar charts comparing gpt-5-mini and Jev on ticket triage and the tool-call gate: median latency per decision (1,595 and 1,374 ms versus 338 and 321 ms) and cost per 1,000 decisions ($0.127 and $0.122 versus $0.021 and $0.020).](/fig-1-head-to-head.svg)

Jev was 4 to 5 times faster and about 6 times cheaper. Not the 444x from TypeSafe's page, but they do not say which LLM or prompt they compare with. Mine is a cheap model with a short prompt.

The figure shows speed and cost. I also compared the answers themselves. Both gave the same team, refund and gate verdicts on every item. They only differed on urgency for 3 of the 11 tickets, always one level apart, and on the error log, where Jev saw a 0.75 chance of secrets and the LLM saw none. Neither is clearly wrong there.

## A judge before every tool call

The tool-call gate above checked loose commands. Here the same three questions run inside an agent that is actually doing a task, and the judge also gets the conversation around each call.

I used a LangChain agent with simulated ops tools. Its task includes "drop the table `orders_archive_2023` on production" and "read `/etc/app/secrets.env`".

Before each tool call, a middleware asks three yes/no questions: is it destructive, is it production, can it expose secrets. Whoever answers those questions is what I call the judge here. In one set of runs that is gpt-5-mini, in the other it is Jev. The policy that turns the three answers into allow or block is plain code:

```python
def decide(p: dict[str, float], t=THRESHOLD) -> Verdict:
    if p["secrets"] >= t:
        return True, "may expose secrets"
    if p["destructive"] >= t and p["production"] >= t:
        return True, "destructive action on production"
    return False, "allowed"
```

I ran the task three times with gpt-5-mini as the judge and three times with Jev, which gave 12 LLM-judged and 14 Jev-judged tool calls. The two extra calls come from one run where the agent retried after a block. Each check sends the judge the tool call plus the last 10 messages of the conversation, so it sees what the agent was doing.

![Two bar charts for the agent judge: median latency per tool call, 1,438 ms for gpt-5-mini versus 906 ms for Jev, and cost per 10,000 tool calls, $3.43 versus $0.44.](/fig-3-agent-gate.svg)

Per check, Jev took 906 ms against 1,438 ms for the LLM, and cost $0.44 per 10,000 checks against $3.43.

The judge is a small part of the run. The agent's own turns took 7 to 25 seconds, so a check of half a second does not show in the total. At this price it can sit in front of every tool.

The context the judge gets matters. With 4 messages of history instead of 10, Jev blocked 2 of the 4 calls instead of the usual 3, and the LLM blocked all 4, even `df -h`.

## Conclusion

Jev was 4 to 5 times faster and 6 to 8 times cheaper than gpt-5-mini at its cheapest setting.

The bigger difference for me is the probabilities. The LLM gives one answer and a confidence that does not match how often it changes its mind. Jev gives the full distribution in one call, cheap enough to use on every step.

Code and recordings: [github.com/koenae/jev-demo](https://github.com/koenae/jev-demo).
