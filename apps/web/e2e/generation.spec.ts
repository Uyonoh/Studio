import { test, expect } from "@playwright/test";
import { makeSessionCookie, resetMockBackend } from "./helpers";

test.describe("Generation flow E2E", () => {
  test.beforeEach(async ({ context, request }) => {
    await resetMockBackend(request);
    await context.addCookies([makeSessionCookie()]);
  });

  test("submits a prompt and watches the job reach succeeded without a reload", async ({
    page,
  }) => {
    await page.goto("/projects/proj-e2e");
    await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();

    // Composer: schema-driven form loads the fake model.
    await page.getByRole("tab", { name: /Generation Composer/i }).click();
    const modelPicker = page.getByRole("combobox", { name: "Model" });
    await expect(modelPicker).toBeVisible();
    await expect(modelPicker).toHaveAttribute("data-value", "fake-image-fast");

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
