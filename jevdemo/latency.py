"""Small latency helpers shared by demos, benchmark and preflight."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from time import perf_counter
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def timed(fn: Callable[[], T]) -> tuple[T, float]:
    """Run `fn` and return `(result, elapsed_ms)`."""
    started = perf_counter()
    result = fn()
    return result, (perf_counter() - started) * 1000.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low, high = int(rank), min(int(rank) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


@dataclass(frozen=True)
class LatencyStats:
    n: int
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float

    @classmethod
    def of(cls, values: list[float]) -> "LatencyStats":
        return cls(
            n=len(values),
            median_ms=round(median(values), 1),
            p95_ms=round(percentile(values, 0.95), 1),
            min_ms=round(min(values), 1),
            max_ms=round(max(values), 1),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
