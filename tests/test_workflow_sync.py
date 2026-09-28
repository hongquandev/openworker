from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from coworker.personas.registry import PersonaRegistry
from coworker.skills.store import SkillStore
from coworker.server import create_app, SessionManager
from coworker.providers import ModelCapabilities, ProviderClient


class DummyProvider(ProviderClient):
    def complete(self, **kwargs):
        pass

    def capabilities(self, model):
        return ModelCapabilities()


def test_sync_workflows_from_dir(tmp_path):
    # Setup source directory representing a workflow repo
    src_dir = tmp_path / "repo"
    src_dir.mkdir()
    
    # 1. Add a persona
    personas_dir = src_dir / "personas" / "custom-helper"
    personas_dir.mkdir(parents=True)
    (personas_dir / "manifest.md").write_text(
        """---
id: custom-helper
name: Custom Helper
icon: bot
version: "1.0.0"
tools: [files]
---
You are a custom helper.
""",
        encoding="utf-8",
    )
    
    # 2. Add a skill
    skills_dir = src_dir / "skills" / "code-analyzer"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        """---
name: code-analyzer
description: Analyze code style
---
Follow clean architecture principles.
""",
        encoding="utf-8",
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    reg = PersonaRegistry(state_path=state_dir / "personas.json")
    skill_store = SkillStore(global_dir=state_dir / "skills")

    # Initial sync
    res = reg.sync_workflows(str(src_dir), skill_store=skill_store)
    assert res["ok"] is True
    assert len(res["added"]) == 1
    assert res["added"][0]["id"] == "custom-helper"
    assert "code-analyzer" in res["synced_skills"]
    assert reg.get("custom-helper") is not None

    # Sync again without change -> unchanged
    res2 = reg.sync_workflows(str(src_dir), skill_store=skill_store)
    assert res2["ok"] is True
    assert len(res2["unchanged"]) == 1
    assert res2["unchanged"][0]["id"] == "custom-helper"

    # Bump version -> updated
    (personas_dir / "manifest.md").write_text(
        """---
id: custom-helper
name: Custom Helper
icon: bot
version: "1.1.0"
tools: [files]
---
You are an updated custom helper.
""",
        encoding="utf-8",
    )
    res3 = reg.sync_workflows(str(src_dir), skill_store=skill_store)
    assert res3["ok"] is True
    assert len(res3["updated"]) == 1
    assert res3["updated"][0]["version"] == "1.1.0"


def test_sync_workflows_api_endpoint(tmp_path, monkeypatch):
    src_dir = tmp_path / "repo"
    src_dir.mkdir()
    personas_dir = src_dir / "personas" / "team-bot"
    personas_dir.mkdir(parents=True)
    (personas_dir / "manifest.md").write_text(
        """---
id: team-bot
name: Team Bot
icon: users
version: "1.0.0"
tools: [files]
---
Team Bot instructions.
""",
        encoding="utf-8",
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setenv("COWORKER_STATE_DIR", str(state_dir))

    mgr = SessionManager(workspace=tmp_path, provider=DummyProvider())
    app = create_app(mgr)
    client = TestClient(app)

    resp = client.post("/v1/workflows/sync", json={"source_url": str(src_dir)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert any(p["id"] == "team-bot" for p in data["added"])
