import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";

test.describe("Photo Grid", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scene = page.locator("a[href*=scene]").first();
    await scene.click();
    await expect(page).toHaveURL(/\/scene\//);
  });

  test("shows thumbnail grid", async ({ page }) => {
    const thumbs = page.locator(".grid img");
    await expect(thumbs.first()).toBeVisible({ timeout: 10000 });
    const count = await thumbs.count();
    expect(count).toBeGreaterThan(0);
  });

  test("shows selection checkboxes", async ({ page }) => {
    const checkboxes = page.locator(".grid button.absolute");
    await expect(checkboxes.first()).toBeVisible({ timeout: 10000 });
  });

  test("shows selected count", async ({ page }) => {
    await expect(page.locator("text=/\\d+\\/\\d+ selected/")).toBeVisible();
  });

  test("batch action buttons are visible", async ({ page }) => {
    await expect(page.getByText("Select All")).toBeVisible();
    await expect(page.getByText("Deselect All")).toBeVisible();
    await expect(page.getByText("Photos Only")).toBeVisible();
    await expect(page.getByText("Videos Only")).toBeVisible();
  });

  test("clicking deselect all updates count", async ({ page }) => {
    await page.getByText("Deselect All").click();
    await expect(page.locator("text=0/")).toBeVisible({ timeout: 5000 });
  });

  test("clicking select all restores count", async ({ page }) => {
    await page.getByText("Deselect All").click();
    await page.getByText("Select All").click();
    const countText = await page.locator("text=/\\d+\\/\\d+ selected/").textContent();
    const parts = countText?.match(/(\d+)\/(\d+)/);
    if (parts) expect(parts[1]).toBe(parts[2]);
  });

  test("clicking thumbnail opens detail view", async ({ page }) => {
    const thumb = page.locator(".grid .aspect-square").first();
    await thumb.click();
    await expect(page.locator(".fixed.inset-0")).toBeVisible({ timeout: 3000 });
  });
});
