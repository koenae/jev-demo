"""Exercise the demo code paths against a fake TypeSafe transport (no key, no network).

    uv run python scripts/selftest.py

This checks serialization, record/offline round-trips and the gate logic. It says
nothing about Jev's answers: the fake returns random but schema-valid probabilities.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typesafe_sdk import TypeSafeClient  # noqa: E402

from jevdemo import recording  # noqa: E402
from jevdemo.testing import fake_transport  # noqa: E402


def fake_client(*_args, **_kwargs) -> TypeSafeClient:
    return TypeSafeClient(api_key="fake", transport=fake_transport())


def main() -> int:
    from jevdemo import confidence_gate, smart_if

    with tempfile.TemporaryDirectory() as tmp:
        with (
            mock.patch.object(recording, "RECORDINGS_DIR", Path(tmp)),
            mock.patch.object(smart_if, "make_client", fake_client),
            mock.patch.object(confidence_gate, "make_client", fake_client),
        ):
            live = smart_if.run_smart_if("record")
            replay = smart_if.run_smart_if("offline")
            assert replay.team == live.team and replay.origin == "recording", "demo1 round-trip"
            assert live.urgency.level in live.urgency.legend
            print(f"demo1 ok  team={live.team.choice} latency={live.meta.latency_ms} ms")

            gate_live = confidence_gate.run_confidence_gate("record")
            gate_replay = confidence_gate.run_confidence_gate("offline")
            assert len(gate_live.decisions) == len(confidence_gate.TICKETS)
            assert gate_replay.decisions == gate_live.decisions, "demo2 round-trip"
            summary = confidence_gate.gate(gate_live.decisions, 0.75)
            assert summary.auto_count + summary.escalated_count == len(gate_live.decisions)
            print(f"demo2 ok  auto={summary.auto_pct:.0f}% total={summary.total_ms:.0f} ms")

            from jevdemo import agent_gate

            probs = {"destructive": 0.9, "production": 0.8, "secrets": 0.1}
            assert agent_gate.decide(probs)[0] is True
            probs = {"destructive": 0.9, "production": 0.1, "secrets": 0.1}
            assert agent_gate.decide(probs)[0] is False
            probs = {"destructive": 0.1, "production": 0.1, "secrets": 0.7}
            assert agent_gate.decide(probs)[0] is True
            print("demo3 ok  gate policy")

            import httpx2
            from langchain_core.messages import HumanMessage
            from langchain_typesafe import TypeSafeClassifier

            from jevdemo.testing import FakeToolCallingLLM

            classifier = TypeSafeClassifier(
                api_key="fake", client=httpx2.Client(transport=fake_transport(1))
            )
            gate = agent_gate.JevToolGate(classifier)
            llm = FakeToolCallingLLM.build(
                [
                    {"name": "run_shell", "args": {"command": "df -h", "host": "app-01"}},
                    {"name": "run_sql", "args": {"query": "DROP TABLE orders_archive_2023",
                                                 "database": "orders-production"}},
                    {"name": "read_file", "args": {"path": "/etc/app/secrets.env", "host": "app-01"}},
                ]
            )
            state = agent_gate.build_agent(gate, llm).invoke({"messages": [HumanMessage("go")]})
            assert len(gate.decisions) == 3, gate.decisions
            tool_msgs = [m for m in state["messages"] if m.type == "tool"]
            assert len(tool_msgs) == 3
            for d, m in zip(gate.decisions, tool_msgs):
                assert d.blocked == (m.status == "error"), (d, m)
            result = agent_gate.AgentGateResult(
                task="go", decisions=gate.decisions, transcript=agent_gate._transcript(state["messages"]),
                final_answer=agent_gate._text(state["messages"][-1]), llm="fake", total_ms=1.0,
            )
            recording.save_recording(agent_gate.RECORDING, result.to_dict())
            replay = agent_gate.run_agent_gate("offline")
            assert replay.decisions == gate.decisions and replay.final_answer == "Report: done."
            print(f"demo3 ok  middleware ran, blocked={len(replay.blocked)}/3 (random fake probabilities)")
    print("selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
