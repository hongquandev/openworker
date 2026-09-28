---
name: haccp-compliance
description: Audits commercial kitchen cold-chain temperature logs, critical control points, and retention food sample (Rueckstellproben) protocols under HACCP food safety standards. Use this skill when investigating kitchen compliance during a food incident, performing routine cold-storage audits, verifying retention sample quarantine status, or when any temperature deviation or food safety hazard needs to be evaluated against regulatory benchmarks.
---

# HACCP Kitchen Compliance Audit

HACCP (Hazard Analysis and Critical Control Points) is the international standard for
preventing foodborne hazards in commercial kitchens. This skill codifies the temperature
benchmarks, retention sample protocols, and audit procedures that a restaurant must
follow, both during routine operations and when an incident investigation is underway.

The reason these numbers matter: regulatory health inspectors and insurance adjusters
both look for documented temperature compliance. A kitchen that can demonstrate
continuous cold-chain integrity during the incident window has a strong defense.
A kitchen with gaps in its logs does not.

## Critical temperature benchmarks

These are the standard limits used across EU food safety regulations and most
international HACCP frameworks.

| Equipment                  | Optimal Range       | Critical Limit          |
|----------------------------|--------------------:|------------------------:|
| Walk-in chillers           | 1 to 4 C            | Max 5 C (41 F)         |
| Reach-in refrigerators     | 1 to 4 C            | Max 5 C (41 F)         |
| Deep freezers              | -18 C or below       | -18 C (0 F)            |
| Hot-holding stations       | 60 C or above        | Min 60 C (140 F)       |

**The danger zone** is 5 C to 60 C. Perishable foods must not remain in this range for
more than 2 cumulative hours. If temperature logs show a prolonged excursion into the
danger zone during the incident window, flag it immediately: this is the kind of finding
that changes the outcome of an investigation.

## Retention sample protocol (Rueckstellproben)

Retention samples exist so that if someone gets sick, there is a physical sample of what
was served that can be tested. Without them, the investigation relies entirely on
circumstantial evidence.

**During service:**
- High-risk items (raw seafood, tartare, emulsified sauces, dairy-based preparations)
  require mandatory retention samples.
- Minimum portion: 100g per batch or menu component.
- Storage: sealed, date-labeled containers at 4 C or below.
- Retention period: minimum 72 hours after end of service.

**When a P0 or P1 incident is reported:**
- Immediately isolate and lock the corresponding retention containers. Mark them as
  evidence and record the time of quarantine.
- Do not discard quarantined samples until explicitly released by QA, the insurance
  adjuster, or the health inspection authority.
- If the retention sample for the implicated dish is missing or was already discarded,
  document this gap. It weakens the restaurant's position but must be reported honestly.

## Incident audit procedure

When an incident investigation is triggered (usually by the `incident-scoring` skill
producing a P0 or P1 classification):

1. **Pull temperature logs** for the 48 hours preceding and following the reported
   meal. Look for any excursion above 5 C in cold storage or below 60 C in
   hot-holding during the relevant service period.
2. **Retrieve supplier documentation** for the specific protein, shellfish, or
   high-risk ingredient lots used during the implicated shift. This includes invoice
   numbers, batch receiving tags, and delivery temperature readings.
3. **Draft the Internal Kitchen Notice** for the Head Chef, specifying:
   - Which lot identifiers to quarantine.
   - Which prep stations to audit and deep-clean.
   - Which temperature logs to preserve for the insurance file.
4. Present the audit findings as part of the case dossier submitted to the approval
   gate. The kitchen notice is an internal document; it does not go to the guest.
