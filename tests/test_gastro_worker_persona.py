from pathlib import Path
from coworker.personas.manifest import parse_manifest
from coworker.personas.registry import PersonaRegistry
from coworker.personas.pipelines.engine import extract_pipeline
from coworker.skills import SkillLoader


def test_gastro_worker_persona_manifest_validity():
    manifest_path = Path("coworker/personas/builtin/gastro-worker/manifest.md")
    assert manifest_path.exists(), "Manifest file must exist"
    text = manifest_path.read_text(encoding="utf-8")
    m = parse_manifest(text, builtin=True, fallback_id="gastro-worker")
    assert m.id == "gastro-worker"
    assert m.name == "Gastro Worker"
    assert set(m.connectors) == {
        "gmail", "google_calendar", "slack", "google_drive", "google_sheets"
    }
    assert "food-poisoning-triage" in m.system_prompt
    assert "haccp-compliance" in m.system_prompt
    assert "physical-document-processing" in m.system_prompt
    assert "insurance" in m.system_prompt.lower()
    assert "approval gate" in m.system_prompt.lower()


def test_gastro_worker_skills_and_assets_discovered(tmp_path):
    reg = PersonaRegistry(state_path=tmp_path / "personas.json")
    persona = reg.get("gastro-worker")
    assert persona is not None, "Gastro Worker must be registered in builtin registry"
    assert persona.manifest is not None
    assert persona.manifest.source is not None
    base_dir = Path(persona.manifest.source).parent
    skills_dir = base_dir / "skills"
    assert skills_dir.is_dir()
    loader = SkillLoader([skills_dir])
    names = set(loader.names())
    assert "food-poisoning-triage" in names
    assert "haccp-compliance" in names
    assert "physical-document-processing" in names
    assert "incident-scoring" not in names
    assert "insurance-dispatch" not in names

    pdf_asset = base_dir / "assets" / "schadenanzeige_lebensmittelvergiftung.pdf"
    assert pdf_asset.is_file(), "Claim form PDF asset must exist under gastro-worker/assets"


def test_gastro_worker_pipeline_extraction():
    class MockRecord:
        agent = "gastro-worker"
        session_id = "test-session-123"
        workspace = "/tmp/mock-workspace"
        title = "Mock Task"

    messages = [
        {"role": "user", "content": "Triage this food poisoning report"},
        {"role": "assistant", "content": "Scoring incident facts", "tool_calls": [
            {"id": "c1", "function": {"name": "gmail_search_messages", "arguments": "{}"}}
        ]},
        {"role": "assistant", "content": "Drafting claim response", "tool_calls": [
            {"id": "c2", "function": {"name": "gmail_send_email", "arguments": "{\"to\": \"diner@example.com\"}"}}
        ]}
    ]

    result = extract_pipeline(MockRecord(), messages, "/tmp/mock-workspace")
    assert result.get("ok") is True
    assert result.get("persona_id") == "gastro-worker"
    stage_ids = [s["stage_id"] for s in result.get("stages", [])]
    assert "intake" in stage_ids
    assert "severity_scoring" in stage_ids
    assert "insurance_draft" in stage_ids
    assert "approval_gate" in stage_ids
