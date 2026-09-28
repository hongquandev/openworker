from pathlib import Path

from coworker.personas.pipelines.engine import extract_pipeline
from coworker.personas.pipelines.physical_documents import (
    extract_physical_document_pipeline,
    is_physical_document_run,
)
from coworker.sessions import SessionRecord


def _record(tmp_path: Path) -> SessionRecord:
    return SessionRecord(
        session_id="doc-vision-01",
        workspace=str(tmp_path),
        model="vision-model",
        mode="interactive",
        agent="gastro-worker",
        title="Process invoice 101",
    )


def _messages() -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Process this invoice"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,ZmFrZQ=="},
                },
            ],
        },
        {
            "role": "assistant",
            "content": (
                "Document ID: DOC-2026-000101\n"
                "Vision Status: complete\n"
                "Document Type: sales_invoice\n"
                "Risk Level: standard\n"
                "Source File: IMG_0101.jpg\n"
                "Proposed Filename: 2026-09-20_SalesInvoice_Acme_INV-101_1080USD.jpg\n"
                "Proposed Folder: /2026/Sales/Invoices/\n"
                "Duplicate Check: clear\n"
                "Validation: subtotal + tax equals total\n"
                "Workbook Status: proposed\n"
                "Draft Status: prepared\n"
                "Human Gate: pending\n"
            ),
        },
    ]


def test_physical_document_skill_is_packaged():
    skill = Path(
        "coworker/personas/builtin/gastro-worker/skills/physical-document-processing/SKILL.md"
    )
    text = skill.read_text(encoding="utf-8")
    assert "native model vision" in text.lower()
    assert "do not run ocr" in text.lower()
    assert "Human Approval Gate" in text


def test_extract_physical_document_pipeline_waits_for_human(tmp_path: Path):
    messages = _messages()
    assert is_physical_document_run(messages) is True
    result = extract_physical_document_pipeline(_record(tmp_path), messages)
    assert result["workflow"] == "physical_document_processing"
    assert result["status"] == "waiting_approval"
    assert [stage["stage_id"] for stage in result["stages"]] == [
        "document_intake",
        "vision_analysis",
        "filing_preparation",
        "human_gate",
        "approved_commit",
    ]
    vision = result["stages"][1]
    assert vision["status"] == "completed"
    assert vision["data"]["ocr_used_as_primary"] is False
    assert result["stages"][3]["status"] == "waiting_approval"


def test_gastro_worker_routes_document_run_to_document_pipeline(tmp_path: Path):
    result = extract_pipeline(_record(tmp_path), _messages(), str(tmp_path))
    assert result["workflow"] == "physical_document_processing"
    assert result["nodes"]


def test_unavailable_vision_blocks_without_ocr_fallback(tmp_path: Path):
    messages = [
        {"role": "user", "content": "Run physical-document-processing"},
        {
            "role": "assistant",
            "content": (
                "Document ID: DOC-2026-000102\n"
                "Vision Status: unavailable\n"
                "Document Type: unknown\n"
                "Human Gate: reprocess\n"
            ),
        },
    ]
    result = extract_physical_document_pipeline(_record(tmp_path), messages)
    assert result["status"] == "blocked"
    assert result["stages"][1]["data"]["ocr_used_as_primary"] is False
