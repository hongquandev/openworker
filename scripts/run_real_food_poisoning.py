#!/usr/bin/env python3
"""Run real execution of the food-poisoning-triage automation workflow.

This script interacts with the live openworker-server:
1. Ensures an unread English food poisoning complaint email exists in Gmail.
2. Calls POST /v1/automations/task-7dc93f9b52/run to prepare the manual run session.
3. Connects to the session WebSocket (/ws/session/{session_id}) with authentication.
4. Streams the actual Agent execution turn, logging all lifecycle events in real time:
   - Assistant deltas (reasoning & text)
   - Tool proposals and executions (gmail_search_messages, gmail_get_message, load_skill)
   - Human-in-the-loop Approval Gates (permission_required on gmail_send_email)
5. Verifies that the approval item is registered in the user's Inbox (GET /v1/inbox?state=pending).
6. Waits interactively for the user to view and click 'Allow' or 'Deny' directly in the GastroWorker GUI
   (at http://127.0.0.1:5173/#/inbox), polling the state in real time.
7. Finalizes the automation run.
8. Queries the Dynamic Pipeline API (GET /v1/sessions/{session_id}/pipeline) and outputs
   the extracted stages and execution graph for documentation verification.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import websockets

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from create_food_poisoning_email import create_food_poisoning_email

API_BASE = "http://127.0.0.1:8765"
WS_BASE = "ws://127.0.0.1:8765"
GUI_BASE = "http://localhost:1420"
TASK_ID = "task-6ccf87048e"


def get_api_token() -> str:
    env_token = os.environ.get("COWORKER_API_TOKEN")
    if env_token:
        return env_token
    token_file = Path(os.path.expanduser("~/.config/coworker")) / "sidecar-8765.token"
    if token_file.exists():
        return token_file.read_text().strip()
    return ""


def http_post(endpoint: str, data: dict | None = None) -> dict:
    url = f"{API_BASE}{endpoint}"
    token = get_api_token()
    req = urllib.request.Request(
        url,
        data=json.dumps(data or {}).encode("utf-8") if data is not None else b"",
        headers={
            "x-openworker-token": token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(endpoint: str) -> dict:
    url = f"{API_BASE}{endpoint}"
    token = get_api_token()
    req = urllib.request.Request(
        url,
        headers={"x-openworker-token": token},
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_live_pipeline(auto_approve: bool = False, timeout_sec: int = 600, create_email: bool = True):
    if create_email:
        print("=====================================================================")
        print("[STEP 0] Ensuring unread incident email is ready in Gmail...")
        print("=====================================================================")
        created = create_food_poisoning_email()
        print("Draft created ID:", created.get("id"))
        print("Subject:", created.get("subject"))
        print("Recipient:", created.get("to"))

    print("\n=====================================================================")
    print("[STEP 1] Preparing Manual Automation Run via REST API")
    print("=====================================================================")
    run_prep = http_post(f"/v1/automations/{TASK_ID}/run")
    print("Run Prep Response:", json.dumps(run_prep, indent=2))
    assert run_prep.get("ok"), f"Failed to prepare run: {run_prep}"

    run_id = run_prep["run_id"]
    session_id = run_prep["session_id"]
    workspace = run_prep["workspace"]
    agent = run_prep["agent"]
    prompt = run_prep["prompt"]

    print(f"Run ID: {run_id}")
    print(f"Session ID: {session_id}")
    print(f"Agent Persona: {agent}")
    print(f"Workspace: {workspace}")

    print("\n=====================================================================")
    print("[STEP 2] Connecting to Session WebSocket & Driving Execution Turn")
    print("=====================================================================")
    token = get_api_token()
    ws_url = f"{WS_BASE}/ws/session/{session_id}?workspace={urllib.parse.quote(workspace)}&agent={urllib.parse.quote(agent)}"

    async with websockets.connect(ws_url, subprotocols=["openworker", token]) as ws:
        print("WebSocket connected successfully!")

        start_msg = {
            "type": "user_message",
            "text": prompt,
        }
        await ws.send(json.dumps(start_msg))
        print("Sent trigger prompt to coworker agent.")

        turn_completed = False
        approval_item_id = None

        while not turn_completed:
            msg_raw = await ws.recv()
            msg = json.loads(msg_raw)
            evt_type = msg.get("type")
            data = msg.get("data", {})

            if evt_type == "chunk":
                delta = data.get("delta", "")
                sys.stdout.write(delta)
                sys.stdout.flush()

            elif evt_type == "tool_start":
                name = data.get("name")
                call_id = data.get("call_id")
                args = data.get("arguments", {})
                print(f"\n\n[LOG: STEP 3 - TOOL PROPOSAL] Tool: {name} (id: {call_id})")
                print(f"Arguments: {json.dumps(args, indent=2)}")

            elif evt_type == "tool_end":
                name = data.get("name")
                status = data.get("status")
                result = data.get("result", {})
                output_preview = str(result)[:300].replace("\n", " ")
                print(f"[LOG: STEP 3 - TOOL RESULT] Tool: {name} (status: {status})")
                print(f"Preview: {output_preview}...")

            elif evt_type == "permission_required":
                print("\n=====================================================================")
                print("[LOG: STEP 4 - HUMAN-IN-THE-LOOP APPROVAL GATE (HARD FLOOR ACTIVATED)]")
                print("=====================================================================")
                req = data.get("request", {})
                tool_name = req.get("tool_name", data.get("name", "action"))
                print(f"Intercepted Action: {tool_name}")
                print(f"Security Dialect: {data.get('body', 'Supervisor sign-off required for outbound action.')}")

                # Check global Inbox via REST API
                await asyncio.sleep(1)
                inbox_data = http_get("/v1/inbox?state=pending")
                pending_items = inbox_data.get("items", [])
                print(f"\n[INBOX VERIFICATION] Total Pending Items in Inbox: {len(pending_items)}")
                target_item = None
                for it in pending_items:
                    print(f"  -> Item ID: {it.get('id')}")
                    print(f"     Title: {it.get('title')}")
                    print(f"     Kind: {it.get('kind')}")
                    print(f"     Visibility: {it.get('visibility')}")
                    print(f"     State: {it.get('state')}")
                    print(f"     Session ID: {it.get('session_id')}")
                    print(f"     Body: {it.get('body')}")
                    if it.get("session_id") == session_id:
                        target_item = it

                approval_item_id = target_item.get("id") if target_item else None

                print("\n---------------------------------------------------------------------")
                print(">>> CARD IS NOW LIVE IN YOUR OPENWORKER INBOX TAB! <<<")
                print(f"Open URL: {GUI_BASE}/#/inbox")
                print("The system is waiting for your decision on the UI screen.")
                print(f"Mode: {'AUTO-APPROVE after timeout' if auto_approve else 'INTERACTIVE (Waiting for GUI click)'}")
                print("---------------------------------------------------------------------")

                user_resolved = False
                for sec in range(timeout_sec):
                    await asyncio.sleep(2)
                    # Poll the status of the item
                    if approval_item_id:
                        all_inbox = http_get("/v1/inbox")
                        found = next((x for x in all_inbox.get("items", []) if x.get("id") == approval_item_id), None)
                        if found and found.get("state") == "resolved":
                            print(f"\n[SUCCESS] Approval item resolved via GUI! Resolution: '{found.get('resolution')}' by '{found.get('resolved_by')}'")
                            user_resolved = True
                            break

                    remaining_items = http_get("/v1/inbox?state=pending").get("items", [])
                    if not any(x.get("session_id") == session_id for x in remaining_items):
                        print(f"\n[SUCCESS] Pending item cleared from queue via GUI action!")
                        user_resolved = True
                        break

                    sys.stdout.write(f"\rWaiting for user action on GUI: {timeout_sec - (sec * 2)}s remaining... ")
                    sys.stdout.flush()

                if not user_resolved:
                    if auto_approve:
                        print("\n[AUTO-APPROVE] Timeout reached. Sending fallback approval via WebSocket...")
                        await ws.send(json.dumps({"type": "approval", "decision": "allow"}))
                        print("[WebSocket] Sent approval: 'allow'")
                    else:
                        print("\n[TIMEOUT] Reached maximum wait time without GUI action. Terminating turn.")
                        await ws.send(json.dumps({"type": "approval", "decision": "deny"}))

            elif evt_type == "turn_done":
                print("\n\n[LOG: STEP 3 - TURN DONE] Assistant turn finished successfully.")
                turn_completed = True

            elif evt_type == "error":
                print(f"\n[LOG: ERROR] Encountered error: {data}")
                turn_completed = True

    print("\n=====================================================================")
    print("[STEP 5] Finalizing Automation Run:", run_id)
    print("=====================================================================")
    finalize_res = http_post(f"/v1/automations/{TASK_ID}/runs/{run_id}/finalize")
    print("Finalize response:", finalize_res)

    print("\n=====================================================================")
    print("[STEP 6] Extracting Dynamic Pipeline via GET /v1/sessions/{session_id}/pipeline")
    print("=====================================================================")
    pipeline = http_get(f"/v1/sessions/{session_id}/pipeline")
    print(f"Pipeline Result: ok={pipeline.get('ok')}, title={pipeline.get('title')}, status={pipeline.get('status')}")
    print(f"Number of Stages: {len(pipeline.get('stages', []))}")
    print(f"Number of Trace Nodes: {len(pipeline.get('nodes', []))}")

    print("\n--- STAGES OVERVIEW ---")
    for s in pipeline.get("stages", []):
        print(f"[*] Stage [{s['stage_id']}]: {s['title']} -> {s['status']}")
        summary = s.get("data", {}).get("summary") or s.get("data", {}).get("justification") or s.get("data", {}).get("legal_standard")
        if summary:
            print(f"    Summary: {summary}")

    print("\n--- TRACE NODES OVERVIEW ---")
    for n in pipeline.get("nodes", []):
        tool = f" ({n['tool_name']})" if n.get("tool_name") else ""
        print(f"[*] Node [{n['type']}]{tool}: {n['title']} -> {n['status']}")

    print("\n=====================================================================")
    print("[COMPLETED] Real execution and trace completed successfully.")
    print("=====================================================================")


def main():
    parser = argparse.ArgumentParser(description="Live E2E Food Poisoning Triage Workflow Runner")
    parser.add_argument("--auto-approve", action="store_true", help="Auto approve if GUI action is not taken before timeout")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds to wait for GUI action (default: 600s)")
    parser.add_argument("--no-create-email", action="store_true", help="Do not create a new incident email before running")
    args = parser.parse_args()

    asyncio.run(run_live_pipeline(
        auto_approve=args.auto_approve,
        timeout_sec=args.timeout,
        create_email=not args.no_create_email,
    ))


if __name__ == "__main__":
    main()
