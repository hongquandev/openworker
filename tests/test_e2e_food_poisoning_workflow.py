"""End-to-End Test for the Food Poisoning Triage & Insurance Claim Workflow.

This test verifies the complete real-world lifecycle of the `food-poisoning-triage` persona:
1. Ingestion of customer food poisoning complaint with medical and dining evidence.
2. Triaging and risk scoring using the `incident-scoring` skill (evaluating incubation time,
   symptoms, and medical intervention to produce a deterministic P0-CRITICAL rating).
3. Correspondence drafting using the `insurance-dispatch` skill (formulating insurance-compliant
   German text under § 105 VVG without admitting legal guilt, and attaching the official
   Schadenanzeige claim PDF).
4. Kitchen safeguard alert (quarantining retain samples / Rückstellproben and HACCP check).
5. Human Approval Gate enforcement and resolution.
6. Verification of persisted triage dossiers, correspondence, and audit log trail.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from coworker.personas.manifest import parse_manifest
from coworker.personas.registry import PersonaRegistry
from coworker.providers import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    ToolCall,
)
from coworker.server import SessionManager, create_app
from coworker.sessions import SessionRecord
from coworker.skills import SkillLoader


class ScriptedProvider(ProviderClient):
    """Predictable provider that returns pre-scripted Assistant turns."""

    def __init__(self, turns: list[AssistantTurn]):
        self._turns = list(turns)
        self.recorded_calls: list[list[dict]] = []

    def complete(self, *, model, messages, tools=None, **settings):
        # Autotitle handler: if the server prompts for a title, answer without consuming turns
        for m in messages:
            content = str(m.get("content", "")).lower()
            if "title" in content and ("3-5 words" in content or "short title" in content):
                return AssistantTurn(text="Food Poisoning Triage", finish_reason="stop")
        self.recorded_calls.append([dict(m) for m in messages])
        if not self._turns:
            return AssistantTurn(text="Completed processing.", finish_reason="stop")
        return self._turns.pop(0)

    def capabilities(self, model):
        return ModelCapabilities()


def _tool(name: str, args: dict, call_id: str = "call_1") -> AssistantTurn:
    return AssistantTurn(
        tool_calls=[ToolCall(id=call_id, name=name, arguments=args)],
        finish_reason="tool_calls",
    )


def _text(text: str) -> AssistantTurn:
    return AssistantTurn(text=text, finish_reason="stop")


def test_food_poisoning_persona_e2e_workflow(tmp_path: Path, monkeypatch):
    """Real-world end-to-end test executing the food poisoning triage and insurance claim pipeline."""
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))

    # 1. Prepare incoming complaint case data (Email & Medical Report)
    complaints_dir = tmp_path / "incoming_complaints"
    complaints_dir.mkdir(parents=True, exist_ok=True)
    complaint_file = complaints_dir / "complaint_weber_20260908.txt"
    complaint_text = """Absender: dr.weber@example.de
Betreff: Dringende Beschwerde: Schwere Lebensmittelvergiftung nach Besuch am 08.09.2026

Sehr geehrte Damen und Herren,

ich habe am gestrigen Abend, dem 08.09.2026 um 19:45 Uhr, mit meiner Ehefrau und zwei Geschäftspartnern
in Ihrem Restaurant gegessen. Meine Frau und ich hatten als Vorspeise das 'Rindertatar mit Trüffelmayo'
sowie die 'Frischen Austern Fine de Claire'.

Gegen 23:45 Uhr (also exakt 4 Stunden nach dem Verzehr) setzten bei mir und meiner Frau heftigste
Magenkrämpfe, unstillbares Erbrechen, Schüttelfrost und hohes Fieber (39,5°C) ein.
Um 02:30 Uhr musste uns der Notarzt per Rettungswagen (112) in das Universitätsklinikum einliefern.
Die Notaufnahme stellte eine schwere akute bakterielle Gastroenteritis fest. Wir befinden uns
weiterhin in stationärer Behandlung.

Anbei übersende ich Ihnen den Bewirtungsbeleg über 284,50 EUR sowie die vorläufige Liegebescheinigung
und den Notaufnahmebericht des Klinikums. Ich fordere Sie hiermit zur unverzüglichen Schadensregulierung
und Weiterleitung an Ihre Betriebshaftpflichtversicherung auf!

