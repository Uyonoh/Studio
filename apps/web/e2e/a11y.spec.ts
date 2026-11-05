import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { makeSessionCookie, resetMockBackend } from "./helpers";

async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  expect(
    results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }))
  ).toEqual([]);
}

test.describe("Accessibility and responsiveness", () => {
  test.beforeEach(async ({ context, request }) => {
    await resetMockBackend(request);
    await context.addCookies([makeSessionCookie()]);
  });

  test("login page has no axe violations", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Studio/i })).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("projects page has no axe violations", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();
    await expect(page.getByText("Brand Launch")).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("project workspace has no axe violations across tabs", async ({ page }) => {
    await page.goto("/projects/proj-e2e");
    await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();
    await expectNoA11yViolations(page);

    await page.getByRole("tab", { name: /Generation Composer/i }).click();
    await expect(page.getByRole("textbox", { name: "Prompt" })).toBeVisible();
    await expectNoA11yViolations(page);

    await page.getByRole("tab", { name: /Job History/i }).click();
    await expect(page.getByRole("heading", { name: /Job history/i })).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("dialog traps focus and restores it on Escape", async ({ page }) => {
    await page.goto("/projects");
    const trigger = page.getByRole("button", { name: "New Project" });
    await trigger.click();

    const dialog = page.getByRole("dialog", { name: /Create New Project/i });
    await expect(dialog).toBeVisible();
    await expect(page.getByLabel(/Project Name/i)).toBeFocused();

    // Tabbing repeatedly never escapes the dialog.
    for (let i = 0; i < 12; i += 1) {
      await page.keyboard.press("Tab");
      const focusInside = await page.evaluate(() => {
        const active = document.activeElement;
        const dialogEl = document.querySelector('[role="dialog"]');
        return Boolean(dialogEl && active && dialogEl.contains(active));
      });
      expect(focusInside).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("asset drawer traps focus and restores it on Escape", async ({ page }) => {
    await page.goto("/projects/proj-e2e");
    const assetButton = page.getByRole("button", { name: /seeded_photo/i }).first();
    await assetButton.click();

    const drawer = page.getByRole("dialog", { name: /seeded_photo/i });
    await expect(drawer).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(assetButton).toBeFocused();
  });

  test("workspace is usable at 375px with no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/projects/proj-e2e");
    await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();

    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1
    );
    expect(hasOverflow).toBe(false);

    // The sidebar is off-canvas until the menu button opens it.
    const navigation = page.getByRole("complementary", { name: "Main Navigation" });
    await expect(navigation).not.toBeInViewport();

    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(navigation).toBeInViewport();

    await page.getByRole("button", { name: "Close navigation" }).click();
    await expect(navigation).not.toBeInViewport();
  });

  test("dark theme is applied", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(
      true
    );

    const background = await page
      .locator("div.min-h-screen")
      .first()
      .evaluate((element) => getComputedStyle(element).backgroundColor);
    expect(background).toBe("rgb(11, 12, 16)");
  });
});
