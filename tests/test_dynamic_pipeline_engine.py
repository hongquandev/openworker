from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from coworker.personas.pipelines.engine import extract_execution_nodes, extract_pipeline
from coworker.providers import AssistantTurn, ModelCapabilities, ProviderClient
from coworker.server import SessionManager, create_app
from coworker.sessions import SessionRecord


class DummyProvider(ProviderClient):
    def complete(self, *, model, messages, tools=None, **settings):
        return AssistantTurn(text="ok", finish_reason="stop")

    def capabilities(self, model):
        return ModelCapabilities()


def test_extract_execution_nodes_dynamic():
    messages = [
        {"role": "user", "content": "⏰ Running automation 'Nightly Code Audit' now."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {
                        "name": "files.read",
                        "arguments": '{"path": "src/main.py"}',
                    },
                },
                {
                    "id": "tc_2",
                    "function": {
                        "name": "bash",
                        "arguments": '{"command": "pytest -q"}',
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "tc_1", "content": "print('hello world')"},
        {"role": "tool", "tool_call_id": "tc_2", "content": "2 passed in 0.1s"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "tc_3",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "audit_report.md", "content": "# Audit Passed"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc_3", "content": "ok"},
        {"type": "permission_required", "tool": "write_file"},
        {"type": "approval", "decision": "allowed"},
        {"role": "assistant", "content": "Audit finished: 0 security flaws found."},
    ]

    nodes = extract_execution_nodes(messages)
    node_types = [n["type"] for n in nodes]

    # Verify all execution node types are extracted dynamically
    assert "trigger" in node_types
    assert "tool" in node_types
    assert "script" in node_types
    assert "artifact" in node_types
    assert "human_gate" in node_types
    assert "summary" in node_types

    # Verify script node details
    script_node = next(n for n in nodes if n["type"] == "script")
    assert script_node["tool_name"] == "bash"
    assert "pytest" in script_node["inputs"]["command"]
    assert script_node["outputs"] == "2 passed in 0.1s"

    # Verify artifact node details
    artifact_node = next(n for n in nodes if n["type"] == "artifact")
    assert artifact_node["file_path"] == "audit_report.md"


def test_extract_pipeline_generic_automation(tmp_path: Path):
    rec = SessionRecord(
        session_id="gen-auto-01",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        agent="code",
        title="Generic Code Automation",
    )
    messages = [
        {"role": "user", "content": "Check repository status"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "function": {"name": "read_file", "arguments": '{"path": "README.md"}'}}
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "# Project Docs"},
        {"role": "assistant", "content": "Repository status is clean."},
    ]

    res = extract_pipeline(rec, messages, str(tmp_path))
    assert res["ok"] is True
    assert res["pipeline_type"] == "dynamic"
    assert len(res["nodes"]) >= 3
    assert len(res["stages"]) >= 2


def test_dynamic_pipeline_endpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    provider = DummyProvider()
    manager = SessionManager(workspace=tmp_path, provider=provider)

    session_id = "dyn-sess-endpoint"
    manager.session_store.save(
        SessionRecord(
            session_id=session_id,
            workspace=str(tmp_path),
            model="test-model",
            mode="interactive",
            agent="code",
            title="Dynamic Session Endpoint Test",
        )
    )

    client = TestClient(create_app(manager))
    resp = client.get(f"/v1/sessions/{session_id}/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "nodes" in data
    assert "stages" in data
