"""Demo 1 - "Smart if": one support ticket, one API call, three typed answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

from jevdemo.jev import (
    CallMeta,
    ChoiceView,
    NoulView,
    ScoreView,
    answer_from_dict,
    answer_to_dict,
    make_client,
    timed_system_one,
    view,
)
from jevdemo.recording import Mode, load_recording, origin_of, save_recording

RECORDING = "demo1_smart_if"

TICKET = (
    "Hi, I upgraded to the Pro plan on Monday but my invoice shows I was charged twice "
    "(EUR 49 and again EUR 49). I need one of those charges reversed. On top of that the "
    "export to CSV has been failing all week with a 500 error and my quarterly report is "
    "due tomorrow morning, so please look at this today."
)

QUESTIONS = {
    "team": Choice(
        instructions="Which team should own this ticket?",
        criteria={
            "billing": "Invoices, charges, refunds, subscriptions.",
            "technical": "Bugs, errors, integrations, outages.",
            "sales": "Plans, pricing, upgrades before purchase.",
            "other": "Anything else.",
        },
    ),
    "urgency": Score(
        instructions="How urgent is this ticket for the customer?",
        criteria=[
            "No time pressure; can wait a week.",
            "Should be handled within a few days.",
            "Blocking the customer; needs a same-day response.",
        ],
    ),
    "refund": Noul(
        instructions="Does the customer ask for money back?",
        criteria=NoulCriteria(
            true="The customer explicitly wants a charge reversed, refunded or credited.",
            false="The customer only reports a problem or asks a question.",
        ),
    ),
}


@dataclass(frozen=True)
class SmartIfResult:
    ticket: str
    team: ChoiceView
    urgency: ScoreView
    refund: NoulView
    meta: CallMeta
    origin: str = "live"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.ticket,
            "answers": {
                "team": answer_to_dict(self.team),
                "urgency": answer_to_dict(self.urgency),
                "refund": answer_to_dict(self.refund),
            },
            "meta": self.meta.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], origin: str) -> "SmartIfResult":
        answers = data["answers"]
        return cls(
            ticket=data["ticket"],
            team=answer_from_dict(answers["team"]),  # type: ignore[arg-type]
            urgency=answer_from_dict(answers["urgency"]),  # type: ignore[arg-type]
            refund=answer_from_dict(answers["refund"]),  # type: ignore[arg-type]
            meta=CallMeta.from_dict(data["meta"]),
            origin=origin,
        )


def smart_if(client: TypeSafeClient, ticket: str) -> SmartIfResult:
    """One round-trip to Jev; three typed, schema-guaranteed answers."""
    response, latency_ms = timed_system_one(
        client, state={"ticket": ticket}, questions=QUESTIONS
    )
    team = response.choices["team"]        # .choice, .confidence, .probabilities
    urgency = response.scores["urgency"]   # .score (weighted), .probabilities per level
    refund = response.nouls["refund"]      # .noul = P(yes)
    return SmartIfResult(
        ticket=ticket,
        team=view(team),
        urgency=view(urgency),
        refund=view(refund),
        meta=CallMeta.of(response, latency_ms),
    )


def run_smart_if(mode: Mode = "live", ticket: str = TICKET) -> SmartIfResult:
    """Entry point used by the CLI and the slides; handles live / record / offline."""
    if mode == "offline":
        envelope = load_recording(RECORDING)
        return SmartIfResult.from_dict(envelope["data"], origin=origin_of(envelope))
    with make_client() as client:
        result = smart_if(client, ticket)
    if mode == "record":
        save_recording(RECORDING, result.to_dict())
    return result
