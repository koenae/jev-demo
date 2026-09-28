"""Demo 2 - Confidence gate: route a batch of tickets, escalate the uncertain ones."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from typesafe_sdk import Choice, Score, TypeSafeClient

from jevdemo.questions import TEAMS, URGENCY_LEVELS
from jevdemo.jev import (
    CallMeta,
    ChoiceView,
    ScoreView,
    answer_from_dict,
    answer_to_dict,
    make_client,
    timed_system_one,
    view,
)
from jevdemo.recording import Mode, load_recording, origin_of, save_recording

RECORDING = "demo2_confidence_gate"
DEFAULT_THRESHOLD = 0.75


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str
    note: str = ""  # why this ticket is in the set (shown in speaker notes only)


TICKETS: list[Ticket] = [
    Ticket("T-101", "Your API returns 502 on every request since 09:00 UTC. Our checkout is down.",
           "clear technical, urgent"),
    Ticket("T-102", "I was charged EUR 49 twice this month. Please refund one of them.",
           "clear billing"),
    Ticket("T-103", "Do you offer a discount for non-profits if we take the annual plan?",
           "clear sales"),
    Ticket("T-104", "Where can I download my invoices as PDF? I can't find the button.",
           "billing vs other: mild ambiguity"),
    Ticket("T-105", "The webhook for 'invoice.paid' never fires, so our accounting sync is broken "
                    "and finance can't close the month.",
           "ambiguous: technical or billing"),
    Ticket("T-106", "How many seats are included in the Team plan, and can we add SSO later?",
           "sales vs technical"),
    Ticket("T-107", "Password reset email never arrives (checked spam). Locked out of my account.",
           "clear technical"),
    Ticket("T-108", "Thanks for the great support last week, no action needed!",
           "clear other"),
    Ticket("T-109", "My subscription renewed but the new features from the upgrade aren't showing. "
                    "Did the payment go through or is this a bug?",
           "deliberately ambiguous: billing / technical"),
    Ticket("T-110", "Can you tell me what the price would be for 250 users, and does that include "
                    "priority support with an SLA?",
           "sales, with a support angle"),
    Ticket("T-111", "hello?? still waiting", "deliberately ambiguous: no content"),
]

QUESTIONS = {
    "team": Choice(instructions="Which team should own this ticket?", criteria=TEAMS),
    "urgency": Score(instructions="How urgent is this ticket?", criteria=URGENCY_LEVELS),
}


@dataclass(frozen=True)
class TicketDecision:
    ticket_id: str
    text: str
    team: ChoiceView
    urgency: ScoreView
    meta: CallMeta

    @property
    def confidence(self) -> float:
        return self.team.confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "text": self.text,
            "team": answer_to_dict(self.team),
            "urgency": answer_to_dict(self.urgency),
            "meta": self.meta.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TicketDecision":
        return cls(
            ticket_id=data["ticket_id"],
            text=data["text"],
            team=answer_from_dict(data["team"]),  # type: ignore[arg-type]
            urgency=answer_from_dict(data["urgency"]),  # type: ignore[arg-type]
            meta=CallMeta.from_dict(data["meta"]),
        )


@dataclass(frozen=True)
class ConfidenceGateResult:
    decisions: list[TicketDecision]
    origin: str = "live"

    @property
    def latencies_ms(self) -> list[float]:
        return [d.meta.latency_ms for d in self.decisions]

    def to_dict(self) -> dict[str, Any]:
        return {"decisions": [d.to_dict() for d in self.decisions]}

    @classmethod
    def from_dict(cls, data: dict[str, Any], origin: str) -> "ConfidenceGateResult":
        return cls([TicketDecision.from_dict(d) for d in data["decisions"]], origin=origin)


@dataclass(frozen=True)
class GateSummary:
    threshold: float
    auto: list[TicketDecision]
    escalated: list[TicketDecision]
    total_ms: float

    @property
    def auto_count(self) -> int:
        return len(self.auto)

    @property
    def escalated_count(self) -> int:
        return len(self.escalated)

    @property
    def auto_pct(self) -> float:
        total = self.auto_count + self.escalated_count
        return 100.0 * self.auto_count / total if total else 0.0

    @property
    def escalated_pct(self) -> float:
        return 100.0 - self.auto_pct if (self.auto_count + self.escalated_count) else 0.0


def classify_ticket(client: TypeSafeClient, ticket: Ticket) -> TicketDecision:
    """One call per ticket: which team, how urgent, and how sure Jev is."""
    response, latency_ms = timed_system_one(
        client, state={"ticket": ticket.text}, questions=QUESTIONS
    )
    return TicketDecision(
        ticket_id=ticket.id,
        text=ticket.text,
        team=view(response.choices["team"]),
        urgency=view(response.scores["urgency"]),
        meta=CallMeta.of(response, latency_ms),
    )


def gate(decisions: list[TicketDecision], threshold: float = DEFAULT_THRESHOLD) -> GateSummary:
    """The confidence gate itself: pure code, no API call, so it can be re-run at any threshold."""
    auto = [d for d in decisions if d.team.confidence >= threshold]
    escalated = [d for d in decisions if d.team.confidence < threshold]
    total_ms = sum(d.meta.latency_ms for d in decisions)
    return GateSummary(threshold, auto, escalated, total_ms)


def classify_tickets(client: TypeSafeClient, tickets: list[Ticket]) -> list[TicketDecision]:
    return [classify_ticket(client, ticket) for ticket in tickets]


def run_confidence_gate(mode: Mode = "live", tickets: list[Ticket] = TICKETS) -> ConfidenceGateResult:
    """Entry point for the CLI: classify every ticket (or replay), never apply the gate."""
    if mode == "offline":
        envelope = load_recording(RECORDING)
        return ConfidenceGateResult.from_dict(envelope["data"], origin=origin_of(envelope))
    with make_client() as client:
        result = ConfidenceGateResult(classify_tickets(client, tickets))
    if mode == "record":
        save_recording(RECORDING, result.to_dict())
    return result
