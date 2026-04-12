import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";

test.describe("Scene List", () => {
  test("shows all scenes with counts", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await expect(page.locator("h1")).toContainText("Miami Trip");
    const scenes = page.locator("a[href*=scene]");
    await expect(scenes.first()).toBeVisible();
    const count = await scenes.count();
    expect(count).toBeGreaterThan(0);
  });

  test("scene card shows thumbnail", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const thumb = page.locator("a[href*=scene] img").first();
    await expect(thumb).toBeVisible();
  });

  test("scene card shows selected count", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const card = page.locator("a[href*=scene]").first();
    await expect(card).toContainText("/");
  });

  test("clicking scene navigates to grid", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scene = page.locator("a[href*=scene]").first();
    await scene.click();
    await expect(page).toHaveURL(/\/scene\//);
  });

  test("back link returns to scenes", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scene = page.locator("a[href*=scene]").first();
    await scene.click();
    await page.locator("a[href*=project]").first().click();
    await expect(page).toHaveURL(PROJECT_URL);
  });
});
