import { test, expect } from "@playwright/test";

const SUPABASE_URL = "http://127.0.0.1:3101";
const STORAGE_KEY = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;

// 1x1 transparent PNG
const TINY_PNG_BUFFER = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
);

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

test.describe("Asset upload E2E", () => {
  test.beforeEach(async ({ context }) => {
    await context.addCookies([makeSessionCookie()]);
  });

  test("uploads an image asset into the project and confirms its presence", async ({ page }) => {
    await page.goto("/projects/proj-e2e");

    // Project header loads
    await expect(page.getByRole("heading", { name: /Brand Launch/i })).toBeVisible();

    // Seeded asset visible
    await expect(page.getByText("seeded_photo.png")).toBeVisible();

    // Open upload zone
    await page.getByRole("button", { name: /upload assets/i }).click();

    // Attach file to hidden file input
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "e2e_brand_banner.png",
      mimeType: "image/png",
      buffer: TINY_PNG_BUFFER,
    });

    // Upload progress card transitions to Ready
    await expect(page.getByText("Ready")).toBeVisible();

    // The newly uploaded asset card appears in the grid (using its unique image alt attribute)
    const uploadedCard = page.getByAltText("e2e_brand_banner.png");
    await expect(uploadedCard).toBeVisible();

    // Clicking the asset opens the details drawer (force click in case overlay is active)
    await uploadedCard.click({ force: true });
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("512 × 512 px")).toBeVisible();
    await expect(drawer.getByText("image/png")).toBeVisible();

    // Close drawer
    await page.getByRole("button", { name: /close drawer/i }).click();
    await expect(drawer).not.toBeVisible();
  });
});
