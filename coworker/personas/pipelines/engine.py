from __future__ import annotations

import json
from typing import Any, Optional

from coworker.personas.registry import PersonaRegistry
from coworker.sessions import SessionRecord


def _human_tool_title(name: str, args: dict[str, Any]) -> str:
    """Generate a clean human-readable title for a tool call."""
    if name in ("read_file", "files.read"):
        p = args.get("path") or args.get("file_path") or "file"
        return f"Read File: {p}"
    if name in ("write_file", "files.write"):
        p = args.get("path") or args.get("file_path") or "file"
        return f"Write File: {p}"
    if name == "gmail.list_messages":
        q = args.get("query")
        return f"Search Gmail: {q}" if q else "Scan Gmail Messages"
    if name == "gmail.get_message":
        mid = args.get("message_id") or args.get("id") or ""
        return f"Fetch Email: {mid}" if mid else "Fetch Email"
    if name in ("bash", "shell", "run_command"):
        cmd = args.get("command") or args.get("CommandLine") or ""
        cmd_preview = (cmd[:30] + "...") if len(cmd) > 30 else cmd
        return f"Execute Script: {cmd_preview}" if cmd_preview else "Execute Script"
    return f"Execute Tool: {name}"


def extract_execution_nodes(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract granular execution nodes (Tools, Scripts, Gates, Artifacts, Summary) from messages."""
    nodes: list[dict[str, Any]] = []
    node_idx = 1

    # Map tool_call_id to tool output message
    tool_results: dict[str, Any] = {}
    for msg in messages:
        if msg.get("role") in ("tool", "function"):
            t_id = msg.get("tool_call_id") or msg.get("name") or ""
            content = msg.get("content")
            if t_id:
                tool_results[t_id] = content

    first_user_seen = False
    last_assistant_text = ""

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""

        # 1. Trigger Node from first user message
        if role == "user" and not first_user_seen:
            first_user_seen = True
            prompt_preview = content if isinstance(content, str) else str(content)
            is_cron = "Running automation" in prompt_preview or "alarm" in prompt_preview.lower()
            nodes.append({
                "node_id": f"node_{node_idx}",
                "type": "trigger",
                "title": "Automation Scheduled Trigger" if is_cron else "Trigger: User Prompt",
                "status": "completed",
                "inputs": {"prompt": prompt_preview.strip()},
                "outputs": {"trigger_type": "cron" if is_cron else "manual"},
                "description": "Triggered execution lifecycle",
            })
            node_idx += 1

        # 2. Tool / Script Nodes
        tool_calls = msg.get("tool_calls") or []
        for tc in tool_calls:
            tc_id = tc.get("id") or ""
            func = tc.get("function") or {}
            fn_name = func.get("name") or tc.get("name") or ""
            raw_args = func.get("arguments") or tc.get("arguments") or {}
            parsed_args: dict[str, Any] = {}
            if isinstance(raw_args, dict):
                parsed_args = raw_args
            elif isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = {"raw": raw_args}

            is_script = fn_name in ("bash", "shell", "run_command", "python")
            raw_output = tool_results.get(tc_id, "")
            parsed_output: Any = raw_output
            if isinstance(raw_output, str) and raw_output.startswith("{"):
                try:
                    parsed_output = json.loads(raw_output)
                except Exception:
                    pass

            node_title = _human_tool_title(fn_name, parsed_args)
            nodes.append({
                "node_id": f"node_{node_idx}",
                "type": "script" if is_script else "tool",
                "tool_name": fn_name,
                "title": node_title,
                "status": "completed",
                "inputs": parsed_args,
                "outputs": parsed_output if parsed_output else "Execution succeeded without error",
                "description": f"Invoked capability {fn_name}",
            })
            node_idx += 1

            # If write_file, also generate an Artifact Node
            if fn_name in ("write_file", "files.write"):
                p = parsed_args.get("path") or parsed_args.get("file_path") or "output"
                nodes.append({
                    "node_id": f"node_{node_idx}",
                    "type": "artifact",
                    "title": f"Artifact: {p}",
                    "file_path": str(p),
                    "status": "completed",
                    "inputs": {"path": str(p)},
                    "outputs": {"persisted": True},
                    "description": f"Generated deliverable file: {p}",
                })
                node_idx += 1

        # 3. Human Approval Gate Node
        if msg.get("type") in ("permission_required", "approval") or msg.get("status") == "permission_required":
            decision = msg.get("decision") or ("allow" if msg.get("type") == "approval" else "waiting")
            gate_status = "completed" if decision in ("allow", "allowed", "approved") else "waiting_approval"
            nodes.append({
                "node_id": f"node_{node_idx}",
                "type": "human_gate",
                "title": "Human-in-the-Loop Approval Gate",
                "status": gate_status,
                "inputs": {"policy": "Hard Floor: Requires human sign-off before dispatch"},
                "outputs": {"decision": decision},
                "description": "Enforced supervisor verification checkpoint",
            })
            node_idx += 1

        # Track last assistant answer
        if role == "assistant" and isinstance(content, str) and content.strip():
            last_assistant_text = content.strip()

    # 4. Summary / Outcome Node
    if last_assistant_text:
        nodes.append({
            "node_id": f"node_{node_idx}",
            "type": "summary",
            "title": "Execution Summary",
            "status": "completed",
            "inputs": {},
            "outputs": {"summary": last_assistant_text},
            "description": "Final response produced by the coworker",
        })

    return nodes


def extract_pipeline(
    record: Optional[SessionRecord],
    messages: list[dict[str, Any]],
    workspace_path: Optional[str] = None,
    manager: Optional[Any] = None,
) -> dict[str, Any]:
    """Dynamic Pipeline Extractor: Supports both Declarative Schema and Trace-driven Graph."""
    persona_id = record.agent if record else "gastro-worker"
    ws = workspace_path or (record.workspace if record else "")

    # Extract all granular execution nodes
    nodes = extract_execution_nodes(messages)

    # Check if Persona has declarative pipeline in Manifest
    pipeline_schema: Optional[dict[str, Any]] = None
    try:
        reg = PersonaRegistry.builtin()
        persona = reg.get(persona_id)
        if persona and persona.pipeline:
            pipeline_schema = persona.pipeline
    except Exception:
        pass

    # Special handling or schema-based mapping
    if persona_id == "gastro-worker":
        from coworker.personas.pipelines.physical_documents import (
            extract_physical_document_pipeline,
            is_physical_document_run,
        )

        if is_physical_document_run(messages):
            document_data = extract_physical_document_pipeline(record, messages)
            document_data["nodes"] = nodes
            return document_data

    if persona_id in ("food-poisoning-triage", "gastro-worker"):
        from coworker.personas.pipelines.food_poisoning import extract_food_poisoning_pipeline
        fp_data = extract_food_poisoning_pipeline(record, messages, ws)
        fp_data["nodes"] = nodes
        fp_data["pipeline_type"] = "schema"
        return fp_data

    # If declarative schema exists for other personas
    if pipeline_schema and "stages" in pipeline_schema:
        declared_stages = pipeline_schema["stages"]
        mapped_stages: list[dict[str, Any]] = []

        for st in declared_stages:
            st_id = st.get("id", "stage")
            st_title = st.get("title", st_id)
            match_tools = set(st.get("match_tools", []))
            match_events = set(st.get("match_events", []))

            stage_nodes = [
                n for n in nodes
                if (n.get("tool_name") in match_tools)
                or (n.get("type") in match_events)
            ]

            stage_status = "completed" if stage_nodes else "pending"
            if any(n.get("status") == "waiting_approval" for n in stage_nodes):
                stage_status = "waiting_approval"

            mapped_stages.append({
                "stage_id": st_id,
                "title": st_title,
                "status": stage_status,
                "description": st.get("description", ""),
                "nodes": stage_nodes,
                "data": {
                    "node_count": len(stage_nodes),
                    "summary": f"{len(stage_nodes)} actions recorded in this stage",
                },
            })

        overall_status = "completed"
        if any(s["status"] == "waiting_approval" for s in mapped_stages):
            overall_status = "waiting_approval"
        elif any(s["status"] == "running" for s in mapped_stages):
            overall_status = "running"

        return {
            "ok": True,
            "session_id": record.session_id if record else "",
            "persona_id": persona_id,
            "title": (record.title if record and record.title else f"Workflow: {persona_id}"),
            "status": overall_status,
            "pipeline_type": "schema",
            "has_incident": True,
            "stages": mapped_stages,
            "nodes": nodes,
        }

    # Trace-driven Dynamic Fallback (Universal Pipeline Graph)
    auto_stages: list[dict[str, Any]] = []
    
    # Stage 1: Trigger & Ingestion
    input_nodes = [n for n in nodes if n["type"] in ("trigger", "tool") and ("read" in n.get("tool_name", "").lower() or "list" in n.get("tool_name", "").lower() or n["type"] == "trigger")]
    auto_stages.append({
        "stage_id": "ingestion",
        "title": "Trigger & Data Ingestion",
        "status": "completed" if input_nodes else "pending",
        "data": {
            "node_count": len(input_nodes),
            "summary": f"{len(input_nodes)} ingestion steps executed",
        },
    })

    # Stage 2: Processing & Scripts
    processing_nodes = [n for n in nodes if n["type"] == "script" or (n["type"] == "tool" and n not in input_nodes)]
    auto_stages.append({
        "stage_id": "processing",
        "title": "Action & Script Execution",
        "status": "completed" if processing_nodes else ("completed" if nodes else "pending"),
        "data": {
            "node_count": len(processing_nodes),
            "summary": f"{len(processing_nodes)} operations executed",
        },
    })

    # Stage 3: Verification & Governance
    gate_nodes = [n for n in nodes if n["type"] == "human_gate"]
    gate_status = "completed"
    if any(n["status"] == "waiting_approval" for n in gate_nodes):
        gate_status = "waiting_approval"
    auto_stages.append({
        "stage_id": "governance",
        "title": "Human Governance & Output",
        "status": gate_status,
        "data": {
            "gate_count": len(gate_nodes),
            "summary": "Human approval gate checked" if gate_nodes else "Automated execution completed safely",
        },
    })

    return {
        "ok": True,
        "session_id": record.session_id if record else "",
        "persona_id": persona_id,
        "title": (record.title if record and record.title else f"Automation: {persona_id}"),
        "status": "waiting_approval" if gate_status == "waiting_approval" else "completed",
        "pipeline_type": "dynamic",
        "has_incident": bool(nodes),
        "stages": auto_stages,
        "nodes": nodes,
    }
