"""Demo 5 - One call vs N samples: what an LLM answer *is*, next to what Jev returns.

For a few tickets we ask the LLM the same question N times (default 20). Each answer is one
sample from a distribution you never get to see, plus a self-reported confidence. Jev is
asked once (well, `jev_repeats` times, to show it is stable) and returns the distribution.
"""

from __future__ import annotations

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from typesafe_sdk import Choice, TypeSafeClient

from jevdemo import confidence_gate
from jevdemo.config import build_chat_model, llm_settings, load_env
from jevdemo.jev import make_client, timed_system_one
from jevdemo.llm_judge import TEAM_PROMPT, TeamAnswer, cost_usd, llm_answer, llm_price_from_env
from jevdemo.questions import TEAMS
from jevdemo.recording import Mode, load_recording, origin_of, save_recording

RECORDING = "demo5_one_call_vs_samples"
DEFAULT_SAMPLES = 20
DEFAULT_JEV_REPEATS = 3
WORKERS = 4

# One clearly ambiguous ticket and one clear one, so the LLM is not only caught at its weakest.
TICKET_IDS = ("T-109", "T-102")
TICKETS = {t.id: t for t in confidence_gate.TICKETS}

QUESTION = {"team": Choice(instructions="Which team should own this ticket?", criteria=TEAMS)}


@dataclass(frozen=True)
class LLMSample:
    team: str
    confidence: float          # self-reported by the LLM
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class JevCall:
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float
    input_tokens: int | None

    @property
    def team(self) -> str:
        return max(self.probabilities, key=self.probabilities.__getitem__)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TicketComparison:
    ticket_id: str
    text: str
    llm_samples: list[LLMSample]
    jev_calls: list[JevCall]

    # --- what the demo shows -------------------------------------------------------------
    @property
    def llm_distribution(self) -> dict[str, float]:
        """Fraction of samples per label: the LLM's hidden distribution, reconstructed."""
        counts = Counter(s.team for s in self.llm_samples)
        n = len(self.llm_samples) or 1
        return {label: counts.get(label, 0) / n for label in TEAMS}

    @property
    def llm_majority(self) -> str:
        return max(self.llm_distribution, key=self.llm_distribution.__getitem__)

    @property
    def llm_agreement(self) -> float:
        """Share of samples that agree with the majority label."""
        return self.llm_distribution[self.llm_majority]

    @property
    def llm_mean_confidence(self) -> float:
        return mean(s.confidence for s in self.llm_samples) if self.llm_samples else 0.0

    @property
    def jev(self) -> JevCall:
        return self.jev_calls[0]

    @property
    def jev_spread(self) -> float:
        """Largest difference between repeated Jev calls for any label (stability check)."""
        if len(self.jev_calls) < 2:
            return 0.0
        return max(
            max(c.probabilities[label] for c in self.jev_calls) - min(c.probabilities[label] for c in self.jev_calls)
            for label in TEAMS
        )

    @property
    def llm_total_ms(self) -> float:
        return sum(s.latency_ms for s in self.llm_samples)

    def llm_tokens(self) -> tuple[int, int]:
        return sum(s.input_tokens or 0 for s in self.llm_samples), sum(s.output_tokens or 0 for s in self.llm_samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "text": self.text,
            "llm_samples": [s.to_dict() for s in self.llm_samples],
            "jev_calls": [c.to_dict() for c in self.jev_calls],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TicketComparison":
        return cls(d["ticket_id"], d["text"], [LLMSample(**s) for s in d["llm_samples"]], [JevCall(**c) for c in d["jev_calls"]])


@dataclass(frozen=True)
class OneCallVsSamplesResult:
    tickets: list[TicketComparison]
    llm: str
    jev_model: str
    samples: int
    llm_usd_per_mtok: tuple[float, float] | None
    origin: str = "live"
    extra: dict[str, Any] = field(default_factory=dict)

    def costs(self, t: TicketComparison) -> tuple[float | None, float | None]:
        """(cost of N LLM samples, cost of one Jev call) in USD."""
        tin, tout = t.llm_tokens()
        return cost_usd("llm", tin, tout, self.llm_usd_per_mtok), cost_usd("jev", t.jev.input_tokens or 0, 0, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tickets": [t.to_dict() for t in self.tickets],
            "llm": self.llm,
            "jev_model": self.jev_model,
            "samples": self.samples,
            "llm_usd_per_mtok": list(self.llm_usd_per_mtok) if self.llm_usd_per_mtok else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], origin: str) -> "OneCallVsSamplesResult":
        prices = d.get("llm_usd_per_mtok")
        return cls(
            [TicketComparison.from_dict(t) for t in d["tickets"]], d["llm"], d["jev_model"], d["samples"],
            (prices[0], prices[1]) if prices else None, origin,
        )


def sample_llm(llm, text: str) -> LLMSample:
    answer, ms, tin, tout = llm_answer(llm, TEAM_PROMPT, {"ticket": text}, TeamAnswer)
    return LLMSample(answer["team"], float(answer["confidence"]), round(ms, 1), tin, tout)


def call_jev(client: TypeSafeClient, text: str) -> JevCall:
    response, ms = timed_system_one(client, {"ticket": text}, QUESTION)
    team = response.choices["team"]
    return JevCall(dict(team.probabilities), team.confidence, round(ms, 1), response.usage.input_tokens)


def compare_ticket(client: TypeSafeClient, llm, ticket_id: str, samples: int, jev_repeats: int, workers: int) -> TicketComparison:
    text = TICKETS[ticket_id].text
    with ThreadPoolExecutor(max_workers=workers) as pool:
        llm_samples = list(pool.map(lambda _: sample_llm(llm, text), range(samples)))
    jev_calls = [call_jev(client, text) for _ in range(jev_repeats)]
    return TicketComparison(ticket_id, text, llm_samples, jev_calls)


def run_one_call_vs_samples(
    mode: Mode = "live",
    samples: int | None = None,
    jev_repeats: int = DEFAULT_JEV_REPEATS,
    ticket_ids: tuple[str, ...] = TICKET_IDS,
    workers: int = WORKERS,
) -> OneCallVsSamplesResult:
    """Entry point for the CLI (live / record / offline)."""
    if mode == "offline":
        envelope = load_recording(RECORDING)
        return OneCallVsSamplesResult.from_dict(envelope["data"], origin=origin_of(envelope))
    load_env()
    samples = samples or int(os.environ.get("LLM_SAMPLES", DEFAULT_SAMPLES))
    settings = llm_settings()
    llm = build_chat_model(settings)
    with make_client(timeout=30.0) as client:
        tickets = [compare_ticket(client, llm, tid, samples, jev_repeats, workers) for tid in ticket_ids]
    jev_model = os.environ.get("TYPESAFE_DEFAULT_MODEL", "").strip() or "jev-latest"
    result = OneCallVsSamplesResult(tickets, settings.label, jev_model, samples, llm_price_from_env())
    if mode == "record":
        save_recording(RECORDING, result.to_dict())
    return result
