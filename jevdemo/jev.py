"""Thin helpers around the TypeSafe SDK: client creation, timing and JSON-friendly answers."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping

from typesafe_sdk import (
    ChoiceAnswer,
    NoulAnswer,
    Question,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeAPIConnectionError,
    TypeSafeAPIError,
    TypeSafeAuthenticationError,
    TypeSafeClient,
    TypeSafeError,
)

from jevdemo.config import typesafe_api_key
from jevdemo.errors import DemoError

DEFAULT_TIMEOUT_S = 15.0


def make_client(timeout: float = DEFAULT_TIMEOUT_S) -> TypeSafeClient:
    """Create a TypeSafe client; raises MissingKeyError with a hint when the key is absent."""
    return TypeSafeClient(api_key=typesafe_api_key(), timeout=timeout)


def timed_system_one(
    client: TypeSafeClient, state: Any, questions: Mapping[str, Question]
) -> tuple[SystemOneResponse, float]:
    """Call `/v1/systemone` once and return `(response, latency_ms)` with clean errors."""
    started = perf_counter()
    try:
        response = client.system_one(state=state, questions=questions)
    except TypeSafeAuthenticationError as error:
        raise DemoError(
            f"TypeSafe rejected the API key ({error}).",
            hint="Check TYPESAFE_API_KEY in .env, or switch to offline mode.",
        ) from error
    except TypeSafeAPIConnectionError as error:
        raise DemoError(
            f"Could not reach api.typesafe.ai ({error}).",
            hint="Check the network (VPN/proxy?) or switch to offline mode.",
        ) from error
    except TypeSafeAPIError as error:
        raise DemoError(
            f"TypeSafe API error: {error}", hint="Retry, or switch to offline mode."
        ) from error
    except TypeSafeError as error:
        raise DemoError(f"TypeSafe SDK error: {error}") from error
    return response, (perf_counter() - started) * 1000.0


# --- JSON-friendly views of the SDK answer objects -----------------------------------------


@dataclass(frozen=True)
class ChoiceView:
    choice: str
    confidence: float
    probabilities: dict[str, float]
    type: str = "choice"


@dataclass(frozen=True)
class ScoreView:
    score: float
    confidence: float
    probabilities: dict[int, float]
    legend: dict[int, str]
    type: str = "score"

    @property
    def level(self) -> int:
        """Most probable rubric level (the `score` itself is a probability-weighted average)."""
        return max(self.probabilities, key=self.probabilities.__getitem__)

    @property
    def label(self) -> str:
        return str(self.legend[self.level])


@dataclass(frozen=True)
class NoulView:
    noul: float
    type: str = "noul"

    @property
    def yes(self) -> bool:
        return self.noul >= 0.5


AnswerView = ChoiceView | ScoreView | NoulView


def view(answer: ChoiceAnswer | ScoreAnswer | NoulAnswer) -> AnswerView:
    if isinstance(answer, ChoiceAnswer):
        return ChoiceView(answer.choice, answer.confidence, dict(answer.probabilities))
    if isinstance(answer, ScoreAnswer):
        return ScoreView(
            answer.score,
            answer.confidence,
            {int(k): v for k, v in answer.probabilities.items()},
            {int(k): str(v) for k, v in answer.legend.items()},
        )
    return NoulView(answer.noul)


def answer_to_dict(answer: AnswerView) -> dict[str, Any]:
    if isinstance(answer, ChoiceView):
        return {
            "type": "choice",
            "choice": answer.choice,
            "confidence": answer.confidence,
            "probabilities": answer.probabilities,
        }
    if isinstance(answer, ScoreView):
        return {
            "type": "score",
            "score": answer.score,
            "confidence": answer.confidence,
            "probabilities": {str(k): v for k, v in answer.probabilities.items()},
            "legend": {str(k): v for k, v in answer.legend.items()},
        }
    return {"type": "noul", "noul": answer.noul}


def answer_from_dict(data: dict[str, Any]) -> AnswerView:
    kind = data["type"]
    if kind == "choice":
        return ChoiceView(data["choice"], data["confidence"], dict(data["probabilities"]))
    if kind == "score":
        return ScoreView(
            data["score"],
            data["confidence"],
            {int(k): v for k, v in data["probabilities"].items()},
            {int(k): str(v) for k, v in data["legend"].items()},
        )
    return NoulView(data["noul"])


@dataclass(frozen=True)
class CallMeta:
    """Metadata of one API call, kept next to the answers."""

    latency_ms: float
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, response: SystemOneResponse, latency_ms: float) -> "CallMeta":
        try:
            request_id = response.request_id
        except Exception:  # header missing on some responses
            request_id = None
        return cls(
            latency_ms=round(latency_ms, 1),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            request_id=request_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CallMeta":
        return cls(
            latency_ms=data["latency_ms"],
            model=data["model"],
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            request_id=data.get("request_id"),
        )
