from __future__ import annotations

import re
from typing import Any, Optional

from coworker.sessions import SessionRecord


_LABELS = {
    "document_id": "Document ID",
    "vision_status": "Vision Status",
    "document_type": "Document Type",
    "risk_level": "Risk Level",
    "source_file": "Source File",
    "proposed_filename": "Proposed Filename",
    "proposed_folder": "Proposed Folder",
    "duplicate_check": "Duplicate Check",
    "validation": "Validation",
    "workbook_status": "Workbook Status",
    "draft_status": "Draft Status",
    "human_gate": "Human Gate",
}


def _assistant_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "assistant"
        and isinstance(message.get("content"), str)
    )


def _value(text: str, label: str, default: str = "") -> str:
    match = re.search(
        rf"^{re.escape(label)}\s*:\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE
    )
    return match.group(1).strip() if match else default


def is_physical_document_run(messages: list[dict[str, Any]]) -> bool:
    """Identify this workflow without stealing ordinary GastroWorker sessions."""
    text = "\n".join(str(message.get("content") or "") for message in messages)
    lowered = text.lower()
    return (
        "vision status:" in lowered
        or "physical-document-processing" in lowered
        or ("document id:" in lowered and "proposed filename:" in lowered)
    )


def extract_physical_document_pipeline(
    record: Optional[SessionRecord], messages: list[dict[str, Any]]
) -> dict[str, Any]:
    """Render the governed Vision-to-filing workflow from its structured review package."""
    text = _assistant_text(messages)
    data = {key: _value(text, label) for key, label in _LABELS.items()}
    has_image = any(
        isinstance(part, dict) and part.get("type") in {"image_url", "file"}
        for message in messages
        if isinstance(message.get("content"), list)
        for part in message["content"]
    )

    vision = data["vision_status"].lower()
    gate = data["human_gate"].lower()
    workbook = data["workbook_status"].lower()
    draft = data["draft_status"].lower()

    intake_status = "completed" if has_image or data["source_file"] else "pending"
    vision_status = (
        "completed"
        if vision == "complete"
        else "blocked"
        if vision in {"needs_better_image", "missing_pages", "unavailable"}
        else "running"
        if messages
        else "pending"
    )
    preparation_status = (
        "completed"
        if data["proposed_filename"] and data["proposed_folder"]
        else "pending"
    )
    gate_status = (
        "completed"
        if gate == "approved"
        else "blocked"
        if gate in {"rejected", "reprocess"}
        else "waiting_approval"
        if gate == "pending" or preparation_status == "completed"
        else "pending"
    )
    commit_status = (
        "completed"
        if workbook == "recorded" and draft in {"none", "sent"}
        else "blocked"
        if workbook == "blocked"
        else "pending"
    )

    stages = [
        {
            "stage_id": "document_intake",
            "title": "Document Intake & Quality Check",
            "status": intake_status,
            "data": {
                "document_id": data["document_id"],
                "source_file": data["source_file"],
                "has_visual_attachment": has_image,
                "duplicate_check": data["duplicate_check"],
            },
        },
        {
            "stage_id": "vision_analysis",
            "title": "Native Vision Classification & Extraction",
            "status": vision_status,
            "data": {
                "vision_status": data["vision_status"],
                "document_type": data["document_type"],
                "risk_level": data["risk_level"],
                "validation": data["validation"],
                "source_of_truth": "original visual document",
                "ocr_used_as_primary": False,
            },
        },
        {
            "stage_id": "filing_preparation",
            "title": "Filing, Workbook & Draft Preparation",
            "status": preparation_status,
            "data": {
                "proposed_filename": data["proposed_filename"],
                "proposed_folder": data["proposed_folder"],
                "workbook_status": data["workbook_status"],
                "draft_status": data["draft_status"],
            },
        },
        {
            "stage_id": "human_gate",
            "title": "Human Approval Gate",
            "status": gate_status,
            "data": {
                "decision": data["human_gate"] or "pending",
                "gate_policy": "Human approval required before filing, official workbook writes, or external sends.",
            },
        },
        {
            "stage_id": "approved_commit",
            "title": "Approved Commit & Audit Trail",
            "status": commit_status,
            "data": {
                "workbook_status": data["workbook_status"],
                "draft_status": data["draft_status"],
            },
        },
    ]

    overall = "completed" if commit_status == "completed" else gate_status
    if vision_status == "blocked" or commit_status == "blocked":
        overall = "blocked"
    return {
        "ok": True,
        "session_id": record.session_id if record else "",
        "persona_id": record.agent if record and record.agent else "gastro-worker",
        "title": record.title if record and record.title else "Physical Document Processing",
        "status": overall,
        "pipeline_type": "schema",
        "has_incident": bool(text or has_image),
        "workflow": "physical_document_processing",
        "stages": stages,
    }
