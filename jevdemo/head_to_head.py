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

from typesafe_sdk import TypeSafeClient

from jevdemo import agent_gate, confidence_gate, smart_if
from jevdemo.config import build_chat_model, llm_settings
from jevdemo.gate_questions import GATE_QUESTIONS_SDK
from jevdemo.jev import make_client, timed_system_one
from jevdemo.latency import LatencyStats, percentile
from jevdemo.recording import Mode, load_recording, origin_of, save_recording

RECORDING = "demo4_head_to_head"
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


def gate_state(call: dict[str, Any]) -> dict[str, Any]:
    return {"tool_call": call, "tool_description": TOOL_DESCRIPTIONS[call["name"]]}


from jevdemo.llm_judge import (  # noqa: E402  (kept near its use)
    GATE_PROMPT,
    JEV_INPUT_USD_PER_MTOK,
    TRIAGE_PROMPT,
    GateAnswer,
    TriageAnswer,
    cost_usd,
    llm_answer,
    llm_price_from_env,
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
    response, ms = timed_system_one(client, gate_state(call), GATE_QUESTIONS_SDK)
    p = {name: a.noul for name, a in response.nouls.items()}
    return Sample(
        "jev", "gate", item_id, {k: v >= 0.5 for k, v in p.items()}, {"p": p},
        round(ms, 1), response.usage.input_tokens, response.usage.output_tokens,
    )


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


def summarize(result: HeadToHeadResult) -> dict[tuple[Task, System], SystemSummary]:
    out: dict[tuple[Task, System], SystemSummary] = {}
    for task in ("triage", "gate"):
        for system in ("jev", "llm"):
            rows = [s for s in result.samples if s.task == task and s.system == system]
            if not rows:
                continue
            tin = sum(s.input_tokens or 0 for s in rows)
            tout = sum(s.output_tokens or 0 for s in rows)
            cost = cost_usd(system, tin, tout, result.llm_usd_per_mtok)
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
    result = HeadToHeadResult(samples, settings.label, jev_model, llm_price_from_env(), workers)
    if mode == "record":
        save_recording(RECORDING, result.to_dict())
    return result


__all__ = [
    "GATE_ITEMS", "TRIAGE_ITEMS", "HeadToHeadResult", "Sample", "SystemSummary",
    "agreement", "run_head_to_head", "speedup", "summarize", "median", "percentile",
]
