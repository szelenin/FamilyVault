import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";

test.describe("Scene List", () => {
  test("shows all scenes with counts", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await expect(page.locator("h1")).toContainText("Miami Trip");
    const scenes = page.locator("a[href*=scene]");
    await expect(scenes.first()).toBeVisible();
    expect(await scenes.count()).toBeGreaterThan(0);
  });

  test("scene card shows thumbnail", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await expect(page.locator("a[href*=scene] img").first()).toBeVisible();
  });

  test("scene card shows selected count", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await expect(page.locator("a[href*=scene]").first()).toContainText("/");
  });

  test("clicking scene navigates to grid", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await page.locator("a[href*=scene]").first().click();
    await expect(page).toHaveURL(/\/scene\//);
  });

  test("back link returns to scenes", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await page.locator("a[href*=scene]").first().click();
    await page.locator("a[href*=project]").first().click();
    await expect(page).toHaveURL(PROJECT_URL);
  });
});

test.describe("Scene Exclude & Restore", () => {
  test("exclude button is visible", async ({ page }) => {
    await page.goto(PROJECT_URL);
    await expect(page.locator("[data-testid=exclude-scene]").first()).toBeVisible();
  });

  test("clicking exclude hides scene and shows undo", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scenesBefore = await page.locator("a[href*=scene]").count();
    await page.locator("[data-testid=exclude-scene]").first().click();
    await page.waitForTimeout(300);
    const scenesAfter = await page.locator("a[href*=scene]").count();
    expect(scenesAfter).toBe(scenesBefore - 1);
    await expect(page.locator("text=Excluded")).toBeVisible();
  });

  test("undo restores excluded scene", async ({ page }) => {
    await page.goto(PROJECT_URL);
    const scenesBefore = await page.locator("a[href*=scene]").count();
    await page.locator("[data-testid=exclude-scene]").first().click();
    await page.waitForTimeout(300);
    await page.getByRole("button", { name: "Undo" }).click();
    await page.waitForTimeout(300);
    expect(await page.locator("a[href*=scene]").count()).toBe(scenesBefore);
  });
});
