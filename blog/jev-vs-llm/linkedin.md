# LinkedIn post

Image: `linkedin-cover.png` (1200 x 627). Text below is the post body.

---

I sent the same decisions to TypeSafe's Jev and to gpt-5-mini, and recorded every call.

Jev is a small model that only answers structured questions: pick one option, give a score, or yes/no. It returns a probability per option instead of text. TypeSafe calls it a System 1 model, after Kahneman.

What I measured:

- Ticket triage and a tool-call safety check: Jev was 4 to 5 times faster and 6 to 8 times cheaper than gpt-5-mini at its cheapest setting.
- On an ambiguous ticket, gpt-5-mini gave a different answer 5 times out of 20, while reporting 84% confidence every time. Jev gave billing 0.54 and technical 0.45 in one call.
- As a judge in front of every agent tool call: 906 ms and $0.44 per 10,000 checks, against 1,438 ms and $3.43 for gpt-5-mini.

The speed and cost gap is nice, but I expect it to move as prices move. The part I find more useful is getting the full distribution in one call, cheap enough to run on every step. The LLM's own confidence number did not tell me much.

No labeled data, so this is agreement, not accuracy. Details, figures and the recordings are in the post and the repo.

Post: https://koenaerts.com/posts/jev-vs-llm-measured/
Repo: https://github.com/koenae/jev-demo
