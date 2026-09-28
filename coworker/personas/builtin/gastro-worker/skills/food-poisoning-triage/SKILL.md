---
name: food-poisoning-triage
description: Triages customer foodborne illness and food poisoning complaints, calculates incubation windows, assigns deterministic severity tiers (P0-Critical, P1-High, P2-Standard), drafts legally compliant commercial liability correspondence without admitting liability, attaches the official claim form PDF, and submits everything to the Human Approval Gate via gmail_send_email. Use this skill whenever a customer complaint alleging food poisoning, gastrointestinal distress, or food safety issues after dining needs to be evaluated, scored, or resolved under restaurant liability standards.
---

# Foodborne Illness Triage and Insurance Claims Protocol

This skill provides the end-to-end operational protocol for handling customer complaints
alleging foodborne illness or food poisoning in restaurants and hospitality venues.

Customer health complaints carry both immediate guest care obligations and severe commercial
liability risks. Standard Commercial General Liability (CGL) insurance policies contain
strict cooperation clauses: any admission of fault or kitchen negligence made before the
insurance adjuster investigates can void coverage. This protocol balances genuine empathy
for the customer's distress with the legal rigor required by commercial insurance carriers.

## Execution Constraints (Tool Discipline)

When executing this protocol:

- Use **only** Gmail tools: `gmail_search_messages`, `gmail_get_message`, and `gmail_send_email`.
- **Never** execute shell commands (`run_shell`, `ls`, `pwd`, `find`), code execution scripts,
  or exploratory file system searches. All evidence exists in Gmail messages, and the official
  claim form path is pre-configured.

---

## Stage 1: Inbox Ingestion and Content Classification

1. **Scan Gmail unread messages:**
   - Search unread emails broadly using:
     `gmail_search_messages(query='is:unread', max_results=3)`
   - Do not filter by hardcoded subjects or customer names in the query.
2. **Inspect each message:**
   - For each returned email ID, retrieve the full message using:
     `gmail_get_message(message_id=...)`
   - Read the sender, subject, date, body, and attachment metadata.
3. **Classify content:**
   - If the message is unrelated to food safety (marketing newsletters, supplier bills,
     routine reservation inquiries), ignore it and proceed to the next message.
   - If the message alleges food poisoning, gastrointestinal distress, nausea, vomiting,
     or acute illness after dining, proceed immediately to incident extraction.
4. **Extract incident facts:**
   - **Guest name and contact:** Full name, phone number, and reply email address.
   - **Visit timestamp:** Date, meal shift, and approximate dining time.
   - **Dishes consumed:** Specific food items, beverages, appetizers, and raw ingredients.
   - **Symptom onset and incubation window:** Elapsed hours between dining and first symptoms.
     Cross-reference against known pathogen timelines:
     - Under 6 hours: _Staphylococcus aureus_ enterotoxin, _Bacillus cereus_ (emetic).
     - 6 to 24 hours: _Clostridium perfringens_, _Salmonella enterica_, Norovirus.
     - 24 to 72 hours: _Campylobacter jejuni_, _Escherichia coli_ (STEC), _Shigella_.
   - **Diner impact ratio:** Total guests at the table vs. count of affected individuals.
   - **Proof of purchase:** Presence of an itemized dining receipt, bill, or payment confirmation.
   - **Medical documentation:** Doctor's note, emergency room report, or hospital discharge summary.

---

## Stage 2: Incident Triaging and Deterministic Risk Scoring

Evaluate the extracted facts against the 3-level priority ladder:

### Level P0: Critical Escalation

- **Criteria (any of the following):**
  - Confirmed inpatient hospital admission or emergency ambulance dispatch.
  - Severe life-threatening complications (e.g. extreme dehydration requiring IV fluids).
  - Three (3) or more individuals ill from the same meal service.
- **Required Actions:**
  - Assign badge: `[P0-CRITICAL]`.
  - Prepare an immediate Internal Operational Alert for the General Manager and Head Chef:
    - Quarantine and seal batch retention samples (_Rückstellproben_) from the affected shift.
    - Review HACCP cold-storage temperature logs and supplier lot tags.
  - Draft an urgent, empathetic customer response attaching the claim form packet.

### Level P1: High Priority

- **Criteria:**
  - Confirmed physician note or outpatient medical treatment without overnight hospital stay.
  - Or two (2) dining guests experiencing acute onset within a plausible incubation window
    for the same dish, supported by an itemized receipt.
- **Required Actions:**
  - Assign badge: `[P1-HIGH]`.
  - Prepare an internal advisory for the Head Chef to audit prep stations of the implicated dish.
  - Draft an empathetic customer response attaching the claim form packet.

### Level P2: Standard Verification

