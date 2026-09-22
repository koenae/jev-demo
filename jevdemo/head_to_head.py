"""Demo 4 - Head-to-head: the same decisions made by an LLM (structured output) and by Jev.

Two tasks, both systems, same criteria text:
  * triage: 11 support tickets -> team / urgency / refund?   (demo 2's tickets)
  * gate:   6 proposed tool calls -> destructive? production? secrets?  (demo 3's questions)

Per call we record latency, tokens and the answer; `summarize()` turns that into
median/p95, cost and the agreement rate between the two systems.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import median
from time import perf_counter
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field
from typesafe_sdk import TypeSafeClient

from jevdemo import agent_gate, confidence_gate, smart_if
from jevdemo.config import build_chat_model, llm_settings, load_env
from jevdemo.jev import make_client, timed_system_one
from jevdemo.latency import LatencyStats, percentile
from jevdemo.questions import REFUND, TEAMS, URGENCY_LEVELS
from jevdemo.recording import Mode, load_recording, origin_of, save_recording

RECORDING = "demo4_head_to_head"
JEV_INPUT_USD_PER_MTOK = 0.042  # vendor price; output tokens are free
WORKERS = 4

# --- Tasks ----------------------------------------------------------------------------------

TRIAGE_ITEMS = [(t.id, {"ticket": t.text}) for t in confidence_gate.TICKETS]

GATE_ITEMS: list[tuple[str, dict[str, Any]]] = [
    ("G-1", {"name": "run_shell", "args": {"command": "df -h", "host": "app-01"}}),
    ("G-2", {"name": "run_sql", "args": {"query": "SELECT query, mean_exec_time FROM pg_stat_statements "
                                          "ORDER BY mean_exec_time DESC LIMIT 5", "database": "orders-production"}}),
    ("G-3", {"name": "run_sql", "args": {"query": "DROP TABLE orders_archive_2023", "database": "orders-production"}}),
    ("G-4", {"name": "read_file", "args": {"path": "/etc/app/secrets.env", "host": "app-01"}}),
    ("G-5", {"name": "run_sql", "args": {"query": "TRUNCATE TABLE sessions", "database": "analytics-staging"}}),
    ("G-6", {"name": "run_shell", "args": {"command": "tail -n 200 /var/log/app/error.log", "host": "build-02"}}),
]
TOOL_DESCRIPTIONS = {t.name: t.description for t in agent_gate.TOOLS}
# demo 3 defines its questions with langchain-typesafe's types; the SDK accepts them as dicts
GATE_QUESTIONS = {name: q.model_dump() for name, q in agent_gate.GATE_QUESTIONS.items()}


def gate_state(call: dict[str, Any]) -> dict[str, Any]:
    return {"tool_call": call, "tool_description": TOOL_DESCRIPTIONS[call["name"]]}


# The LLM gets the *same* criteria text as Jev, as a system prompt + JSON schema.

class TriageAnswer(BaseModel):
    team: Literal["billing", "technical", "sales", "other"]
    urgency: int = Field(ge=0, le=2, description="0, 1 or 2 as defined in the rubric")
    refund: bool = Field(description="Does the customer ask for money back?")


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


TRIAGE_PROMPT = (
    "You triage customer support tickets. Answer with JSON only.\n"
    "team - which team should own this ticket: "
    + "; ".join(f"{k}: {v}" for k, v in TEAMS.items())
    + "\nurgency - how urgent is this ticket for the customer: "
    + "; ".join(f"{i}: {v}" for i, v in enumerate(URGENCY_LEVELS))
    + f"\nrefund - does the customer ask for money back? Yes when: {REFUND['true']} No when: {REFUND['false']}"
)
GATE_PROMPT = (
    "You review a proposed tool call from an SRE agent. Answer with JSON only.\n"
    + "\n".join(f"{name} - {_noul_text(q)}" for name, q in agent_gate.GATE_QUESTIONS.items())
)

# --- Samples --------------------------------------------------------------------------------

System = Literal["jev", "llm"]
Task = Literal["triage", "gate"]


@dataclass(frozen=True)
class Sample:
    system: System
    task: Task
    item_id: str
    answer: dict[str, Any]         # normalized: triage -> team/urgency/refund, gate -> 3 bools
    detail: dict[str, Any]         # jev: probabilities; llm: raw output
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Sample":
        return cls(**d)


def jev_triage(client: TypeSafeClient, item_id: str, state: dict[str, Any]) -> Sample:
    response, ms = timed_system_one(client, state, smart_if.QUESTIONS)
    team, urg, ref = response.choices["team"], response.scores["urgency"], response.nouls["refund"]
    level = max(urg.probabilities, key=urg.probabilities.__getitem__)
    return Sample(
        "jev", "triage", item_id,
        {"team": team.choice, "urgency": level, "refund": ref.noul >= 0.5},
        {"team_p": team.probabilities, "team_confidence": team.confidence,
         "urgency_p": {str(k): v for k, v in urg.probabilities.items()}, "refund_p": ref.noul},
        round(ms, 1), response.usage.input_tokens, response.usage.output_tokens,
    )


def jev_gate(client: TypeSafeClient, item_id: str, call: dict[str, Any]) -> Sample:
    response, ms = timed_system_one(client, gate_state(call), GATE_QUESTIONS)
    p = {name: a.noul for name, a in response.nouls.items()}
    return Sample(
        "jev", "gate", item_id, {k: v >= 0.5 for k, v in p.items()}, {"p": p},
        round(ms, 1), response.usage.input_tokens, response.usage.output_tokens,
    )


def llm_answer(llm, system_prompt: str, state: dict[str, Any], schema: type[BaseModel]) -> tuple[dict[str, Any], float, int | None, int | None]:
    """One structured-output call; returns (answer, latency_ms, input_tokens, output_tokens)."""
    import json

    structured = llm.with_structured_output(schema, include_raw=True)
    started = perf_counter()
    out = structured.invoke([("system", system_prompt), ("human", json.dumps(state))])
    ms = (perf_counter() - started) * 1000
    parsed, raw = out["parsed"], out["raw"]
    if parsed is None:
        raise RuntimeError(f"LLM returned no valid JSON: {out.get('parsing_error')}")
    usage = getattr(raw, "usage_metadata", None) or {}
    return parsed.model_dump(), ms, usage.get("input_tokens"), usage.get("output_tokens")


def llm_triage(llm, item_id: str, state: dict[str, Any]) -> Sample:
    answer, ms, tin, tout = llm_answer(llm, TRIAGE_PROMPT, state, TriageAnswer)
    return Sample("llm", "triage", item_id, answer, {"raw": answer}, round(ms, 1), tin, tout)


def llm_gate(llm, item_id: str, call: dict[str, Any]) -> Sample:
    answer, ms, tin, tout = llm_answer(llm, GATE_PROMPT, gate_state(call), GateAnswer)
    return Sample("llm", "gate", item_id, answer, {"raw": answer}, round(ms, 1), tin, tout)


# --- Result + summary -----------------------------------------------------------------------


@dataclass(frozen=True)
class HeadToHeadResult:
    samples: list[Sample]
    llm: str
    jev_model: str
    llm_usd_per_mtok: tuple[float, float] | None   # (input, output); None = not configured
    workers: int = WORKERS
    origin: str = "live"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples": [s.to_dict() for s in self.samples],
            "llm": self.llm,
            "jev_model": self.jev_model,
            "llm_usd_per_mtok": list(self.llm_usd_per_mtok) if self.llm_usd_per_mtok else None,
            "workers": self.workers,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], origin: str) -> "HeadToHeadResult":
        prices = d.get("llm_usd_per_mtok")
        return cls(
            [Sample.from_dict(s) for s in d["samples"]], d["llm"], d["jev_model"],
            (prices[0], prices[1]) if prices else None, d.get("workers", WORKERS), origin,
        )


@dataclass(frozen=True)
class SystemSummary:
    system: System
    task: Task
    n: int
    latency: LatencyStats
    input_tokens: int
    output_tokens: int
    cost_usd: float | None          # for the n calls
    cost_per_1000_usd: float | None


def _cost(system: System, tin: int, tout: int, llm_prices: tuple[float, float] | None) -> float | None:
    if system == "jev":
        return tin * JEV_INPUT_USD_PER_MTOK / 1e6
    if llm_prices is None:
        return None
    return (tin * llm_prices[0] + tout * llm_prices[1]) / 1e6


def summarize(result: HeadToHeadResult) -> dict[tuple[Task, System], SystemSummary]:
    out: dict[tuple[Task, System], SystemSummary] = {}
    for task in ("triage", "gate"):
        for system in ("jev", "llm"):
            rows = [s for s in result.samples if s.task == task and s.system == system]
            if not rows:
                continue
            tin = sum(s.input_tokens or 0 for s in rows)
            tout = sum(s.output_tokens or 0 for s in rows)
            cost = _cost(system, tin, tout, result.llm_usd_per_mtok)
            out[(task, system)] = SystemSummary(
                system, task, len(rows), LatencyStats.of([s.latency_ms for s in rows]),
                tin, tout, cost, None if cost is None else cost / len(rows) * 1000,
            )
    return out


def agreement(result: HeadToHeadResult, task: Task) -> dict[str, float]:
    """Share of items where LLM and Jev gave the same answer, per field."""
    jev = {s.item_id: s.answer for s in result.samples if s.task == task and s.system == "jev"}
    llm = {s.item_id: s.answer for s in result.samples if s.task == task and s.system == "llm"}
    ids = sorted(set(jev) & set(llm))
    if not ids:
        return {}
    fields = list(jev[ids[0]])
    return {f: sum(jev[i][f] == llm[i][f] for i in ids) / len(ids) for f in fields}


def speedup(summary: dict[tuple[Task, System], SystemSummary], task: Task) -> tuple[float | None, float | None]:
    """(latency factor, cost factor) LLM / Jev for a task; None when not computable."""
    j, l = summary.get((task, "jev")), summary.get((task, "llm"))
    if not j or not l:
        return None, None
    lat = l.latency.median_ms / j.latency.median_ms if j.latency.median_ms else None
    cost = (l.cost_usd / j.cost_usd) if (l.cost_usd is not None and j.cost_usd) else None
    return lat, cost


# --- Entry point ----------------------------------------------------------------------------


def llm_prices_from_env() -> tuple[float, float] | None:
    load_env()
    tin, tout = os.environ.get("LLM_PRICE_INPUT_PER_MTOK", ""), os.environ.get("LLM_PRICE_OUTPUT_PER_MTOK", "")
    if not tin or not tout:
        return None
    return float(tin), float(tout)


def _run_all(fn: Callable[..., Sample], items: list[tuple[str, dict[str, Any]]], workers: int) -> list[Sample]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda it: fn(it[0], it[1]), items))


def run_head_to_head(mode: Mode = "live", workers: int = WORKERS) -> HeadToHeadResult:
    """Run every item through both systems (or replay). Calls run `workers` at a time."""
    if mode == "offline":
        envelope = load_recording(RECORDING)
        return HeadToHeadResult.from_dict(envelope["data"], origin=origin_of(envelope))

    settings = llm_settings()
    llm = build_chat_model(settings)
    samples: list[Sample] = []
    with make_client(timeout=30.0) as client:
        samples += _run_all(lambda i, s: jev_triage(client, i, s), TRIAGE_ITEMS, workers)
        samples += _run_all(lambda i, c: jev_gate(client, i, c), GATE_ITEMS, workers)
    jev_model = os.environ.get("TYPESAFE_DEFAULT_MODEL", "").strip() or "jev-latest"
    samples += _run_all(lambda i, s: llm_triage(llm, i, s), TRIAGE_ITEMS, workers)
    samples += _run_all(lambda i, c: llm_gate(llm, i, c), GATE_ITEMS, workers)
    result = HeadToHeadResult(samples, settings.label, jev_model, llm_prices_from_env(), workers)
    if mode == "record":
        save_recording(RECORDING, result.to_dict())
    return result


__all__ = [
    "GATE_ITEMS", "TRIAGE_ITEMS", "HeadToHeadResult", "Sample", "SystemSummary",
    "agreement", "run_head_to_head", "speedup", "summarize", "median", "percentile",
]
