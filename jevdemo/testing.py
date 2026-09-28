"""A fake TypeSafe transport for self-tests when no key or network is available.

It answers every question with a schema-conform but *meaningless* distribution.
Only used by `scripts/selftest.py`; never by the demos themselves.
"""

from __future__ import annotations

import json
import random
from typing import Any

import httpx2


def _answer(question: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    kind = question["type"]
    if kind == "noul":
        return {"type": "noul", "noul": round(rng.random(), 4)}
    if kind == "choice":
        keys = list(question["criteria"])
        weights = [rng.random() for _ in keys]
        total = sum(weights)
        probs = {k: round(w / total, 4) for k, w in zip(keys, weights)}
        best = max(probs, key=probs.__getitem__)
        return {"type": "choice", "choice": best, "confidence": probs[best], "probabilities": probs}
    levels = question["criteria"]
    weights = [rng.random() for _ in levels]
    total = sum(weights)
    probs = {str(i): round(w / total, 4) for i, w in enumerate(weights)}
    score = sum(int(i) * p for i, p in probs.items())
    return {
        "type": "score",
        "score": round(score, 4),
        "confidence": max(probs.values()),
        "legend": {str(i): text for i, text in enumerate(levels)},
        "probabilities": probs,
    }


def fake_transport(seed: int = 0) -> httpx2.MockTransport:
    rng = random.Random(seed)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/models":
            body = {"models": [{"name": "jev-latest", "description": "fake", "release_date": "2026-09-15"}]}
            return httpx2.Response(200, json=body)
        payload = json.loads(request.content)
        answers = {name: _answer(q, rng) for name, q in payload["questions"].items()}
        body = {
            "model": "jev-fake",
            "answers": answers,
            "usage": {"input_tokens": len(json.dumps(payload["state"])) // 4, "output_tokens": 0},
        }
        return httpx2.Response(200, json=body, headers={"x-typesafe-request-id": "fake"})

    return httpx2.MockTransport(handler)


class FakeToolCallingLLM:
    """Build a scripted chat model that emits fixed tool calls, for the selftest only."""

    @staticmethod
    def build(tool_calls: list[dict[str, Any]], final_text: str = "Report: done."):
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langchain_core.messages import AIMessage

        class _Scripted(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):  # noqa: ANN001 - create_agent needs this
                return self

        calls = [
            {"id": f"call_{i}", "name": c["name"], "args": c["args"], "type": "tool_call"}
            for i, c in enumerate(tool_calls)
        ]
        return _Scripted(responses=[AIMessage(content="", tool_calls=calls), AIMessage(final_text)])