- **Criteria:**
  - Single unconfirmed complaint without medical documentation or doctor's note.
  - Or complaints with missing receipt or unverified dining timestamp.
- **Required Actions:**
  - Assign badge: `[P2-STANDARD]`.
  - Draft a courteous acknowledgment explaining operational hygiene standards and providing
    the claim form for optional completion upon submitting medical and receipt proof.

---

## Stage 3: Correspondence Drafting (Without Admission of Liability)

### Communication Guardrails

1. **Empathy Without Admission:**
   - Express sincere regret that the customer is feeling unwell.
   - **NEVER** state or imply fault (e.g. never say "our food made you sick" or "we made a mistake").
   - Frame the resolution as standard cooperation with the restaurant's commercial liability insurance carrier.
2. **Claim Form Attachment:**
   - The bundled official claim form is located at:
     `coworker/personas/builtin/gastro-worker/assets/schadenanzeige_lebensmittelvergiftung.pdf`.
   - Refer to it naturally as "the attached Incident Claim Form" in the email body. Never print raw local file paths in the email text.
3. **Required Guest Documentation:**
   - Clearly inform the customer that the insurance claims specialist requires:
     1. Completed and signed Incident Claim Form,
     2. Itemized dining receipt or proof of payment,
     3. Medical note or physician's certificate confirming diagnosis and treatment date.

### Customer Response Templates

#### Template 1: Critical Escalation (P0)

```text
Subject: URGENT: Regarding your visit on [Date] - Executive Management Review

Dear [Customer Name],

We received your message regarding your acute illness and hospital visit with profound concern. We sincerely hope that you and your dining companions are resting and feeling better.

Because we treat any report of acute health distress with the highest urgency, our executive management team and Head Chef have immediately initiated an internal review of all food safety logs, cold-storage temperature records, and supplier batch records for the service period in question.

To assist you without delay and transition this matter to our commercial liability insurance partner for direct support, please review the attached Incident Claim Form. We kindly request that you return the completed form along with your medical documentation and dining receipt at your earliest convenience.

Should you need to reach us directly, please contact our management office at [Phone Number].

We are committed to resolving this matter swiftly and wish you a speedy recovery.

Respectfully,

Executive Management and Food Safety
[Restaurant Name]
```

#### Template 2: Standard / High Priority (P1 / P2)

```text
Subject: Your feedback regarding your visit on [Date] - [Restaurant Name]

Dear [Customer Name],

Thank you for contacting us. We received your note regarding your visit on [Date] with sincere concern. The well-being and safety of our guests are always our highest priorities.

Our kitchen maintains rigorous food safety and HACCP sanitation standards in storing, preparing, and serving all menu items. To conduct a comprehensive inquiry and facilitate an evaluation with our commercial liability insurance provider, we kindly request your cooperation in providing a few additional details.

Attached you will find our official Customer Incident Claim Form. Please complete this form to the best of your knowledge and return it to us along with:
1. A copy of your itemized dining receipt or payment confirmation,
2. An official medical note or physician's report confirming the diagnosis and date of medical attention.

Upon receipt of your completed documentation, we will promptly transmit your file to our insurance claims specialist for expedited assessment.

We wish you a rapid and complete recovery.

Sincerely,

Guest Relations and Quality Assurance
[Restaurant Name]
```

---

## Stage 4: Human-in-the-Loop Approval Gate (Hard Floor)

Outward transmission of customer correspondence is a Hard Floor operation. You must **never** send emails directly without human supervisor sign-off.

1. **Present the complete Case Dossier in your response:**
   - **Incident Fact Sheet:** Guest name, visit date, dishes consumed, incubation time, evidence provided.
   - **Severity Classification:** `[P0-CRITICAL]`, `[P1-HIGH]`, or `[P2-STANDARD]` badge with justification.
   - **Complete Customer Email Draft:** Sincere empathy without admission of liability.
   - **Internal Kitchen Alert Draft:** For P0 and P1 cases, alerting Head Chef and GM.
   - **Attached Claim Form Reference:** Note that `schadenanzeige_lebensmittelvergiftung.pdf` is attached.
2. **Submit to the Approval Gate:**
   - Submit the drafted communication to the Human Approval Gate by invoking:
     ```python
     gmail_send_email(
         to="guest@example.com",
         subject="Regarding your visit on [Date] - [Restaurant Name]",
         body="[Full drafted email text]",
         attachments=["coworker/personas/builtin/gastro-worker/assets/schadenanzeige_lebensmittelvergiftung.pdf"]
     )
     ```
   - Calling `gmail_send_email` IS how you submit the draft to the approval gate. The platform's security floor intercepts the tool call, holds the outgoing message, and displays an approval card in the user's Inbox awaiting supervisor sign-off.
