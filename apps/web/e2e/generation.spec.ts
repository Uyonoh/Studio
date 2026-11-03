import { test, expect } from "@playwright/test";

const SUPABASE_URL = "http://127.0.0.1:3101";
const STORAGE_KEY = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;

function makeSessionCookie() {
  const session = {
    access_token: "e2e-access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "e2e-refresh-token",
    user: {
      id: "usr-e2e-123",
      aud: "authenticated",
      role: "authenticated",
      email: "e2e@example.com",
    },
  };
  const encoded = Buffer.from(JSON.stringify(session)).toString("base64url");
  return {
    name: STORAGE_KEY,
    value: `base64-${encoded}`,
    domain: "127.0.0.1",
    path: "/",
    httpOnly: false,
    secure: false,
    sameSite: "Lax" as const,
  };
}

test.describe("Generation flow E2E", () => {
  test.beforeEach(async ({ context }) => {
    await context.addCookies([makeSessionCookie()]);
  });

  test("submits a prompt and watches the job reach succeeded without a reload", async ({
    page,
  }) => {
    await page.goto("/projects/proj-e2e");
    await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();

    // Composer: schema-driven form loads the fake model.
    await page.getByRole("tab", { name: /Generation Composer/i }).click();
    const modelSelect = page.getByLabel("Model");
    await expect(modelSelect).toBeVisible();
    await expect(modelSelect).toHaveValue("fake-image-fast");

    const prompt = "A cinematic lighthouse at dusk";
    await page.getByRole("textbox", { name: "Prompt" }).fill(prompt);
    await page.getByRole("button", { name: "Generate", exact: true }).click();

    // Job accepted (202) and echoed back to the composer.
    await expect(page.getByRole("status")).toContainText(/queued/i);

    // History shows the same job and receives status changes without a page reload.
    await page.getByRole("tab", { name: /Job History/i }).click();
    await expect(page.getByText(prompt)).toBeVisible();

    await expect(page.getByText("succeeded", { exact: true })).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(`img[alt="${prompt}"]`)).toBeVisible();
  });
});
