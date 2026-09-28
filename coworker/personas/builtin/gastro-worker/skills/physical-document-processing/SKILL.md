---
name: physical-document-processing
description: Uses native model vision to inspect photographed restaurant documents, classify them, extract evidence-backed structured fields, validate accounting data, propose filenames and filing destinations, prepare workbook updates and email drafts, and hold all consequential actions at a Human Approval Gate. Use for invoices, receipts, tax notices, government letters, licenses, contracts, and other photographed physical records.
---

# Physical Document Processing

Process photographed documents as a governed accounting workflow. The original image or
rendered PDF page is the source of truth. Do not run OCR or treat OCR output as primary
evidence. If the active model cannot see the image, stop and request a vision-capable model
or a new image attachment; never infer values from a filename or placeholder.

## Required workflow

1. **Intake and visual quality**
   - For scheduled Drive runs, call `drive_list_folder` on the configured intake folder.
     Reconcile file ids against the `Document Register` with `sheets_read_range`; process
     only unseen ids or previously retryable ids.
   - For an image in Drive, call `drive_read_image`. Its result injects the original image
     into the next model turn. Never call `drive_read_file` to inspect an image as text.
   - Inspect every supplied image directly with model vision.
   - Record page count, orientation, blur, glare, cropping, obstruction, and whether more
     than one document appears in an image.
   - For multi-page records, verify page order and identify likely missing pages.
   - Check for likely duplicates using document type, issuer/vendor, reference number,
     issue date, and total. A possible duplicate always goes to review.
   - If a money amount, identifier, deadline, or page is unreadable, label it `unknown`.
     Never complete a partial number by guessing.

2. **Visual classification and extraction**
   - Classify the document as one of: `sales_invoice`, `vendor_invoice`, `receipt`,
     `government_tax_notice`, `government_letter`, `license`, `contract`, `insurance`,
     `payroll`, or `unknown`.
   - Extract only fields visible in the document. For every field return its value,
     confidence from 0 to 1, page number, and short visual evidence such as
     `top-right box labelled Invoice No.` Do not expose hidden chain-of-thought.
   - Use ISO dates (`YYYY-MM-DD`) and decimal numeric values. Preserve the printed currency.
   - At minimum try to extract document/reference number, issuer/vendor, issue date,
     due/response date, subtotal, tax, total, payment/transfer status, and requested action.

3. **Deterministic validation**
   - Check `subtotal + tax = total` when all three values exist.
   - Check issue date is not after due date.
   - Flag an unusual tax rate instead of correcting it.
   - Flag a government deadline within three days as `urgent`.
   - Flag tax, legal, payroll, government, unknown, duplicate, missing-page, and inconsistent
     records as requiring review regardless of confidence.
   - A field below 0.80 must not be written to the master workbook. A field from 0.80 to
     0.94 must be highlighted for Human verification. Money, deadlines, tax, and legal
     obligations always require Human verification.

4. **Prepare, do not prematurely commit**
   - Propose a filename in the form
     `YYYY-MM-DD_DocumentType_Organization_Reference_AmountCurrency.ext`. Sanitize unsafe
     characters. Use `UNKNOWN` for absent verified values.
   - Propose a destination under the configured year and category tree. Do not invent a
     new remote folder when no routing rule matches; use `01_NEEDS_REVIEW/ROUTING`.
   - Prepare an idempotent workbook change keyed by `document_id`, with a Drive/local link,
     source filename, field confidence, review status, and audit metadata. Never append a
     second row for a retry of the same document.
   - Prepare draft replies, reminders, and dashboard deltas. Drafts must cite the source
     document and must not invent facts absent from the image or workbook.
   - Read worksheet names with `sheets_get_spreadsheet` and existing rows with
     `sheets_read_range`. Use the configured master spreadsheet id and worksheet names;
     never guess them. Prepare exact arguments for `sheets_update_values` or
     `sheets_append_rows`, but do not execute either before the review package is complete.

5. **Human Approval Gate — hard floor**
   - Present one review package containing the original file reference, classification,
     extracted fields with confidence/evidence, validation warnings, proposed filename and
     folder, proposed workbook changes, draft messages, attachments, and dashboard impact.
   - Stop before remote rename/move, official workbook mutation, email send, government
     response, or final status change. Use the relevant write tool only to create the
     platform approval card after the complete review package is ready.
   - Tax, legal, payroll, government, and external-send actions can never bypass this gate.
   - Submit each consequential write through its real platform gate:
     `drive_update_file` for rename/move, `sheets_update_values`/`sheets_append_rows` for
     workbook and audit rows, and `gmail_send_email` for external or internal mail.
   - If Human denies and supplies corrected values, regenerate the review package with the
     corrections and submit new exact tool calls. A denial alone commits nothing.

6. **After approval**
   - Execute only the exact approved mutations. If approval included edits, use the edited
     values and retain both proposed and approved values in the audit record.
   - Set lifecycle states in order:
     `RECEIVED -> VISION_COMPLETE -> NEEDS_REVIEW -> APPROVED -> FILED -> RECORDED -> SENT -> COMPLETED`.
     Skip `SENT` when no outbound message exists.
   - Report every mutation and retain original path/name, final path/name, workbook row,
     message id, model id, schema version, approver, timestamps, and approval provenance.
   - Apply approved operations in this order: update/append workbook rows; rename/move the
     Drive file; send approved Gmail drafts; append the final audit row. If a later action
     fails, keep the document out of `COMPLETED`, record the partial state, and retry only
     the missing idempotent action.

## Required structured review package

Use these exact top-level labels so the pipeline UI can render the run:

```text
Document ID: DOC-YYYY-NNNNNN
Vision Status: complete | needs_better_image | missing_pages | unavailable
Document Type: <classification>
Risk Level: standard | high | urgent
Source File: <name or file id>
Proposed Filename: <name>
Proposed Folder: <path>
Duplicate Check: clear | possible_duplicate | confirmed_duplicate
Validation: <concise result>
Workbook Status: proposed | approved | recorded | blocked
Draft Status: none | prepared | approved | sent
Human Gate: pending | approved | rejected | reprocess
```

Follow the labels with a field table containing `Field`, `Value`, `Confidence`, `Page`,
`Visual evidence`, and `Review required`. End with a concise list of proposed mutations.

## Failure behavior

- No visible image: `Vision Status: unavailable`; do not substitute OCR.
- Blur, glare, crop, or obstruction hides a required field: request a better image.
- Missing page: do not finalize classification-sensitive or financial totals.
- Workbook locked or unavailable: keep the prepared update and create a retry/review item.
- Missing recipient or filing destination: keep the draft/proposal pending.
- Repeated run: reconcile by `document_id`; do not duplicate rows or messages.
