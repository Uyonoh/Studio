import { test, expect } from "@playwright/test";
import { makeSessionCookie, resetMockBackend } from "./helpers";

test.describe("Launch flows", () => {
  test.describe("passwordless sign-up", () => {
    test.beforeEach(async ({ request }) => {
      await resetMockBackend(request);
    });

    test("requests a magic link for a new account", async ({ page }) => {
      await page.goto("/login");
      await expect(page.getByRole("heading", { name: /Studio/i })).toBeVisible();

      await page.getByRole("tab", { name: /Magic Link/i }).click();
      await page.getByLabel("Work email").fill("new-user@example.com");
      await page.getByRole("button", { name: /Send Magic Link/i }).click();

      const alert = page.getByRole("alert").filter({ hasText: /Check your inbox/i });
      await expect(alert).toBeVisible();
      await expect(alert).toContainText("new-user@example.com");
    });
  });

  test.describe("authenticated workspace flows", () => {
    test.beforeEach(async ({ context, request }) => {
      await resetMockBackend(request);
      await context.addCookies([makeSessionCookie()]);
    });

    test("creates a project from the projects page", async ({ page }) => {
      await page.goto("/projects");
      await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();

      await page.getByRole("button", { name: "New Project" }).click();
      const dialog = page.getByRole("dialog", { name: /Create New Project/i });
      await expect(dialog).toBeVisible();

      await page.getByLabel(/Project Name/i).fill("E2E Summer Campaign");
      await page.getByLabel(/Description/i).fill("Created by the browser E2E suite");
      await page.getByRole("button", { name: "Create Project" }).click();

      await expect(dialog).toBeHidden();
      await expect(
        page.getByRole("link", { name: "E2E Summer Campaign", exact: true })
      ).toBeVisible();
    });

    test("runs an image-to-video generation from a library asset", async ({ page }) => {
      await page.goto("/projects/proj-e2e");
      await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();
      await page.getByRole("tab", { name: /Generation Composer/i }).click();

      // Video output + image starting point derives the image_to_video task.
      await page.getByRole("button", { name: "Video", exact: true }).click();
      await page.getByRole("button", { name: /Text \+ image/i }).click();
      await page.getByRole("button", { name: "Use seeded_photo.png" }).click();

      const modelPicker = page.getByRole("combobox", { name: "Model" });
      await expect(modelPicker).toHaveAttribute("data-value", "fake-video-i2v");

      const prompt = "E2E animate the seeded product photo";
      await page.getByRole("textbox", { name: "Prompt" }).fill(prompt);
      await page.getByRole("button", { name: "Generate", exact: true }).click();
      await expect(page.getByRole("status")).toContainText(/queued/i);

      await page.getByRole("tab", { name: /Job History/i }).click();
      await expect(page.getByText(prompt)).toBeVisible();
      await expect(page.getByText("succeeded", { exact: true })).toBeVisible({ timeout: 30_000 });
      await expect(page.locator('video[src*="original.mp4"]')).toBeVisible();
    });

    test("cancels a running generation", async ({ page }) => {
      await page.goto("/projects/proj-e2e");
      await page.getByRole("tab", { name: /Generation Composer/i }).click();

      const prompt = "E2E CANCEL a slow generation";
      await page.getByRole("textbox", { name: "Prompt" }).fill(prompt);
      await page.getByRole("button", { name: "Generate", exact: true }).click();
      await expect(page.getByRole("status")).toContainText(/queued/i);

      await page.getByRole("tab", { name: /Job History/i }).click();
      const card = page.locator('article[aria-label^="Generation job-e2e-"]').filter({
        hasText: prompt,
      });
      await expect(card).toBeVisible();

      await card.getByRole("button", { name: "Cancel", exact: true }).click();
      await expect(card.getByText("canceled", { exact: true })).toBeVisible({ timeout: 20_000 });
    });

    test("retries a failed generation and recovers", async ({ page }) => {
      await page.goto("/projects/proj-e2e");
      await page.getByRole("tab", { name: /Generation Composer/i }).click();

      // The mock provider fails any prompt containing FAIL.
      const prompt = "E2E FAIL once then recover";
      await page.getByRole("textbox", { name: "Prompt" }).fill(prompt);
      await page.getByRole("button", { name: "Generate", exact: true }).click();
      await expect(page.getByRole("status")).toContainText(/queued/i);

      await page.getByRole("tab", { name: /Job History/i }).click();
      const failedCard = page.locator('article[aria-label^="Generation job-e2e-"]').filter({
        hasText: prompt,
      });
      await expect(failedCard.getByText("failed", { exact: true })).toBeVisible({
        timeout: 30_000,
      });
      await expect(failedCard.getByText(/simulated failure/i)).toBeVisible();

      await failedCard.getByRole("button", { name: "Retry", exact: true }).click();
      await expect(page.getByText("Retry queued")).toBeVisible();

      // The retried job is a new card with the same prompt and reaches succeeded.
      await expect(page.getByText("succeeded", { exact: true })).toBeVisible({ timeout: 30_000 });
    });

    test("shows the insufficient-credits path without creating a job", async ({ page }) => {
      await page.goto("/projects/proj-e2e");
      await page.getByRole("tab", { name: /Generation Composer/i }).click();

      await page.getByRole("textbox", { name: "Prompt" }).fill("E2E NO_CREDITS request");
      await page.getByRole("button", { name: "Generate", exact: true }).click();

      const alert = page.getByRole("alert").filter({ hasText: /Not enough credits/i });
      await expect(alert).toBeVisible();
      await expect(alert).toContainText(/Top up your workspace/i);

      // No job was accepted, so job history stays empty.
      await page.getByRole("tab", { name: /Job History/i }).click();
      await expect(page.getByText("No generation jobs yet")).toBeVisible();
    });
  });
});
