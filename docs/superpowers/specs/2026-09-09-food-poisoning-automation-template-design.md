# Food Poisoning Claims Automation Quickstart Template Design

**Author**: Antigravity  
**Date**: 2026-09-09  
**Status**: Approved (Brainstorming Phase)  
**Topic**: UI Automation Quickstart Template for Food Poisoning Triage and Claims Dispatch  

---

## 1. Overview & Objectives

Provide a one-click **Automation Quickstart Template** on GastroWorker's Automations page (`ScheduledView.tsx`), titled **"Food poisoning & claims triage"**, positioned alongside existing templates such as *Inbox digest* and *Morning brief*.

When scheduled:
- Wakes up automatically according to a recurring schedule (e.g. daily at 08:30 or hourly).
- Binds execution to the newly created `food-poisoning-triage` coworker.
- Executes automated instructions in English to inspect incoming emails (via Gmail/Outlook), parse non-physical documents (receipts, medical notes), calculate severity scores (P0-P2), and draft German insurance claim packets (*Schadenanzeige*).
- Parks all outbound drafts in GastroWorker's **Human Approval Gate** queue.

---

## 2. Component Changes

### 1. Backend Server (`coworker/server/manager.py`)
- Update `create_automation(self, payload)` to read `agent = payload.get("agent") or "cowork"` and assign it to `ScheduledTask.agent`.

### 2. Frontend API (`surfaces/gui/src/api.ts`)
- Extend the `createAutomation` payload type signature to include optional `agent?: string`.

### 3. Frontend Automation Quickstart (`surfaces/gui/src/components/AutomationQuickstart.tsx`)
- Add the `foodpoisoning` entry to `TEMPLATES` with:
  - `key`: `"foodpoisoning"`
  - `titleKey`: `"automations.tmpl_food_poisoning_title"`
  - `blurbKey`: `"automations.tmpl_food_poisoning_blurb"`
  - `cadenceKey`: `"automations.cadence_daily"`
  - `conns`: `[{ name: "gmail", whyKey: "automations.why_food_poisoning_email" }]`
  - `day`: `"daily"`
  - `time`: `"08:30"`
  - `agent`: `"food-poisoning-triage"`
  - `instructions`: English instructions resolving from `automations.tmpl_food_poisoning_instructions`.

### 4. Internationalization (`surfaces/gui/src/locales/en.json` & `zh.json`)
Synchronize localization keys:
- `automations.tmpl_food_poisoning_title`
- `automations.tmpl_food_poisoning_blurb`
- `automations.why_food_poisoning_email`
- `automations.tmpl_food_poisoning_instructions` (in English)

---

## 3. Verification Plan
- Unit tests: `npm test` in `surfaces/gui` (verifying `locales.test.ts` and `ScheduledView.test.tsx`).
- Backend unit tests: `pytest` verifying `create_automation` accepts `agent`.
