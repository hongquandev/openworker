# Food Poisoning Automation Quickstart Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated "Food poisoning & claims triage" Quickstart Template to the Automations view in GastroWorker UI with English instructions, and enable the backend automation creator to bind tasks directly to the `food-poisoning-triage` persona.

**Architecture:** Update `coworker/server/manager.py` to accept `agent` in `create_automation`, extend `surfaces/gui/src/api.ts` types, add the template configuration to `AutomationQuickstart.tsx`, and sync localization keys in `en.json` and `zh.json`.

**Tech Stack:** Python 3.10+ (FastAPI, manager.py), TypeScript, React 18, i18next, Vitest.

---

## File Structure

- Modify: `coworker/server/manager.py:5061-5075`
- Modify: `surfaces/gui/src/api.ts:2052-2065`
- Modify: `surfaces/gui/src/components/AutomationQuickstart.tsx:120-170`
- Modify: `surfaces/gui/src/locales/en.json:540-575`
- Modify: `surfaces/gui/src/locales/zh.json:540-575`
- Test: `tests/test_automation_agent_binding.py`
- Test: `surfaces/gui/src/locales/locales.test.ts`

---

## Tasks

### Task 1: Enable Persona Binding in Backend Automation Creator

**Files:**
- Create: `tests/test_automation_agent_binding.py`
- Modify: `coworker/server/manager.py`

- [ ] **Step 1: Write test for creating automation with custom agent**
```python
def test_create_automation_with_agent(tmp_path, monkeypatch):
    from coworker.server.manager import SessionManager
    from coworker.providers import ModelCapabilities, ProviderClient

    class FakeProvider(ProviderClient):
        def complete(self, **kwargs): pass
        def capabilities(self, model): return ModelCapabilities()

    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    mgr = SessionManager(workspace=tmp_path, provider=FakeProvider())
    res = mgr.create_automation({
        "title": "Food Claims Check",
        "instructions": "Scan emails",
        "cron": "0 8 * * *",
        "agent": "food-poisoning-triage"
    })
    assert res["ok"] is True
    task = mgr.task_store.get(res["task"]["id"])
    assert task.agent == "food-poisoning-triage"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_automation_agent_binding.py -v`
Expected: FAIL (`assert task.agent == 'food-poisoning-triage'`, got `'cowork'`)

- [ ] **Step 3: Update `coworker/server/manager.py` to use `agent=payload.get("agent") or "cowork"`**

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_automation_agent_binding.py -v`
Expected: PASS

---

### Task 2: Synchronize Localization Keys (`en.json` & `zh.json`)

**Files:**
- Modify: `surfaces/gui/src/locales/en.json`
- Modify: `surfaces/gui/src/locales/zh.json`
- Test: `surfaces/gui/src/locales/locales.test.ts`

- [ ] **Step 1: Add localization keys to `en.json` and `zh.json`**
English (`en.json`):
- `"tmpl_food_poisoning_title"`: `"Food poisoning & claims triage"`
- `"tmpl_food_poisoning_blurb"`: `"Scan inbox for food poisoning complaints, score medical risk, and draft German insurance claims."`
- `"why_food_poisoning_email"`: `"Incoming guest complaints and receipts"`
- `"tmpl_food_poisoning_instructions"`: `"Check unread emails for customer complaints alleging food poisoning or foodborne illness. Extract any attached receipts and medical certificates, evaluate severity (P0/P1/P2) using the incident-scoring skill, and draft a formal German response attaching the Schadenanzeige form using insurance-dispatch. Submit all drafts to the Human Approval Gate before sending."`

Chinese (`zh.json`):
- `"tmpl_food_poisoning_title"`: `"食物中毒投诉与保险初审"`
- `"tmpl_food_poisoning_blurb"`: `"扫描收件箱中的食物中毒投诉，评估医疗风险等级，并起草德国保险理赔文件。"`
- `"why_food_poisoning_email"`: `"来信投诉与消费凭证"`
- `"tmpl_food_poisoning_instructions"`: `"Check unread emails for customer complaints alleging food poisoning or foodborne illness. Extract any attached receipts and medical certificates, evaluate severity (P0/P1/P2) using the incident-scoring skill, and draft a formal German response attaching the Schadenanzeige form using insurance-dispatch. Submit all drafts to the Human Approval Gate before sending."`

- [ ] **Step 2: Run `npm test` in `surfaces/gui` to verify `locales.test.ts` passes**

---

### Task 3: Update `AutomationQuickstart.tsx` and Frontend API Types

**Files:**
- Modify: `surfaces/gui/src/api.ts`
- Modify: `surfaces/gui/src/components/AutomationQuickstart.tsx`

- [ ] **Step 1: Add `agent?: string` to `createAutomation` payload type in `api.ts`**
- [ ] **Step 2: Add `foodpoisoning` to `TEMPLATES` in `AutomationQuickstart.tsx`**
- [ ] **Step 3: Update `onCreate` call in `AutomationQuickstart.tsx` to forward `agent: picked.agent`**
- [ ] **Step 4: Run typecheck `npx tsc --noEmit` and unit test in `surfaces/gui`**
