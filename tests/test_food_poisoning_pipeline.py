from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from coworker.personas.pipelines.food_poisoning import extract_food_poisoning_pipeline
from coworker.providers import AssistantTurn, ModelCapabilities, ProviderClient
from coworker.server import SessionManager, create_app
from coworker.sessions import SessionRecord


class DummyProvider(ProviderClient):
    def complete(self, *, model, messages, tools=None, **settings):
        return AssistantTurn(text="ok", finish_reason="stop")

    def capabilities(self, model):
        return ModelCapabilities()


def test_extract_food_poisoning_pipeline_basic(tmp_path: Path):
    rec = SessionRecord(
        session_id="fp-test-01",
        workspace=str(tmp_path),
        model="test-model",
        mode="interactive",
        agent="gastro-worker",
        title="Food Poisoning Triage: Case Weber",
    )
    messages = [
        {
            "role": "user",
            "content": "Process complaint in complaint_weber_20260908.txt",
        },
        {
            "role": "assistant",
            "content": (
                "Fall-ID: FP-2026-09-08-WEBER\n"
                "Betroffene Gäste: Dr. Maximilian Weber\n"
                "Verzehrte Speisen: Rindertatar mit Trüffelmayo, Frische Austern Fine de Claire\n"
                "Inkubationszeit: 4,0 Stunden\n"
                "Leitsymptome: Hohes Fieber (39,5°C), unstillbares Erbrechen\n"
                "Klassifikation: [P0-CRITICAL]\n"
                "Begründung: Stationäre Hospitalisierung / Notarzteinsatz bei 2 Gästen.\n"
                "Rückstellproben sichern und HACCP prüfen.\n"
                "Sehr geehrter Herr Dr. Weber,\n"
                "wir haben Ihre Mitteilung mit großem Bedauern zur Kenntnis genommen.\n"
                "Mit freundlichen Grüßen,\nRestaurantleitung"
            ),
        },
    ]

    pipeline = extract_food_poisoning_pipeline(rec, messages, str(tmp_path))
    assert pipeline["ok"] is True
    assert pipeline["session_id"] == "fp-test-01"
    assert len(pipeline["stages"]) == 4

    intake = pipeline["stages"][0]
    assert intake["stage_id"] == "intake"
    assert intake["status"] == "completed"
    assert intake["data"]["guest_name"] == "Dr. Maximilian Weber"
    assert "Austern" in intake["data"]["dishes"]
    assert "4,0 Stunden" in intake["data"]["incubation_time"]

    scoring = pipeline["stages"][1]
    assert scoring["stage_id"] == "severity_scoring"
    assert scoring["status"] == "completed"
    assert scoring["data"]["severity"] == "P0-CRITICAL"
    assert scoring["data"]["badge_color"] == "danger"
    assert len(scoring["data"]["kitchen_safeguards"]) > 0

    draft = pipeline["stages"][2]
    assert draft["stage_id"] == "insurance_draft"
    assert draft["status"] == "completed"
    assert "Dr. Weber" in draft["data"]["draft_body"]
    assert draft["data"]["claim_form_pdf"] in ("schadenanzeige_lebensmittelvergiftung.pdf", "incident_claim_form.pdf")

    gate = pipeline["stages"][3]
    assert gate["stage_id"] == "approval_gate"
    assert gate["status"] == "completed"


def test_session_pipeline_endpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    provider = DummyProvider()
    manager = SessionManager(workspace=tmp_path, provider=provider)

    session_id = "fp-api-test"
    manager.session_store.save(
        SessionRecord(
            session_id=session_id,
            workspace=str(tmp_path),
            model="test-model",
            mode="interactive",
            agent="gastro-worker",
            title="API Test Case",
        )
    )

    client = TestClient(create_app(manager))
    resp = client.get(f"/v1/sessions/{session_id}/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["session_id"] == session_id
    assert len(data["stages"]) == 4
