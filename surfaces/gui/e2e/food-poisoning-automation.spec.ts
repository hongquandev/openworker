// E2E Test: Food Poisoning Incident Triage & Insurance Claim Automation Template
// Verifies the full UI lifecycle of the gastrotriage automation quickstart template:
// 1. Surfacing the template card with title, blurb, and cadence indicator.
// 2. Expanding the configure card with Gmail connector requirement.
// 3. One-click sign-in to connect Gmail, revealing the recipe schedule options.
// 4. Submission of the automation, verifying network payload carries English instructions and gastro-worker persona.
// 5. Creation of the recurring automation and navigation to its detail view.

import { expect } from "@playwright/test";
import { test } from "./fixtures";

async function openQuickstart(page) {
  await page.goto("/");
  await page.getByTestId("nav-automations").click();
  await expect(
    page.getByText("Recurring tasks GastroWorker runs on a schedule."),
  ).toBeVisible();
  await page.getByRole("button", { name: "+ New automation" }).click();
  await expect(page.getByText("Start from a template")).toBeVisible();
}

test("gastrotriage template card displays correctly and creates automation with English instructions", async ({
  page,
}) => {
  await openQuickstart(page);

  // 1. Template card is visible in the Quickstart grid with correct English title & blurb
  const card = page.getByTestId("qs-template-gastrotriage");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Gastro: Food Incident & Claims Triage");
  await expect(card).toContainText("Scan inbox for food poisoning complaints");
  await expect(card).toContainText("Daily");

  // 2. Expand the template configuration
  await card.click();
  const cfg = page.getByTestId("qs-configure");
  await expect(cfg).toBeVisible();
  await expect(cfg).toContainText("Set up");
  await expect(cfg).toContainText("Gastro: Food Incident & Claims Triage");

  // 3. Verify Gmail connector row explains why it is needed and gates creation
  await expect(cfg).toContainText("Incoming guest complaints and receipts");
  await expect(page.getByTestId("ob-create")).toBeDisabled();
  await expect(page.getByTestId("ob-create-hint")).toContainText("Connect Gmail");

  // 4. Connect Gmail via cloud sign-in flow (mirrors pipeline digest recipe flow)
  await page.getByTestId("ob-connect-gmail").click();
  await expect(page.getByTestId("ob-cloudpane")).toBeVisible();
  await page.getByTestId("ob-cloud-signin").click();
  await expect(page.getByTestId("ob-recipe")).toBeVisible({ timeout: 15_000 });

  // 5. Verify default daily schedule in recipe
  await expect(
    page.getByTestId("ob-recipe").getByRole("button", { name: "Day" }),
  ).toContainText("Every day");

  // 6. Intercept POST /v1/automations request to verify full payload
  const [createReq] = await Promise.all([
    page.waitForRequest(
      (req) => req.url().includes("/v1/automations") && req.method() === "POST",
    ),
    page.getByTestId("ob-create").click(),
  ]);

  const postData = createReq.postDataJSON();
  expect(postData.title).toBe("Gastro: Food Incident & Claims Triage");
  expect(postData.agent).toBe("gastro-worker");
  expect(postData.instructions).toContain("food-poisoning-triage");
  expect(postData.instructions).toContain("claim form");
  expect(postData.instructions).toContain("manager approval");

  // 7. Detail page displays created automation
  await expect(page.getByRole("button", { name: /Run now/ })).toBeVisible();
  await expect(
    page.getByText("Gastro: Food Incident & Claims Triage").first(),
  ).toBeVisible();
});
