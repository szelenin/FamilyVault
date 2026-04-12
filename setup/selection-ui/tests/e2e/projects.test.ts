import { test, expect } from "@playwright/test";

test.describe("Project List", () => {
  test("shows project list on home page", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toHaveText("Projects");
    await expect(page.locator("a[href*=project]").first()).toBeVisible();
  });

  test("project card shows title and scene count", async ({ page }) => {
    await page.goto("/");
    const card = page.locator("a[href*=project]").first();
    await expect(card).toContainText("Miami Trip");
    await expect(card).toContainText("scenes");
  });

  test("archive button is visible on each project", async ({ page }) => {
    await page.goto("/");
    const archiveBtn = page.locator("button svg").first();
    await expect(archiveBtn).toBeVisible();
  });

  test("clicking project navigates to scene list", async ({ page }) => {
    await page.goto("/");
    const card = page.locator("a[href*=project]").first();
    await card.click();
    await expect(page).toHaveURL(/\/project\//);
    await expect(page.locator("text=scenes")).toBeVisible();
  });
});
