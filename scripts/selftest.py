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
            tool_msgs = {m.name: m for m in state["messages"] if m.type == "tool"}
            assert len(tool_msgs) == 3
            for d in gate.decisions:  # tool calls run in parallel: match by name, not order
                assert d.blocked == (tool_msgs[d.tool].status == "error"), (d, tool_msgs[d.tool])
            ordered = agent_gate.in_call_order(gate.decisions, state["messages"])
            assert [d.tool for d in ordered] == ["run_shell", "run_sql", "read_file"], ordered
            result = agent_gate.AgentGateResult(
                task="go", decisions=ordered, transcript=agent_gate._transcript(state["messages"]),
                final_answer=agent_gate._text(state["messages"][-1]), llm="fake", total_ms=1.0,
            )
            recording.save_recording(agent_gate.RECORDING, result.to_dict())
            replay = agent_gate.run_agent_gate("offline")
            assert replay.decisions == ordered and replay.final_answer == "Report: done."
            print(f"demo3 ok  middleware ran, blocked={len(replay.blocked)}/3 (random fake probabilities)")
            from jevdemo import head_to_head as h

            def fake_llm_answer(llm, prompt, state, schema):
                if schema is h.TriageAnswer:
                    return {"team": "billing", "urgency": 1, "refund": False}, 1500.0, 300, 120
                return {"destructive": True, "production": True, "secrets": False}, 1200.0, 250, 60

            with (
                mock.patch.object(h, "make_client", fake_client),
                mock.patch.object(h, "llm_answer", fake_llm_answer),
                mock.patch.object(h, "llm_settings", lambda: type("S", (), {"label": "fake"})()),
                mock.patch.object(h, "build_chat_model", lambda s: object()),
            ):
                h2h = h.run_head_to_head("record", workers=2)
                assert len(h2h.samples) == 2 * (len(h.TRIAGE_ITEMS) + len(h.GATE_ITEMS))
                summary = h.summarize(h2h)
                assert set(summary) == {("triage", "jev"), ("triage", "llm"), ("gate", "jev"), ("gate", "llm")}
                lat, cost = h.speedup(summary, "triage")
                assert lat and lat > 1 and cost is None  # no LLM prices configured
                agree = h.agreement(h2h, "gate")
                assert set(agree) == {"destructive", "production", "secrets"}
                replay = h.run_head_to_head("offline")
                assert replay.samples == h2h.samples
                print(f"demo4 ok  {len(h2h.samples)} samples, triage speedup x{lat:.1f} (fake numbers)")
            # demo 5 + gate comparison, with the LLM judge faked
            from jevdemo import llm_judge
            from jevdemo import one_call_vs_samples as m5

            def fake_team_answer(llm, prompt, state, schema):
                return {"team": "billing", "confidence": 0.9}, 1500.0, 200, 30

            with (
                mock.patch.object(m5, "make_client", fake_client),
                mock.patch.object(m5, "llm_answer", fake_team_answer),
                mock.patch.object(m5, "llm_settings", lambda: type("S", (), {"label": "fake"})()),
                mock.patch.object(m5, "build_chat_model", lambda s: object()),
            ):
                r5 = m5.run_one_call_vs_samples("record", samples=5, jev_repeats=2, workers=2)
                assert len(r5.tickets) == 2 and len(r5.tickets[0].llm_samples) == 5
                assert r5.tickets[0].llm_majority == "billing" and r5.tickets[0].llm_agreement == 1.0
                assert abs(sum(r5.tickets[0].jev.probabilities.values()) - 1) < 0.01
                assert m5.run_one_call_vs_samples("offline").tickets[1].text == r5.tickets[1].text
                print(f"demo5 ok  spread over jev repeats {r5.tickets[0].jev_spread:.3f} (fake)")

            def fake_gate_answer(llm, prompt, state, schema):
                q = str(state["tool_call"]["args"]).lower()
                return {"destructive": "drop" in q, "production": "production" in q, "secrets": "secrets" in q}, 900.0, 250, 40

            calls = [
                {"name": "run_shell", "args": {"command": "df -h", "host": "app-01"}},
                {"name": "run_sql", "args": {"query": "DROP TABLE orders_archive_2023", "database": "orders-production"}},
                {"name": "read_file", "args": {"path": "/etc/app/secrets.env", "host": "app-01"}},
            ]
            with (
                mock.patch.object(llm_judge, "llm_answer", fake_gate_answer),
                mock.patch.object(agent_gate, "llm_settings", lambda: type("S", (), {"label": "fake"})()),
                mock.patch.object(agent_gate, "build_chat_model", lambda s: FakeToolCallingLLM.build(calls)),
                mock.patch.object(agent_gate, "typesafe_api_key", lambda: "fake"),
                mock.patch.object(agent_gate, "TypeSafeClassifier",
                                  lambda **kw: TypeSafeClassifier(api_key="fake", client=httpx2.Client(transport=fake_transport(2)))),
            ):
                cmp_ = agent_gate.run_gate_comparison("record", runs=2)
                rows = {r.gate: r for r in agent_gate.compare(cmp_)}
                assert set(rows) == {"none", "llm", "jev"} and rows["jev"].runs == 2
                assert rows["none"].blocked == 0 and rows["none"].tool_calls == 3
                assert rows["llm"].blocked == 2, rows["llm"]          # DROP on production + secrets
                assert rows["llm"].gate_ms == 3 * 900.0 and rows["llm"].gate_ms_per_call == 900.0
                assert cmp_.runs["jev"][0].gate_input_tokens > 0, "Jev gate must count its tokens"
                assert rows["llm"].agent_ms == rows["llm"].total_ms - rows["llm"].gate_ms
                replay = agent_gate.run_gate_comparison("offline")
                assert replay.runs["llm"][0].decisions == cmp_.runs["llm"][0].decisions
                assert agent_gate.run_agent_gate("offline", gate="jev").gate == "jev"
                print(f"gate comparison ok  llm gate blocked {rows['llm'].blocked}/3, jev gate blocked {rows['jev'].blocked}/3 (random fake)")
    print("selftest passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