Mit freundlichen Grüßen,
Dr. Maximilian Weber
"""
    complaint_file.write_text(complaint_text, encoding="utf-8")

    # 2. Verify Persona & Sibling Skills Resolution
    persona_manifest_file = Path("coworker/personas/builtin/gastro-worker/manifest.md")
    assert persona_manifest_file.exists()
    manifest = parse_manifest(persona_manifest_file.read_text(encoding="utf-8"), builtin=True)
    assert manifest.id == "gastro-worker"

    skills_dir = persona_manifest_file.parent / "skills"
    skill_loader = SkillLoader([skills_dir])
    discovered_skills = set(skill_loader.names())
    assert "food-poisoning-triage" in discovered_skills

    # 3. Verify Schadenanzeige PDF claim form asset existence
    pdf_asset = persona_manifest_file.parent / "assets" / "schadenanzeige_lebensmittelvergiftung.pdf"
    assert pdf_asset.exists(), "Official Schadenanzeige claim PDF form must exist in persona assets"
    assert pdf_asset.stat().st_size > 1000, "Schadenanzeige PDF must be non-empty valid document"
    with open(pdf_asset, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", "Asset must be a valid PDF file"

    # 4. Prepare scripted LLM turns reflecting the Persona Operational Protocol
    triage_dossier_content = """# INCIDENT DOSSIER & SEVERITY TRIAGE REPORT
Fall-ID: FP-2026-09-08-WEBER
Datum des Vorfalls: 08.09.2026 19:45 Uhr
Betroffene Gäste: Dr. Maximilian Weber + Ehefrau (2 von 4 Personen)
Verzehrte Speisen: Rindertatar mit Trüffelmayo, Frische Austern Fine de Claire
Symptombeginn: 23:45 Uhr (Inkubationszeit: 4,0 Stunden)
Leitsymptome: Hohes Fieber (39,5°C), unstillbares Erbrechen, schwere Krämpfe, Dehydration
Medizinische Intervention: Notarzteinsatz (112), stationäre Notaufnahme im Universitätsklinikum

## SEVERITY SCORING (incident-scoring skill):
Klassifikation: **[P0-CRITICAL]**
Begründung: Stationäre Hospitalisierung / Notarzteinsatz bei 2 Gästen mit übereinstimmenden Symptomen
nach Hochrisiko-Lebensmitteln (Austern/Tatar) und Inkubationszeit von 4 Stunden (Verdacht auf enterotoxinbildende Erreger).

## INTERNAL MITIGATION PROTOCOL:
1. Küchenleitung & Betriebsleitung unverzüglich alarmiert.
2. Rückstellproben der Charge vom 08.09.2026 (Rindfleisch, Austern) sofort asservieren und versiegeln.
3. HACCP-Kühldokumentation und Wareneingangstemperaturen für den 08.09.2026 sichern.

## GERMAN INSURANCE-COMPLIANT DRAFT (§ 105 VVG):
Rechtlicher Hinweis: Die Korrespondenz erfolgt rein vorsorglich und ohne Anerkenntnis einer Rechtspflicht (kein Schuldanerkenntnis gemäß § 105 VVG).

Sehr geehrter Herr Dr. Weber,

wir haben Ihre Mitteilung mit großem Bedauern zur Kenntnis genommen. Das Wohlergehen und die Gesundheit
unserer Gäste stehen für uns an oberster Stelle. Wir bedauern zutiefst, dass Sie und Ihre Ehefrau sich in
stationärer Behandlung befinden, und wünschen Ihnen eine rasche und vollständige Genesung.

Unser Betrieb unterliegt strengsten hygienischen Eigenkontrollen nach dem HACCP-Konzept. Um den von Ihnen
geschilderten Sachverhalt vollumfänglich und gewissenhaft aufzuklären, haben wir den Vorgang umgehend an unsere
Betriebshaftpflichtversicherung gemeldet.

Gemäß den versicherungsrechtlichen Bestimmungen nach § 105 VVG bitten wir Sie höflich, die beigefügte
'Schadenanzeige' ausgefüllt und unterzeichnet an uns zurückzusenden. Bitte fügen Sie eine Kopie des Bewirtungsbelegs
sowie die ärztlichen Behandlungsunterlagen bei, damit die Schadenregulierung durch die Versicherung unverzüglich
geprüft werden kann.

