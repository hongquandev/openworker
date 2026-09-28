from coworker.providers import ModelCapabilities, ProviderClient
from coworker.server.manager import SessionManager


class FakeProvider(ProviderClient):
    def complete(self, **kwargs):
        pass

    def capabilities(self, model):
        return ModelCapabilities()


def test_create_automation_with_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    mgr = SessionManager(workspace=tmp_path, provider=FakeProvider())
    res = mgr.create_automation(
        {
            "title": "Food Claims Check",
            "instructions": "Scan emails",
            "cron": "0 8 * * *",
            "agent": "gastro-worker",
        }
    )
    assert res["ok"] is True
    task = mgr.task_store.get(res["task"]["id"])
    assert task is not None
    assert task.agent == "gastro-worker"
    assert task.model is not None
    assert task.model == mgr.resolve_persona_model("gastro-worker")
    assert res["task"]["model"] == task.model

    # Test manual run resolves and stores the model into SessionRecord
    prep = mgr.prepare_manual_run(task.id)
    assert prep["ok"] is True
    rec = mgr.session_store.load(prep["session_id"])
    assert rec is not None
    assert rec.model == task.model

    # Test engine receives non-empty model
    engine = mgr.get_engine(prep["session_id"])
    assert engine is not None
    assert engine.model == task.model

    # Test update automation model
    up = mgr.update_automation(task.id, {"model": "openai:gpt-4o"})
    assert up["ok"] is True
    assert up["task"]["model"] == "openai:gpt-4o"
    assert mgr.task_store.get(task.id).model == "openai:gpt-4o"

