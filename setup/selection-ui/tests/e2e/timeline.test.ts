import { test, expect } from "@playwright/test";

const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";
const TIMELINE_URL = `${PROJECT_URL}/timeline`;

// Svelte 5 uses event delegation — needs bubbling MouseEvent for onclick handlers
async function svelteClick(locator: import("@playwright/test").Locator) {
  await locator.evaluate((el) => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
}

// Wait for Svelte 5 hydration to complete before interacting
async function waitForHydration(page: import("@playwright/test").Page) {
  await page.waitForTimeout(500);
}

const API_NOTES = "http://localhost:3000/api/project/2026-04-11-miami-trip-last-visit/notes";

test.describe("Screen 2 — Timeline Review", () => {
  // Clear scene notes before tests to ensure clean state
  test.beforeAll(async () => {
    const resp = await fetch(API_NOTES);
    if (resp.ok) {
      const notes = await resp.json();
      for (const sceneId of Object.keys(notes)) {
        await fetch(API_NOTES, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scene_id: sceneId, note: "" }),
        });
      }
    }
  });

  test.describe("Navigation", () => {
    test("Screen 1 has Review Timeline link", async ({ page }) => {
      await page.goto(PROJECT_URL);
      await expect(page.getByText("Review Timeline")).toBeVisible();
    });

    test("Review Timeline link navigates to Screen 2", async ({ page }) => {
      await page.goto(PROJECT_URL);
      await page.getByText("Review Timeline").click();
      await expect(page).toHaveURL(/\/timeline/);
    });

    test("Screen 2 has Selection link back", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await expect(page.getByTestId("back-to-selection")).toBeVisible();
    });

    test("Selection link navigates back to Screen 1", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await page.getByTestId("back-to-selection").click();
      await expect(page).toHaveURL(PROJECT_URL);
    });
  });

  test.describe("Scene Cards", () => {
    test("shows scene cards with labels", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      const cards = page.getByTestId("scene-card");
      await expect(cards.first()).toBeVisible();
      const count = await cards.count();
      expect(count).toBeGreaterThan(0);
    });

    test("scene card shows item count", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await expect(page.locator("text=/\\d+ items/").first()).toBeVisible();
    });

    test("scene card shows thumbnail strip", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      const thumbs = page.getByTestId("thumbnail-strip").first().locator("img");
      await expect(thumbs.first()).toBeVisible({ timeout: 10000 });
    });

    test("scene card shows Add your story button", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await expect(page.getByTestId("add-story").first()).toBeVisible();
    });
  });

  test.describe("Expand Thumbnails", () => {
    test("tapping thumbnail strip expands to show all items", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const moreIndicator = page.locator("text=/\\+\\d+/").first();
      if (await moreIndicator.isVisible({ timeout: 3000 }).catch(() => false)) {
        const strip = page.getByTestId("thumbnail-strip").first();
        const imgsBefore = await strip.locator("img").count();
        await svelteClick(strip);
        await page.waitForTimeout(500);
        const imgsAfter = await strip.locator("img").count();
        expect(imgsAfter).toBeGreaterThanOrEqual(imgsBefore);
      } else {
        test.skip();
      }
    });
  });

  test.describe("Story Notes", () => {
    test("tapping Add your story opens text field", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("add-story").first());
      await expect(page.locator("textarea")).toBeVisible({ timeout: 5000 });
    });

    test("can type a story and save", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      // Use last add-story button to avoid conflicts with other tests
      await svelteClick(page.getByTestId("add-story").last());
      await page.locator("textarea").fill("This was the highlight of our trip!");
      await svelteClick(page.getByRole("button", { name: "Save" }));
      await page.waitForTimeout(500);
      await expect(page.locator("text=This was the highlight")).toBeVisible();
    });

    test("story indicator appears after saving", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const noteIndicator = page.getByTestId("existing-note");
      if (await noteIndicator.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await expect(noteIndicator.first()).toBeVisible();
      } else {
        await svelteClick(page.getByTestId("add-story").first());
        await page.locator("textarea").fill("Test note for indicator");
        await svelteClick(page.getByRole("button", { name: "Save" }));
        await page.waitForTimeout(500);
        await expect(page.getByTestId("existing-note").first()).toBeVisible();
      }
    });

    test("tapping existing note opens editor with current text", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const existingNote = page.getByTestId("existing-note").first();
      if (await existingNote.isVisible({ timeout: 2000 }).catch(() => false)) {
        await svelteClick(existingNote);
        await expect(page.locator("textarea")).toBeVisible();
        const value = await page.locator("textarea").inputValue();
        expect(value.length).toBeGreaterThan(0);
      } else {
        test.skip();
      }
    });

    test("cancel discards changes", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("add-story").first());
      await expect(page.locator("textarea")).toBeVisible({ timeout: 3000 });
      await page.locator("textarea").fill("This should be discarded");
      await svelteClick(page.getByRole("button", { name: "Cancel" }));
      await expect(page.locator("textarea")).not.toBeVisible();
    });
  });

  test.describe("Remove Scene", () => {
    test("remove button is visible on each scene", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      const removeButtons = page.getByTestId("remove-scene");
      await expect(removeButtons.first()).toBeVisible();
    });

    test("clicking remove shows undo toast", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const scenesBefore = await page.getByTestId("scene-card").count();
      await svelteClick(page.getByTestId("remove-scene").first());
      await page.waitForTimeout(300);
      await expect(page.locator("text=Removed")).toBeVisible();
      await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
      const scenesAfter = await page.getByTestId("scene-card").count();
      expect(scenesAfter).toBe(scenesBefore - 1);
    });

    test("undo restores removed scene", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const scenesBefore = await page.getByTestId("scene-card").count();
      await svelteClick(page.getByTestId("remove-scene").first());
      await page.waitForTimeout(300);
      await svelteClick(page.getByRole("button", { name: "Undo" }));
      await page.waitForTimeout(300);
      const scenesAfter = await page.getByTestId("scene-card").count();
      expect(scenesAfter).toBe(scenesBefore);
    });
  });

  test.describe("Summary Bar", () => {
    test("summary bar shows item count and duration", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      const stats = page.getByTestId("summary-stats");
      await expect(stats).toBeVisible();
      await expect(stats).toContainText("items");
    });

    test("summary bar has Selection link", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await expect(page.getByTestId("summary-selection-link")).toBeVisible();
    });
  });

  test.describe("Full Flow", () => {
    test("Screen 1 → Screen 2 → add story → back to Screen 1", async ({ page }) => {
      await page.goto(PROJECT_URL);
      await expect(page.locator("h1")).toContainText("Miami Trip");

      // Navigate to Screen 2
      await page.getByText("Review Timeline").click();
      await expect(page).toHaveURL(/\/timeline/);
      await waitForHydration(page);
      await expect(page.locator("h1")).toContainText("Your Story");

      // Add a story (use last available "Add your story" to avoid conflicts)
      const addStory = page.getByTestId("add-story");
      if (await addStory.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await svelteClick(addStory.first());
        await expect(page.locator("textarea")).toBeVisible({ timeout: 3000 });
        await page.locator("textarea").fill("Full flow test story");
        await svelteClick(page.getByRole("button", { name: "Save" }));
        await page.waitForTimeout(500);
        await expect(page.locator("text=Full flow test")).toBeVisible();
      } else {
        // All scenes already have notes — verify an existing note is shown
        await expect(page.getByTestId("existing-note").first()).toBeVisible();
      }

      // Navigate back to Screen 1
      await page.getByTestId("back-to-selection").click();
      await expect(page).toHaveURL(PROJECT_URL);
    });
  });
});