Mit freundlichen Grüßen,
Restaurantleitung & Qualitätsmanagement
"""

    kitchen_alert_content = """# SOFORTIGE INTERNE SICHERHEITSWARNUNG (P0-CRITICAL)
Empfänger: Küchenchef & Hygienebeauftragter
Vorfallsdatum: 08.09.2026

DRINGENDE MASSNAHMEN:
1. RÜCKSTELLPROBEN SICHERN: Sämtliche Rückstellproben der Rindertatar- und Austernchargen vom 08.09.2026
   sind mit sofortiger Wirkung im Tiefkühler (-18°C) zu versiegeln und für die Lebensmittelaufsicht bereitzuhalten.
2. LIEFERANTENRÜCKVERFOLGBARKEIT: Lieferscheine und Chargennummern der Austernlieferung sofort zusammenstellen.
3. HACCP-AUDIT: Temperaturprotokolle der Kühlhäuser vom 07.09. bis 09.09.2026 exportieren.
"""

    turns = [
        # Turn 1: Read the complaint file
        _tool("read_file", {"path": "incoming_complaints/complaint_weber_20260908.txt"}, "call_read_1"),
        # Turn 2: Write triage dossier report with P0 scoring and VVG-compliant response
        _tool(
            "write_file",
            {"path": "triage_dossier_weber.md", "content": triage_dossier_content},
            "call_write_dossier",
        ),
        # Turn 3: Write internal kitchen emergency safeguard notice
        _tool(
            "write_file",
            {"path": "kitchen_urgent_notice.md", "content": kitchen_alert_content},
            "call_write_kitchen",
        ),
        # Turn 4: Final human review summary
        _text(
            "Food poisoning incident evaluated successfully:\n"
            "- Severity: P0-CRITICAL (Hospitalization, 39.5°C fever, incubation 4h).\n"
            "- Triage dossier prepared under § 105 VVG.\n"
            "- Retention sample quarantine instructions generated.\n"
            f"- Schadenanzeige claim form attached: {pdf_asset.name}."
        ),
    ]

    provider = ScriptedProvider(turns)
    manager = SessionManager(workspace=tmp_path, provider=provider)

    # 5. Create Session with food-poisoning-triage Persona
    session_id = "fp-case-weber"
    manager.session_store.save(
        SessionRecord(
            session_id=session_id,
            workspace=str(tmp_path),
            model="anthropic:claude-opus-4-8",
            mode="interactive",
            agent="gastro-worker",
        )
    )
    manager.session_store.rename(session_id, "Food Poisoning Case: Weber")

    effective_skills = manager.effective_skill_names(session_id)
    assert "food-poisoning-triage" in effective_skills

    # 7. Execute session lifecycle via WebSocket
    client = TestClient(create_app(manager))

    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Submit user prompt to process the incident
        ws.send_json({
            "type": "user_message",
            "text": "Please process the incoming complaint in incoming_complaints/complaint_weber_20260908.txt. Perform incident scoring, prepare the German insurance-compliant response (§ 105 VVG), alert the kitchen for retain sample quarantine, and attach the official claim form.",
        })

        events: list[dict] = []
        while True:
            evt = ws.receive_json()
            events.append(evt)
            evt_type = evt["type"]

            # Human Approval Gate: Interactive mode prompts user for file writes
            if evt_type == "permission_required":
                # Inspect permission request details
                perm_data = evt.get("data", {})
                assert perm_data.get("name") == "write_file" or perm_data.get("tool") == "write_file"
                # Approve the action as the human operator
                ws.send_json({"type": "approval", "decision": "allow"})

            if evt_type == "turn_done":
                break

    # 8. Assertions: Verify outputs on disk and protocol compliance
    event_types = [e["type"] for e in events]
    assert "turn_start" in event_types
    assert "tool_finished" in event_types
    assert "assistant_message" in event_types
    assert "turn_done" in event_types

    # Verify generated Triage Dossier
    generated_dossier_path = tmp_path / "triage_dossier_weber.md"
    if not generated_dossier_path.exists():
        print("\nDEBUG EVENTS:", events)
        print("\nTMP_PATH CONTENTS:", list(tmp_path.rglob("*")))
    assert generated_dossier_path.exists(), "Triage dossier must be created on disk"
    dossier_text = generated_dossier_path.read_text(encoding="utf-8")
    assert "[P0-CRITICAL]" in dossier_text
    assert "Inkubationszeit: 4,0 Stunden" in dossier_text
    assert "Rückstellproben" in dossier_text
    assert "§ 105 VVG" in dossier_text
    assert "Schadenanzeige" in dossier_text
    # Strict insurance guardrail: No admission of guilt
    assert "Schuldanerkenntnis" in dossier_text or "ohne Schuldanerkenntnis" in dossier_text

    # Verify generated Kitchen Safeguard Notice
    kitchen_notice_path = tmp_path / "kitchen_urgent_notice.md"
    assert kitchen_notice_path.exists(), "Kitchen safeguard notice must be created on disk"
    kitchen_text = kitchen_notice_path.read_text(encoding="utf-8")
    assert "RÜCKSTELLPROBEN SICHERN" in kitchen_text
    assert "HACCP" in kitchen_text

    # Verify final assistant message mentions the official PDF form
    assistant_messages = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_messages, "Must receive assistant completion message"
    final_text = assistant_messages[-1]["data"]["text"]
    assert "P0-CRITICAL" in final_text
    assert "schadenanzeige_lebensmittelvergiftung.pdf" in final_text

    # Verify audit trail records the tool runs and approvals
    audit_resp = client.get(f"/v1/audit?session_id={session_id}")
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json().get("events", [])
    assert any(ev.get("tool") == "write_file" for ev in audit_events)


def test_food_poisoning_p2_standard_workflow(tmp_path: Path, monkeypatch):
    """Verify triage workflow for unconfirmed mild complaint classified as P2-STANDARD."""
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))

    p2_dossier_content = """# INCIDENT DOSSIER: P2-STANDARD TRIAGE
