import { expect } from "@playwright/test";
import { test } from "./fixtures";

const googleConnector = (
  name: string,
  title: string,
  logo: string,
  connected = true,
) => ({
  name, title, logo, icon: "", blurb: "", auth: "oauth", two_way: false,
  channels: false, available: true, connected, enabled: connected,
  account: connected ? "restaurant@example.com" : null, allowed_users: [],
  fields: [], instructions: [], tools: [], managed: true, managed_profile: connected,
});

async function routeGoogleConnectors(
  page: import("@playwright/test").Page,
  state: { drive?: boolean; sheets?: boolean; gmail?: boolean } = {},
) {
  await page.route(/\/v1\/connectors$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        connectors: [
          googleConnector("google_drive", "Google Drive", "google_drive", state.drive ?? true),
          googleConnector("google_sheets", "Google Sheets", "google_sheets", state.sheets ?? true),
          googleConnector("gmail", "Gmail", "gmail", state.gmail ?? true),
        ],
      }),
    });
  });
}

test("Physical Document Processing appears in UI and creates a Vision automation", async ({
  page,
}) => {
  await routeGoogleConnectors(page);
  await page.goto("/");
  await page.getByTestId("nav-automations").click();
  await page.getByRole("button", { name: "+ New automation" }).click();

  const card = page.getByTestId("qs-template-physicaldocs");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Physical Document Processing");
  await expect(card).toContainText("Agent Vision");
  await expect(card).toContainText("Daily");

  await card.click();
  const configure = page.getByTestId("qs-configure");
  await expect(configure).toContainText("Photographed documents in the intake folder");
  await expect(configure).toContainText("Master workbook, worksheets, and dashboard");
  await expect(configure).toContainText("Government replies and internal reminders");
  await expect(configure.getByText("Google Drive", { exact: true })).toBeVisible();
  await expect(configure.getByText("Google Sheets", { exact: true })).toBeVisible();
  await expect(configure.getByText("Gmail", { exact: true })).toBeVisible();
  await expect(configure.getByText("✓ Connected", { exact: true })).toHaveCount(3);
  await expect(page.getByTestId("ob-create")).toBeDisabled();
  await page.getByTestId("ob-intake-folder-id").fill("drive-intake-123");
  await page.getByTestId("ob-processed-folder-id").fill("drive-processed-456");
  await page.getByTestId("ob-spreadsheet-id").fill("sheet-master-789");
  await expect(page.getByTestId("ob-create")).toBeEnabled();

  const [request] = await Promise.all([
    page.waitForRequest(
      (candidate) =>
        candidate.url().includes("/v1/automations") && candidate.method() === "POST",
    ),
    page.getByTestId("ob-create").click(),
  ]);

  const payload = request.postDataJSON();
  expect(payload.title).toBe("Physical Document Processing");
  expect(payload.agent).toBe("gastro-worker");
  expect(payload.model).toBe("antigravity:gemini-3.8-flash");
  expect(payload.instructions).toContain("Workflow: physical-document-processing");
  expect(payload.instructions).toContain("native Vision");
  expect(payload.instructions).toContain("never use OCR as the primary evidence");
  expect(payload.instructions).toContain("Human Approval Gate");
  expect(payload.instructions).toContain("audit trail");
  expect(payload.instructions).toContain("Intake folder id: drive-intake-123");
  expect(payload.instructions).toContain("Processed root folder id: drive-processed-456");
  expect(payload.instructions).toContain("Master spreadsheet id: sheet-master-789");

  await expect(page.getByRole("button", { name: /Run now/ })).toBeVisible();
  await expect(page.getByText("Physical Document Processing").first()).toBeVisible();
});

test("Physical Document Processing stays gated until Drive, Sheets, and Gmail are connected", async ({
  page,
}) => {
  await routeGoogleConnectors(page, { sheets: false });
  await page.goto("/");
  await page.getByTestId("nav-automations").click();
  await page.getByRole("button", { name: "+ New automation" }).click();
  await page.getByTestId("qs-template-physicaldocs").click();

  const configure = page.getByTestId("qs-configure");
  await expect(configure.getByText("Google Drive", { exact: true })).toBeVisible();
  await expect(configure.getByText("Google Sheets", { exact: true })).toBeVisible();
  await expect(configure.getByText("Gmail", { exact: true })).toBeVisible();
  await expect(page.getByTestId("ob-create")).toBeDisabled();
  await expect(page.getByTestId("ob-create-hint")).toContainText("Connect Google Sheets");
});
