import { expect } from "@playwright/test";
import { test } from "./fixtures";

async function openConnectors(page: any) {
  await page.goto("/");
  await page.getByTestId("account-row").click();
  await page.getByRole("button", { name: "Connectors", exact: true }).click();
}

async function serveGmail(page: any, override: any) {
  await page.route("**/v1/connectors", async (route: any) => {
    const res = await route.fetch();
    const json = await res.json();
    json.connectors = json.connectors.map((c: any) => (c.name === "gmail" ? { ...c, ...override } : c));
    await route.fulfill({ json });
  });
}

test("Gmail detail displays custom Google OAuth section with copyable redirect URI", async ({
  page,
}) => {
  await serveGmail(page, {
    connected: true,
    enabled: true,
    account: "rohit@gmail.com",
    accounts: [
      { email: "rohit@gmail.com", default: true, managed: true, scopes: "gmail", needs_reauth: false },
    ],
    filters: { senders: [], labels: [] },
  });

  await openConnectors(page);
  await page.getByTestId("connector-gmail").click();
  await expect(page.getByTestId("gmail-detail")).toBeVisible();

  // Verify custom Google OAuth card exists
  const customSection = page.getByTestId("gmail-custom-oauth");
  await expect(customSection).toBeVisible();
  await expect(customSection).toContainText("Google OAuth (Direct Client)");
  await expect(customSection).toContainText("Sign in with Google");

  // Open settings panel
  await page.getByTestId("gmail-custom-toggle-settings").click();
  await expect(customSection).toContainText("/v1/connectors/gmail/oauth/callback");

  // Verify inputs and button exist
  const clientIdInput = page.getByTestId("gmail-custom-client-id");
  const clientSecretInput = page.getByTestId("gmail-custom-client-secret");
  const authBtn = page.getByTestId("gmail-custom-auth-btn");

  await expect(clientIdInput).toBeVisible();
  await expect(clientSecretInput).toBeVisible();
  await expect(authBtn).toBeVisible();

  // Test client validation when client ID is cleared
  await clientIdInput.fill("");
  await authBtn.click();
  await expect(customSection).toContainText("Please provide Google Client ID");
});
