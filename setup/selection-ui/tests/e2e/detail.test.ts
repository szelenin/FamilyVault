import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";

test.describe("Detail View", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scene = page.locator("a[href*=scene]").first();
    await scene.click();
    await page.waitForSelector(".grid img", { timeout: 10000 });
    await page.locator(".grid .aspect-square").first().click();
    await expect(page.locator(".fixed.inset-0")).toBeVisible({ timeout: 3000 });
  });

  test("shows full-screen photo", async ({ page }) => {
    const img = page.locator(".fixed img[src*=preview]");
    await expect(img).toBeVisible();
  });

  test("shows photo counter", async ({ page }) => {
    await expect(page.locator("text=/1 \\//")).toBeVisible();
  });

  test("shows selected toggle button", async ({ page }) => {
    const btn = page.locator(".fixed button.rounded-full");
    await expect(btn).toBeVisible();
  });

  test("close button exits detail view", async ({ page }) => {
    await page.locator(".fixed button").first().click();
    await expect(page.locator(".fixed.inset-0")).not.toBeVisible();
  });

  test("next button navigates to next photo", async ({ page }) => {
    await page.getByText("Next").click();
    await expect(page.locator("text=/2 \\//")).toBeVisible();
  });

  test("prev button navigates back", async ({ page }) => {
    await page.getByText("Next").click();
    await page.getByText("Prev").click();
    await expect(page.locator("text=/1 \\//")).toBeVisible();
  });
});