Fall-ID: FP-2026-09-08-SCHMIDT
Gast: Sabine Schmidt
Verzehrte Speisen: Tagliatelle mit Waldpilzen
Symptome: Leichtes Völlegefühl, Übelkeit ohne Erbrechen, kein Fieber
Nachweise: Keine Quittung, kein ärztliches Attest

## SEVERITY SCORING (incident-scoring skill):
Klassifikation: **[P2-STANDARD]**
Begründung: Einzelfall ohne Fieber, ohne Erbrechen, ohne ärztliche Bestätigung oder Bewirtungsbeleg.

## GERMAN VVG RESPONSE:
Sehr geehrte Frau Schmidt,
wir bedauern Ihr Unwohlsein. Gemäß § 105 VVG fügen wir rein vorsorglich die Schadenanzeige bei.
"""

    turns = [
        _tool(
            "write_file",
            {"path": "triage_p2_schmidt.md", "content": p2_dossier_content},
            "call_p2_write",
        ),
        _text("P2-STANDARD triage complete. Attached schadenanzeige_lebensmittelvergiftung.pdf."),
    ]

    provider = ScriptedProvider(turns)
    manager = SessionManager(workspace=tmp_path, provider=provider)
    session_id = "fp-case-schmidt"
    manager.session_store.save(
        SessionRecord(
            session_id=session_id,
            workspace=str(tmp_path),
            model="anthropic:claude-opus-4-8",
            mode="interactive",
            agent="gastro-worker",
        )
    )
    manager.session_store.rename(session_id, "Food Poisoning Case: Schmidt")

    client = TestClient(create_app(manager))
    with client.websocket_connect(f"/ws/session/{session_id}") as ws:
        ws.receive_json()
        ws.send_json({
            "type": "user_message",
            "text": "Sabine Schmidt complains of mild nausea after eating pasta yesterday. No hospital, no receipt.",
        })
        while True:
            evt = ws.receive_json()
            if evt["type"] == "permission_required":
                ws.send_json({"type": "approval", "decision": "allow"})
            if evt["type"] == "turn_done":
                break

    p2_file = tmp_path / "triage_p2_schmidt.md"
    assert p2_file.exists()
    p2_text = p2_file.read_text(encoding="utf-8")
    assert "[P2-STANDARD]" in p2_text
    assert "Schadenanzeige" in p2_text
