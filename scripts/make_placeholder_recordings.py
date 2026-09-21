"""Write SYNTHETIC placeholder recordings so the slides and --offline mode render
before you have recorded real API responses.

    uv run python scripts/make_placeholder_recordings.py [--force]

Every file gets `"source": "synthetic-placeholder"`; the CLI demos and the slides show a
red badge for them. They are hand-written, plausible-looking numbers and NOT Jev output.
Replace them with real data:

    uv run python demos/demo1_smart_if.py --record
    uv run python demos/demo2_confidence_gate.py --record
    uv run python demos/demo3_agent_gate.py --record
    uv run python scripts/benchmark.py --calls 10 --location "Belgium (...)"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jevdemo import agent_gate, confidence_gate, smart_if  # noqa: E402
from jevdemo.jev import CallMeta, ChoiceView, NoulView, ScoreView  # noqa: E402
from jevdemo.recording import SOURCE_PLACEHOLDER, recording_path, save_recording  # noqa: E402

MODEL = "jev-placeholder (synthetic, not a real model answer)"
LEGEND = {i: text for i, text in enumerate(smart_if.QUESTIONS["urgency"].criteria)}  # type: ignore[arg-type]


def score(probs: dict[int, float]) -> ScoreView:
    value = sum(level * p for level, p in probs.items())
    return ScoreView(round(value, 3), max(probs.values()), probs, {k: str(v) for k, v in LEGEND.items()})


def choice(probs: dict[str, float]) -> ChoiceView:
    best = max(probs, key=probs.__getitem__)
    return ChoiceView(best, probs[best], probs)


def meta(ms: float, tokens: int) -> CallMeta:
    return CallMeta(latency_ms=ms, model=MODEL, input_tokens=tokens, output_tokens=0, request_id=None)


def demo1() -> dict:
    result = smart_if.SmartIfResult(
        ticket=smart_if.TICKET,
        team=choice({"billing": 0.71, "technical": 0.26, "sales": 0.02, "other": 0.01}),
        urgency=score({0: 0.03, 1: 0.17, 2: 0.80}),
        refund=NoulView(0.93),
        meta=meta(412.0, 236),
    )
    return result.to_dict()


DEMO2_ANSWERS: dict[str, tuple[dict[str, float], dict[int, float], float]] = {
    "T-101": ({"technical": 0.95, "billing": 0.02, "sales": 0.01, "other": 0.02}, {0: 0.02, 1: 0.08, 2: 0.90}, 388),
    "T-102": ({"billing": 0.96, "technical": 0.02, "sales": 0.01, "other": 0.01}, {0: 0.20, 1: 0.65, 2: 0.15}, 401),
    "T-103": ({"sales": 0.91, "billing": 0.07, "technical": 0.01, "other": 0.01}, {0: 0.75, 1: 0.22, 2: 0.03}, 372),
    "T-104": ({"billing": 0.66, "other": 0.21, "technical": 0.12, "sales": 0.01}, {0: 0.55, 1: 0.40, 2: 0.05}, 395),
    "T-105": ({"technical": 0.52, "billing": 0.45, "sales": 0.01, "other": 0.02}, {0: 0.05, 1: 0.45, 2: 0.50}, 431),
    "T-106": ({"sales": 0.62, "technical": 0.33, "billing": 0.03, "other": 0.02}, {0: 0.70, 1: 0.27, 2: 0.03}, 379),
    "T-107": ({"technical": 0.90, "other": 0.05, "billing": 0.03, "sales": 0.02}, {0: 0.05, 1: 0.35, 2: 0.60}, 366),
    "T-108": ({"other": 0.94, "technical": 0.02, "billing": 0.02, "sales": 0.02}, {0: 0.95, 1: 0.04, 2: 0.01}, 351),
    "T-109": ({"billing": 0.49, "technical": 0.47, "sales": 0.02, "other": 0.02}, {0: 0.15, 1: 0.60, 2: 0.25}, 447),
    "T-110": ({"sales": 0.84, "billing": 0.10, "technical": 0.04, "other": 0.02}, {0: 0.65, 1: 0.30, 2: 0.05}, 402),
    "T-111": ({"other": 0.41, "technical": 0.30, "billing": 0.19, "sales": 0.10}, {0: 0.30, 1: 0.40, 2: 0.30}, 344),
}


def demo2() -> dict:
    decisions = []
    for ticket in confidence_gate.TICKETS:
        team, urgency, ms = DEMO2_ANSWERS[ticket.id]
        decisions.append(
            confidence_gate.TicketDecision(
                ticket_id=ticket.id,
                text=ticket.text,
                team=choice(team),
                urgency=score(urgency),
                meta=meta(float(ms), 90 + len(ticket.text) // 4),
            )
        )
    return confidence_gate.ConfidenceGateResult(decisions).to_dict()


def demo3() -> dict:
    calls = [
        ("run_shell", {"command": "df -h", "host": "app-01"},
         {"destructive": 0.03, "production": 0.88, "secrets": 0.04}, 402.0),
        ("run_sql", {"query": "SELECT query, mean_exec_time AS mean_ms, calls FROM pg_stat_statements "
                     "ORDER BY mean_exec_time DESC LIMIT 5", "database": "orders-production"},
         {"destructive": 0.05, "production": 0.96, "secrets": 0.06}, 437.0),
        ("run_sql", {"query": "DROP TABLE orders_archive_2023", "database": "orders-production"},
         {"destructive": 0.97, "production": 0.96, "secrets": 0.03}, 418.0),
        ("read_file", {"path": "/etc/app/secrets.env", "host": "app-01"},
         {"destructive": 0.02, "production": 0.85, "secrets": 0.94}, 395.0),
    ]
    decisions = []
    transcript = [{"role": "human", "content": agent_gate.TASK}]
    for name, args, probs, ms in calls:
        blocked, reason = agent_gate.decide(probs)
        decisions.append(agent_gate.GateDecision(name, args, probs, blocked, reason, ms))
        transcript.append({"role": "ai", "content": "", "tool_calls": [{"name": name, "args": args}]})
        if blocked:
            content = f"BLOCKED by Jev gate: {reason}. The tool was NOT executed."
        elif name == "run_shell":
            content = agent_gate.run_shell.invoke(args)
        else:
            content = agent_gate.run_sql.invoke(args)
        transcript.append({"role": "tool", "content": content, "tool": name,
                           "status": "error" if blocked else "success"})
    final = (
        "1. Disk on app-01 is at 93% (6 GB free).\n"
        "2. Slowest query: SELECT * FROM orders WHERE customer_id=? (1840 ms mean, 52k calls).\n"
        "3. Dropping orders_archive_2023 on orders-production was BLOCKED by the gate "
        "(destructive action on production).\n"
        "4. Reading /etc/app/secrets.env was BLOCKED (would expose secrets).\n"
        "Recommendation: add an index on orders(customer_id); ask a human to approve the cleanup."
    )
    transcript.append({"role": "ai", "content": final})
    result = agent_gate.AgentGateResult(
        task=agent_gate.TASK, decisions=decisions, transcript=transcript, final_answer=final,
        llm="placeholder:no-llm-was-called", total_ms=14200.0, gate_model=MODEL,
    )
    return result.to_dict()


def benchmark() -> dict:
    def stats(samples):
        from jevdemo.latency import LatencyStats
        return {"samples_ms": samples, **LatencyStats.of(samples).to_dict()}

    return {
        "location": "PLACEHOLDER - not measured. Run scripts/benchmark.py from Belgium.",
        "calls_per_demo": 10,
        "results": {
            "demo1_smart_if": stats([412, 398, 445, 380, 402, 521, 391, 410, 388, 405]),
            "demo2_confidence_gate": stats([388, 401, 372, 395, 431, 379, 366, 351, 447, 402]),
            "demo3_agent_gate": stats([402, 437, 418, 395, 460, 410, 399, 428, 405, 512]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="write synthetic placeholder recordings")
    parser.add_argument("--force", action="store_true", help="overwrite existing recordings, even real ones")
    args = parser.parse_args()
    for name, build in (
        (smart_if.RECORDING, demo1),
        (confidence_gate.RECORDING, demo2),
        (agent_gate.RECORDING, demo3),
        ("latency_benchmark", benchmark),
    ):
        path = recording_path(name)
        if path.exists() and not args.force:
            import json
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("source") != SOURCE_PLACEHOLDER:
                print(f"keep   {path} (real recording, use --force to overwrite)")
                continue
        save_recording(name, build(), source=SOURCE_PLACEHOLDER)
        print(f"wrote  {path}  [synthetic-placeholder]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
