import { expect } from "@playwright/test";
import { test } from "./fixtures";

// Full browser flow for photographed paper processing:
// image upload -> native Vision review package -> validation -> Human Gate -> approved record.
// The fixture speaks the production WebSocket event protocol, so composer attachments,
// streamed messages, approval suspension/resume, and final lifecycle all use real UI paths.

const ONE_PIXEL_JPEG = Buffer.from(
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EF//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EF//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EF//2Q==",
  "base64",
);

test("photographed invoice runs Vision extraction and commits only after Human approval", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByText("Draft the launch note").first().click();

  const composer = page.getByPlaceholder(/Ask the coworker/);
  await expect(composer).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "invoice-101.jpg",
    mimeType: "image/jpeg",
    buffer: ONE_PIXEL_JPEG,
  });
  await expect(page.getByRole("img", { name: "invoice-101.jpg" })).toBeVisible();

  await composer.fill("Process invoice 101 with physical-document-processing using Vision.");
  await page.getByRole("button", { name: "Send" }).click();

  // Vision result is structured and grounded in a visible location on the image.
  await expect(page.getByText("Document ID: DOC-2026-000101").first()).toBeVisible();
  await expect(page.getByText("Vision Status: complete").first()).toBeVisible();
  await expect(page.getByText("Document Type: sales_invoice").first()).toBeVisible();
  await expect(page.getByText(/subtotal 1000\.00 \+ tax 80\.00 = total 1080\.00/).first()).toBeVisible();
  await expect(page.getByText(/top-right Invoice No\. box/).first()).toBeVisible();
  await expect(page.getByText("Human Gate: pending").first()).toBeVisible();

  // The official workbook mutation is suspended at the real approval card.
  const approval = page.getByTestId("approval-row").last();
  await expect(approval).toContainText("DOC-2026-000101.json");
  await expect(page.getByText("Workbook Status: recorded")).toHaveCount(0);
  await approval.getByRole("button", { name: "Allow", exact: true }).click();

  // Only the approval response resumes the tool and reaches the committed lifecycle.
  await expect(page.getByText("Workbook Status: recorded").last()).toBeVisible();
  await expect(page.getByText("Human Gate: approved").last()).toBeVisible();
  await expect(page.getByText(/RECEIVED -> VISION_COMPLETE -> APPROVED -> FILED -> RECORDED -> COMPLETED/)).toBeVisible();
  await expect(page.getByText(/Audit trail saved with approval provenance/)).toBeVisible();
});

test("document workflow refuses to substitute OCR when no image is attached", async ({ page }) => {
  await page.goto("/");
  const composer = page.getByPlaceholder(/Ask the coworker/);
  await composer.fill("Process invoice 101 with physical-document-processing using Vision.");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Vision Status: unavailable")).toBeVisible();
  await expect(page.getByText("Human Gate: reprocess")).toBeVisible();
  await expect(page.getByTestId("approval-row")).toHaveCount(0);
});
