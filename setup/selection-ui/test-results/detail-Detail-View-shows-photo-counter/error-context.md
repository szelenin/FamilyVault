# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: detail.test.ts >> Detail View >> shows photo counter
- Location: tests/e2e/detail.test.ts:24:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('.fixed.inset-0')
Expected: visible
Timeout: 3000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 3000ms
  - waiting for locator('.fixed.inset-0')

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - banner [ref=e3]:
    - link "Story Engine" [ref=e4] [cursor=pointer]:
      - /url: /
  - main [ref=e5]:
    - generic [ref=e6]:
      - link "← Scenes" [ref=e7] [cursor=pointer]:
        - /url: /project/2026-04-11-miami-trip-last-visit
      - heading "Scene 6" [level=1] [ref=e8]
      - paragraph [ref=e9]: 3/3 selected
    - generic [ref=e10]:
      - button "Select All" [ref=e11]
      - button "Deselect All" [ref=e12]
      - button "Photos Only" [ref=e13]
      - button "Videos Only" [ref=e14]
    - generic [ref=e15]:
      - button "✓" [ref=e17]:
        - generic [ref=e18]: ✓
      - button "✓" [ref=e20]:
        - generic [ref=e21]: ✓
      - button "✓" [ref=e23]:
        - generic [ref=e24]: ✓
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";
  4  | 
  5  | test.describe("Detail View", () => {
  6  |   test.beforeEach(async ({ page }) => {
  7  |     await page.goto(PROJECT_URL);
  8  |     // Click a scene that likely has multiple items
  9  |     const scenes = page.locator("a[href*=scene]");
  10 |     const count = await scenes.count();
  11 |     // Try to find a scene with more items (later scenes tend to be bigger)
  12 |     const sceneIndex = Math.min(5, count - 1);
  13 |     await scenes.nth(sceneIndex).click();
  14 |     await page.waitForSelector(".grid img", { timeout: 10000 });
  15 |     await page.locator(".grid .aspect-square").first().click();
> 16 |     await expect(page.locator(".fixed.inset-0")).toBeVisible({ timeout: 3000 });
     |                                                  ^ Error: expect(locator).toBeVisible() failed
  17 |   });
  18 | 
  19 |   test("shows full-screen photo", async ({ page }) => {
  20 |     const img = page.locator(".fixed img[src*=preview]");
  21 |     await expect(img).toBeVisible();
  22 |   });
  23 | 
  24 |   test("shows photo counter", async ({ page }) => {
  25 |     await expect(page.locator("text=/\\d+ \\//")).toBeVisible();
  26 |   });
  27 | 
  28 |   test("shows selected toggle button", async ({ page }) => {
  29 |     const btn = page.locator(".fixed button.rounded-full");
  30 |     await expect(btn).toBeVisible();
  31 |   });
  32 | 
  33 |   test("close button exits detail view", async ({ page }) => {
  34 |     await page.locator(".fixed button").first().click();
  35 |     await expect(page.locator(".fixed.inset-0")).not.toBeVisible();
  36 |   });
  37 | 
  38 |   test("next button navigates if not last photo", async ({ page }) => {
  39 |     const nextBtn = page.getByText("Next");
  40 |     const isDisabled = await nextBtn.isDisabled();
  41 |     if (!isDisabled) {
  42 |       await nextBtn.click();
  43 |       await expect(page.locator("text=/2 \\//")).toBeVisible();
  44 |     }
  45 |   });
  46 | 
  47 |   test("prev and next navigation", async ({ page }) => {
  48 |     const nextBtn = page.getByText("Next");
  49 |     const isDisabled = await nextBtn.isDisabled();
  50 |     if (!isDisabled) {
  51 |       await nextBtn.click();
  52 |       await page.getByText("Prev").click();
  53 |       await expect(page.locator("text=/1 \\//")).toBeVisible();
  54 |     }
  55 |   });
  56 | });
  57 | 
```