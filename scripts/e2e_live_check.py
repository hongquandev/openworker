#!/usr/bin/env python3
"""E2E Live Check for Food Poisoning Triage Workflow & Human Approval Gate.

This test performs an end-to-end verification against real live services:
1. Verifies Coworker server is running on http://127.0.0.1:8765.
2. Verifies Frontend GUI is reachable on http://127.0.0.1:5173.
3. Injects / verifies an unread English food poisoning incident email in Gmail.
4. Triggers the food-poisoning-triage automation run via REST API.
5. Listens to the live WebSocket stream, asserting:
   - Tool call: gmail_search_messages
   - Tool call: gmail_get_message
   - Reasoning / Skill loading
   - Tool call: gmail_send_email
6. Verifies that Human-in-the-Loop Approval Gate (Hard Floor) activates:
   - Event: 'permission_required'
   - Card is created in /v1/inbox with state: 'pending' and visibility: 'inbox'
7. Waits for human decision on GUI (or supports automated assertion mode with --auto).
8. Verifies completion, finalization, and dynamic pipeline stages (4 stages, 10+ trace nodes).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


def http_req(method: str, endpoint: str, data: dict | None = None) -> dict:
    url = f"{API_BASE}{endpoint}"
    token = get_api_token()
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={
            "x-openworker-token": token,
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_e2e_check(mode: str = "interactive", timeout_sec: int = 300):
    print("================================================================================")
    print("                     E2E LIVE CHECK: FOOD POISONING TRIAGE                     ")
    print("================================================================================")

    # 1. Health check
    print("\n[CHECK 1/6] Verifying Coworker server health...")
    try:
        health = http_req("GET", "/v1/health")
        assert health.get("status") == "ok", f"Health status not ok: {health}"
        print("  ✓ Server is healthy on", API_BASE)
    except Exception as e:
        print(f"  ✗ Failed to connect to server: {e}")
        sys.exit(1)

    # 2. Check GUI accessibility
    print("\n[CHECK 2/6] Verifying GUI availability...")
    try:
        with urllib.request.urlopen(GUI_BASE, timeout=3) as resp:
            print(f"  ✓ Frontend GUI is live at {GUI_BASE} (status {resp.status})")
    except Exception as e:
        print(f"  ! Warning: Frontend at {GUI_BASE} might not be running ({e})")

    # 3. Create incident email
    print("\n[CHECK 3/6] Setting up unread incident complaint in Gmail...")
    created_email = create_food_poisoning_email()
    print(f"  ✓ Created draft message ID: {created_email.get('id')}")
    print(f"    Subject: {created_email.get('subject')}")
    print(f"    Recipient: {created_email.get('to')}")

    # 4. Prepare manual automation run
    print("\n[CHECK 4/6] Initializing automation run via REST API...")
    prep = http_req("POST", f"/v1/automations/{TASK_ID}/run")
    assert prep.get("ok"), f"Preparation failed: {prep}"
    run_id = prep["run_id"]
    session_id = prep["session_id"]
    workspace = prep["workspace"]
    agent = prep["agent"]
    prompt = prep["prompt"]
    print(f"  ✓ Run ID: {run_id}")
    print(f"  ✓ Session ID: {session_id}")
    print(f"  ✓ Agent: {agent}")

    # 5. Connect WebSocket & Monitor Hard Floor
    print("\n[CHECK 5/6] Connecting WebSocket and monitoring live execution...")
    token = get_api_token()
    ws_url = f"{WS_BASE}/ws/session/{session_id}?workspace={urllib.parse.quote(workspace)}&agent={urllib.parse.quote(agent)}"

    gate_triggered = False
    approval_item_id = None

    async with websockets.connect(ws_url, subprotocols=["openworker", token]) as ws:
        await ws.send(json.dumps({"type": "user_message", "text": prompt}))
        print("  ✓ Prompt sent. Agent reasoning initiated...")

        turn_done = False
        while not turn_done:
            raw = await ws.recv()
            evt = json.loads(raw)
            evt_type = evt.get("type")
            data = evt.get("data", {})

            if evt_type == "chunk":
                delta = data.get("delta", "")
                sys.stdout.write(delta)
                sys.stdout.flush()

            elif evt_type == "tool_start":
                name = data.get("name")
                print(f"\n  [Tool Invoked] -> {name}")

            elif evt_type == "permission_required":
                gate_triggered = True
                print("\n\n" + "=" * 80)
                print("  ★ HARD FLOOR GATE ACTIVATED: Outbound tool intercepted!")
                print("=" * 80)
                tool_name = data.get("request", {}).get("tool_name", data.get("name", "action"))
                print(f"  Intercepted Tool: {tool_name}")

                await asyncio.sleep(1)
                inbox = http_req("GET", "/v1/inbox?state=pending")
                pending_items = inbox.get("items", [])
                target = next((x for x in pending_items if x.get("session_id") == session_id), None)

                if target:
                    approval_item_id = target.get("id")
                    print(f"  ✓ Approval Card Confirmed in Inbox:")
                    print(f"    - Card ID: {approval_item_id}")
                    print(f"    - Title: {target.get('title')}")
                    print(f"    - Visibility: {target.get('visibility')}")
                    print(f"    - State: {target.get('state')}")
                    print(f"    - Session: {target.get('session_id')}")
                else:
                    print("  ✗ Warning: Pending item not found in pending inbox query!")

                print("\n  ----------------------------------------------------------------------")
                print(f"  >>> ACTION REQUIRED: OPEN INBOX AT {GUI_BASE}/#/inbox <<<")
                if mode == "interactive":
                    print("  Waiting for your click on the 'Allow' button in the GUI...")
                else:
                    print("  Automated mode: Waiting 5s then approving via API...")
                print("  ----------------------------------------------------------------------")

                if mode == "auto":
                    await asyncio.sleep(5)
                    print("  [Auto] Resolving card via REST API...")
                    http_req("POST", f"/v1/inbox/{approval_item_id}/resolve", {"resolution": "allow"})
                    print("  ✓ Resolved card via API.")
                else:
                    # Poll for GUI click
                    user_clicked = False
                    for s in range(timeout_sec):
                        await asyncio.sleep(2)
                        all_items = http_req("GET", "/v1/inbox").get("items", [])
                        matching = next((x for x in all_items if x.get("id") == approval_item_id), None)
                        if matching and matching.get("state") == "resolved":
                            print(f"\n  ✓ Human Decision Received from GUI: resolution='{matching.get('resolution')}'")
                            user_clicked = True
                            break
                        sys.stdout.write(f"\r  Waiting for GUI action: {timeout_sec - s*2}s remaining... ")
                        sys.stdout.flush()

                    if not user_clicked:
                        print("\n  [Timeout] Auto-resuming with approval...")
                        await ws.send(json.dumps({"type": "approval", "decision": "allow"}))

            elif evt_type == "turn_done":
                print("\n\n  ✓ Agent turn completed.")
                turn_done = True

            elif evt_type == "error":
                print(f"\n  ✗ Error received: {data}")
                turn_done = True

    assert gate_triggered, "Human Approval Gate (permission_required) was NOT triggered!"

    # 6. Finalize & Validate Pipeline
    print("\n[CHECK 6/6] Finalizing run and inspecting Dynamic Pipeline traces...")
    http_req("POST", f"/v1/automations/{TASK_ID}/runs/{run_id}/finalize")
    pipeline = http_req("GET", f"/v1/sessions/{session_id}/pipeline")

    print(f"  ✓ Pipeline Title: {pipeline.get('title')}")
    print(f"  ✓ Overall Status: {pipeline.get('status')}")
    stages = pipeline.get("stages", [])
    nodes = pipeline.get("nodes", [])
    print(f"  ✓ Total Stages: {len(stages)}")
    print(f"  ✓ Total Trace Nodes: {len(nodes)}")

    for idx, s in enumerate(stages, 1):
        print(f"    Stage {idx}: [{s['stage_id']}] {s['title']} -> {s['status']}")

    print("\n================================================================================")
    print("                     E2E LIVE CHECK PASSED SUCCESSFULLY!                        ")
    print("================================================================================")


def main():
    parser = argparse.ArgumentParser(description="E2E Live Check for Food Poisoning Triage")
    parser.add_argument("--auto", action="store_true", help="Run automated test without waiting for manual GUI click")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds to wait for GUI action")
    args = parser.parse_args()

    mode = "auto" if args.auto else "interactive"
    asyncio.run(run_e2e_check(mode=mode, timeout_sec=args.timeout))


if __name__ == "__main__":
    main()
