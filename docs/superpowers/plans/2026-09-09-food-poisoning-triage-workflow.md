# Food Poisoning Claims & Insurance Triage Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate the `food-poisoning-triage` persona and its domain skills (`incident-scoring` and `insurance-dispatch`) into GastroWorker to automate the ingestion, scoring, and German insurance claim form dispatching for food poisoning complaints under strict Human Gate governance.

**Architecture:** Implement a Builtin Persona manifest conforming to GastroWorker's `PersonaManifest` schema, equipped with `pdf_support` and messaging connectors. Attach two specialized skills for multi-factor risk scoring (P0-P2) and German formal insurance response drafting with the standard *Schadenanzeige* PDF template.

**Tech Stack:** Python 3.10+, PyYAML, Pydantic v2, Pytest, GastroWorker Persona Registry & Permissions Engine, ReportLab / pypdf (for standard PDF generation).

---

## File Structure

```
coworker/personas/builtin/food-poisoning-triage/
├── manifest.md                              # Core persona manifest and system prompt
├── assets/
│   └── schadenanzeige_lebensmittelvergiftung.pdf # Bundled German insurance claim form
└── skills/
    ├── incident-scoring/
    │   └── SKILL.md                         # Scoring rules (P0/P1/P2) & evidence checklist
    └── insurance-dispatch/
        └── SKILL.md                         # German correspondence templates & human gate guidelines

tests/
└── test_food_poisoning_persona.py           # Unit & integration tests for manifest and scoring
```

---

## Tasks

### Task 1: Create Test Suite for the Food Poisoning Persona Bundle

**Files:**
- Create: `tests/test_food_poisoning_persona.py`

- [ ] **Step 1: Write the test verifying persona manifest loading and skill discovery**

```python
from pathlib import Path
from coworker.personas.manifest import parse_manifest
from coworker.personas.registry import PersonaRegistry

def test_food_poisoning_persona_manifest_validity():
    manifest_path = Path("coworker/personas/builtin/food-poisoning-triage/manifest.md")
    assert manifest_path.exists(), "Manifest file must exist"
    text = manifest_path.read_text(encoding="utf-8")
    m = parse_manifest(text, builtin=True, fallback_id="food-poisoning-triage")
    assert m.id == "food-poisoning-triage"
    assert m.name == "Food Safety & Insurance Claims Specialist"
    assert "P0" in m.system_prompt
    assert "Schadenanzeige" in m.system_prompt

def test_food_poisoning_skills_discovered():
    reg = PersonaRegistry.builtin()
    persona = reg.get("food-poisoning-triage")
    assert persona is not None, "Persona must be registered in builtin registry"
    skill_names = [s.name for s in persona.skills]
    assert "incident-scoring" in skill_names
    assert "insurance-dispatch" in skill_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_food_poisoning_persona.py -v`
Expected: FAIL with `AssertionError: Manifest file must exist`

---

### Task 2: Implement the Food Poisoning Domain Skills

**Files:**
- Create: `coworker/personas/builtin/food-poisoning-triage/skills/incident-scoring/SKILL.md`
- Create: `coworker/personas/builtin/food-poisoning-triage/skills/insurance-dispatch/SKILL.md`

- [ ] **Step 1: Implement `incident-scoring` skill**
Define frontmatter (`name: incident-scoring`, `description: ...`) and instructions:
- Extraction protocol: diner counts, onset time, incubation calculation, symptoms, receipt verification.
- Triaging rules:
  - **P0 (Critical)**: Hospitalization, ER admission, or >=3 affected diners.
  - **P1 (High)**: Confirmed doctor's sick note / medical diagnosis, or 2 affected diners with proof of purchase.
  - **P2 (Standard)**: Single guest without medical certificate or invoice.

- [ ] **Step 2: Implement `insurance-dispatch` skill**
Define frontmatter (`name: insurance-dispatch`, `description: ...`) and instructions:
- German email drafting standards (*Höflichkeitsform*, *Sehr geehrte Damen und Herren*, *Betriebshaftpflichtversicherung*).
- Form attachment procedure: attach `schadenanzeige_lebensmittelvergiftung.pdf`.
- Mandatory Human Approval Gate: never call `send_message` or `send_email` without explicit user review.

---

### Task 3: Generate and Bundle the German Insurance Claim Form PDF Asset

**Files:**
- Create: `coworker/personas/builtin/food-poisoning-triage/assets/schadenanzeige_lebensmittelvergiftung.pdf`
- Create script (scratch): `scripts/generate_sample_schadenanzeige.py`

- [ ] **Step 1: Write generator script using Python standard / pypdf / reportlab to create the official form**
Fields include:
- *Name und Anschrift des Anspruchstellers* (Claimant name & address)
- *Datum und Uhrzeit des Restaurantbesuchs* (Date and time of visit)
- *Rechnungsnummer / Zahlungsnachweis* (Invoice / Payment reference)
- *Verzehrte Speisen und Getränke* (Food & drink items consumed)
- *Art und Beginn der Beschwerden* (Symptoms & onset time)
- *Behandelnder Arzt / Krankenhaus* (Treating physician / Hospital)

- [ ] **Step 2: Execute generator script to output the PDF into `assets/`**
Verify the PDF is valid and readable via `pypdf` or `pdf_support`.

---

### Task 4: Implement the `food-poisoning-triage` Persona Manifest

**Files:**
- Create: `coworker/personas/builtin/food-poisoning-triage/manifest.md`

- [ ] **Step 1: Write the full Persona Manifest**
Frontmatter:
```yaml
---
ships: true
id: food-poisoning-triage
name: Food Safety & Insurance Claims Specialist
icon: shield-alert
tagline: Triage food poisoning complaints, score medical risk, draft German insurance claims under human review
requires_folder: false
subagents: false
scheduling: true
version: "1"
team: lead
tools: [files, search, todo]
recommended_models: [anthropic:claude-opus-4-8, openai:gpt-4o]
default_permission_mode: interactive
description: Ingests non-physical food poisoning complaints and medical attachments, scores severity (P0-P2), and drafts professional German insurance notifications and claim forms for human approval.
---
```
System Prompt:
- Role & Authority: First Notice of Loss (FNOL) Claims Specialist for hospitality liability insurance in Germany (*Betriebshaftpflicht*).
- Workflow stages: Ingestion -> Attachment extraction -> Incident scoring -> Draft preparation -> Human gate escalation.
- Core rules: Empathy without admitting legal fault, strict untrusted input handling, zero-leakage of health data (GDPR / DSGVO).

---

### Task 5: Verify Implementation and Run Test Suite

**Files:**
- Test: `tests/test_food_poisoning_persona.py`

- [ ] **Step 1: Run pytest to verify all tests pass**
Run: `.venv/bin/pytest tests/test_food_poisoning_persona.py -v`
Expected: PASS (2 passed)

- [ ] **Step 2: Run full regression test suite on persona loading**
Run: `.venv/bin/pytest tests/test_persona_manifest.py tests/test_persona_skills.py -v`
Expected: PASS

- [ ] **Step 3: Verify package discovery**
Run: `.venv/bin/python -c "from coworker.personas.registry import PersonaRegistry; reg = PersonaRegistry.builtin(); assert reg.get('food-poisoning-triage') is not None; print('Persona discovered successfully')"`
Expected: "Persona discovered successfully"
