import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";

test.describe("Detail View", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROJECT_URL);
    // Click a scene that likely has multiple items
    const scenes = page.locator("a[href*=scene]");
    const count = await scenes.count();
    // Try to find a scene with more items (later scenes tend to be bigger)
    const sceneIndex = Math.min(5, count - 1);
    await scenes.nth(sceneIndex).click();
    await page.waitForSelector(".grid img", { timeout: 10000 });
    await page.locator(".grid .aspect-square").first().click();
    await expect(page.locator(".fixed.inset-0")).toBeVisible({ timeout: 3000 });
  });

  test("shows full-screen photo", async ({ page }) => {
    const img = page.locator(".fixed img[src*=preview]");
    await expect(img).toBeVisible();
  });

  test("shows photo counter", async ({ page }) => {
    await expect(page.locator("text=/\\d+ \\//")).toBeVisible();
  });

  test("shows selected toggle button", async ({ page }) => {
    const btn = page.locator(".fixed button.rounded-full");
    await expect(btn).toBeVisible();
  });

  test("close button exits detail view", async ({ page }) => {
    await page.locator(".fixed button").first().click();
    await expect(page.locator(".fixed.inset-0")).not.toBeVisible();
  });

  test("next button navigates if not last photo", async ({ page }) => {
    const nextBtn = page.getByText("Next");
    const isDisabled = await nextBtn.isDisabled();
    if (!isDisabled) {
      await nextBtn.click();
      await expect(page.locator("text=/2 \\//")).toBeVisible();
    }
  });

  test("prev and next navigation", async ({ page }) => {
    const nextBtn = page.getByText("Next");
    const isDisabled = await nextBtn.isDisabled();
    if (!isDisabled) {
      await nextBtn.click();
      await page.getByText("Prev").click();
      await expect(page.locator("text=/1 \\//")).toBeVisible();
    }
  });
});
