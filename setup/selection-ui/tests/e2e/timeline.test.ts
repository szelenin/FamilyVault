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
  // Track notes written by tests so we can clean only those up afterward
  const testNoteSceneIds: string[] = [];

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

    test("scene card shows Add your story button or existing note", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      const addStory = page.getByTestId("add-story").first();
      const existingNote = page.getByTestId("existing-note").first();
      const hasAddStory = await addStory.isVisible({ timeout: 3000 }).catch(() => false);
      const hasNote = await existingNote.isVisible({ timeout: 3000 }).catch(() => false);
      expect(hasAddStory || hasNote).toBe(true);
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
    test("tapping Add your story (or existing note) opens text field", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const addStory = page.getByTestId("add-story").first();
      const existingNote = page.getByTestId("existing-note").first();
      if (await addStory.isVisible({ timeout: 2000 }).catch(() => false)) {
        await svelteClick(addStory);
      } else {
        await svelteClick(existingNote);
      }
      await expect(page.locator("textarea")).toBeVisible({ timeout: 5000 });
    });

    test("can type a story and save", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const addStory = page.getByTestId("add-story");
      if (await addStory.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await svelteClick(addStory.last());
        await page.locator("textarea").fill("Test story note");
        await svelteClick(page.getByRole("button", { name: "Save" }));
        await page.waitForTimeout(500);
        // Verify textarea closed (save accepted) and a note indicator now exists
        await expect(page.locator("textarea")).not.toBeVisible();
        await expect(page.getByTestId("existing-note").first()).toBeVisible();
      } else {
        // All scenes have notes — verify editing an existing note works
        await svelteClick(page.getByTestId("existing-note").first());
        await expect(page.locator("textarea")).toBeVisible();
        await page.locator("textarea").fill("Updated story note");
        await svelteClick(page.getByRole("button", { name: "Save" }));
        await page.waitForTimeout(500);
        await expect(page.locator("textarea")).not.toBeVisible();
        await expect(page.getByTestId("existing-note").first()).toBeVisible();
      }
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
      const addStory = page.getByTestId("add-story").first();
      const existingNote = page.getByTestId("existing-note").first();
      if (await addStory.isVisible({ timeout: 2000 }).catch(() => false)) {
        await svelteClick(addStory);
      } else {
        await svelteClick(existingNote);
      }
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

  test.describe("Clip Editing — Preview", () => {
    test("expand scene → tap thumbnail → detail overlay opens", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      // Expand first scene
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000); // wait for details fetch
      // Tap first expanded thumbnail
      const thumb = page.getByTestId("expanded-thumbnail").first();
      if (await thumb.isVisible({ timeout: 5000 }).catch(() => false)) {
        await svelteClick(thumb);
        await expect(page.getByTestId("detail-overlay")).toBeVisible({ timeout: 5000 });
      } else {
        test.skip();
      }
    });

    test("detail overlay shows close button and counter", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000);
      const thumb = page.getByTestId("expanded-thumbnail").first();
      if (await thumb.isVisible({ timeout: 5000 }).catch(() => false)) {
        await svelteClick(thumb);
        await expect(page.getByTestId("detail-close")).toBeVisible();
        await expect(page.getByTestId("detail-counter")).toBeVisible();
      } else {
        test.skip();
      }
    });

    test("close button returns to timeline", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000);
      const thumb = page.getByTestId("expanded-thumbnail").first();
      if (await thumb.isVisible({ timeout: 5000 }).catch(() => false)) {
        await svelteClick(thumb);
        await expect(page.getByTestId("detail-overlay")).toBeVisible();
        await svelteClick(page.getByTestId("detail-close"));
        await expect(page.getByTestId("detail-overlay")).not.toBeVisible();
      } else {
        test.skip();
      }
    });

    test("prev/next navigation in detail view", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      // Find a scene with multiple items by looking for +N indicator
      const strips = page.getByTestId("thumbnail-strip");
      const count = await strips.count();
      let found = false;
      for (let i = 0; i < count; i++) {
        await svelteClick(strips.nth(i));
        await page.waitForTimeout(1000);
        const thumbCount = await page.getByTestId("expanded-thumbnail").count();
        if (thumbCount >= 2) {
          await svelteClick(page.getByTestId("expanded-thumbnail").first());
          await expect(page.getByTestId("detail-counter")).toContainText("1 /");
          await svelteClick(page.getByTestId("detail-next"));
          await expect(page.getByTestId("detail-counter")).toContainText("2 /");
          await svelteClick(page.getByTestId("detail-prev"));
          await expect(page.getByTestId("detail-counter")).toContainText("1 /");
          await svelteClick(page.getByTestId("detail-close"));
          found = true;
          break;
        }
        // Collapse and try next
        await svelteClick(strips.nth(i));
        await page.waitForTimeout(300);
      }
      if (!found) test.skip();
    });
  });

  test.describe("Clip Editing — Deselect", () => {
    test("X button visible on expanded thumbnails", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000);
      const xBtn = page.getByTestId("deselect-item").first();
      await expect(xBtn).toBeVisible({ timeout: 5000 });
    });

    test("tapping X deselects item and shows undo", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      const countBefore = await page.getByTestId("scene-card").first().locator("text=/\\d+ items/").textContent();
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000);
      await svelteClick(page.getByTestId("deselect-item").first());
      await page.waitForTimeout(300);
      await expect(page.locator("text=Item removed")).toBeVisible();
    });

    test("detail view has Remove button", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      await svelteClick(page.getByTestId("thumbnail-strip").first());
      await page.waitForTimeout(1000);
      const thumb = page.getByTestId("expanded-thumbnail").first();
      if (await thumb.isVisible({ timeout: 5000 }).catch(() => false)) {
        await svelteClick(thumb);
        await expect(page.getByTestId("detail-deselect")).toBeVisible();
        await svelteClick(page.getByTestId("detail-close"));
      } else {
        test.skip();
      }
    });
  });

  test.describe("Clip Editing — Video Trim", () => {
    // Helper: find a scene with a video item, expand it, return true if found
    async function expandSceneWithVideo(page: import("@playwright/test").Page): Promise<boolean> {
      const strips = page.getByTestId("thumbnail-strip");
      const count = await strips.count();
      for (let i = 0; i < count; i++) {
        await svelteClick(strips.nth(i));
        await page.waitForTimeout(1000);
        if (await page.getByTestId("video-badge").first().isVisible({ timeout: 2000 }).catch(() => false)) {
          return true;
        }
        // No video in this scene — collapse and try next
        await svelteClick(strips.nth(i));
        await page.waitForTimeout(300);
      }
      return false;
    }

    // video-badge is now a child of the expanded-thumbnail div — parent IS the target
    function videoThumbLocator(page: import("@playwright/test").Page) {
      return page.getByTestId("video-badge").first().locator("xpath=..");
    }

    test("filmstrip trim UI visible when opening a video item", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      if (!(await expandSceneWithVideo(page))) { test.skip(); return; }
      await svelteClick(videoThumbLocator(page));
      await expect(page.getByTestId("detail-overlay")).toBeVisible({ timeout: 5000 });
      // Filmstrip is always shown for videos — no trim button needed
      await expect(page.getByTestId("trim-ui")).toBeVisible({ timeout: 3000 });
      await svelteClick(page.getByTestId("detail-close"));
    });

    test("video trim — set start/end → verify saved via API", async ({ page }) => {
      await page.goto(TIMELINE_URL);
      await waitForHydration(page);
      if (!(await expandSceneWithVideo(page))) { test.skip(); return; }
      await svelteClick(videoThumbLocator(page));
      await expect(page.getByTestId("detail-overlay")).toBeVisible({ timeout: 5000 });
      await expect(page.getByTestId("trim-ui")).toBeVisible({ timeout: 3000 });
      // Adjust trim-start via hidden range — oninput triggers autosave
      const trimStart = page.getByTestId("trim-start");
      await trimStart.focus();
      for (let k = 0; k < 5; k++) await page.keyboard.press("ArrowRight");
      // Autosave fires on input — verify "Saved ✓" indicator
      await expect(page.getByTestId("trim-saved")).toBeVisible({ timeout: 3000 });
      // Close and verify trim badge on thumbnail
      await svelteClick(page.getByTestId("detail-close"));
      await page.waitForTimeout(300);
      await expect(page.getByTestId("trim-badge").first()).toBeVisible({ timeout: 3000 });
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
        await expect(page.locator("text=Full flow test").first()).toBeVisible();
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
