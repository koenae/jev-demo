"""The LLM side of every comparison: the same criteria text as Jev gets, via structured output.

Used by demo 3 (LLM gate), demo 4 (head-to-head) and demo 5 (one call vs samples), so all
three compare against exactly the same prompt and schema.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from jevdemo.gate_questions import GATE_QUESTIONS
from jevdemo.questions import REFUND, TEAMS, URGENCY_LEVELS


class TriageAnswer(BaseModel):
    team: Literal["billing", "technical", "sales", "other"]
    urgency: int = Field(ge=0, le=2, description="0, 1 or 2 as defined in the rubric")
    refund: bool = Field(description="Does the customer ask for money back?")


class TeamAnswer(BaseModel):
    team: Literal["billing", "technical", "sales", "other"]
    confidence: float = Field(ge=0, le=1, description="Your own confidence in `team`, 0 to 1")


class GateAnswer(BaseModel):
    destructive: bool
    production: bool
    secrets: bool


def _noul_text(q: Any) -> str:
    """Instructions + criteria of a Noul (SDK TypedDict or langchain pydantic model) as text."""
    text = str(q.instructions)
    crit = q.criteria
    if crit:
        yes = crit.get("true") if isinstance(crit, dict) else crit.true
        no = crit.get("false") if isinstance(crit, dict) else crit.false
        text += f" Yes when: {yes} No when: {no}"
    return text


TEAM_TEXT = "team - which team should own this ticket: " + "; ".join(f"{k}: {v}" for k, v in TEAMS.items())
TRIAGE_PROMPT = (
    "You triage customer support tickets. Answer with JSON only.\n"
    + TEAM_TEXT
    + "\nurgency - how urgent is this ticket for the customer: "
    + "; ".join(f"{i}: {v}" for i, v in enumerate(URGENCY_LEVELS))
    + f"\nrefund - does the customer ask for money back? Yes when: {REFUND['true']} No when: {REFUND['false']}"
)
TEAM_PROMPT = (
    "You triage customer support tickets. Answer with JSON only.\n"
    + TEAM_TEXT
    + "\nconfidence - how confident you are in your team choice, from 0 to 1."
)
GATE_PROMPT = (
    "You review a proposed tool call from an SRE agent. Answer with JSON only.\n"
    + "\n".join(f"{name} - {_noul_text(q)}" for name, q in GATE_QUESTIONS.items())
)


def llm_answer(llm, system_prompt: str, state: Any, schema: type[BaseModel]) -> tuple[dict[str, Any], float, int | None, int | None]:
    """One structured-output call; returns (answer, latency_ms, input_tokens, output_tokens)."""
    structured = llm.with_structured_output(schema, include_raw=True)
    started = perf_counter()
    out = structured.invoke([("system", system_prompt), ("human", json.dumps(state, default=str))])
    ms = (perf_counter() - started) * 1000
    parsed, raw = out["parsed"], out["raw"]
    if parsed is None:
        raise RuntimeError(f"LLM returned no valid JSON: {out.get('parsing_error')}")
    usage = getattr(raw, "usage_metadata", None) or {}
    return parsed.model_dump(), ms, usage.get("input_tokens"), usage.get("output_tokens")


def llm_price_from_env() -> tuple[float, float] | None:
    """(input, output) USD per million tokens from LLM_PRICE_*; None when not configured."""
    import os

    from jevdemo.config import load_env

    load_env()
    tin, tout = os.environ.get("LLM_PRICE_INPUT_PER_MTOK", ""), os.environ.get("LLM_PRICE_OUTPUT_PER_MTOK", "")
    if not tin or not tout:
        return None
    return float(tin), float(tout)


JEV_INPUT_USD_PER_MTOK = 0.042  # vendor price; output tokens are free


def cost_usd(system: str, tin: int, tout: int, llm_prices: tuple[float, float] | None) -> float | None:
    if system == "jev":
        return tin * JEV_INPUT_USD_PER_MTOK / 1e6
    if llm_prices is None:
        return None
    return (tin * llm_prices[0] + tout * llm_prices[1]) / 1e6
