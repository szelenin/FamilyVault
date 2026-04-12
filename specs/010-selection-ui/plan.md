# Implementation Plan: Scene-Based Selection UI

**Branch**: `010-selection-ui` | **Date**: 2026-04-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-selection-ui/spec.md`

## Summary

Build a SvelteKit PWA web app that shows project scenes with photo/video thumbnails. User selects/deselects items, the app writes `deselected_ids` to project.json. Claude reads it to build the timeline. Hosted on Mac Mini at `http://macmini:3000`.

## Technical Context

**Language/Version**: TypeScript, SvelteKit, Node.js (needs installing on Mac Mini)
**Primary Dependencies**: SvelteKit, @immich/ui, @vite-pwa/sveltekit, Tailwind CSS
**Storage**: Reads/writes project.json on filesystem, reads thumbnails from Immich API
**Testing**: Playwright (E2E browser tests), Vitest (unit tests for data logic)
**Target Platform**: Mobile-first PWA, also works on desktop
**Project Type**: New web application (first frontend in the project)

## Research

### R1: Node.js on Mac Mini

**Finding**: Node.js is NOT installed on Mac Mini. Need to install via Homebrew: `brew install node`.

### R2: Immich Thumbnail API

**Tested**: `GET /api/assets/{id}/thumbnail?size=preview` returns 1920×1440 JPEG (~950KB). For grid thumbnails, `?size=thumbnail` returns smaller images (~50KB). Use `thumbnail` for grid, `preview` for detail view.

### R3: Project.json Access

**Decision**: The SvelteKit app reads/writes project.json directly from the filesystem via server-side API routes. No separate backend needed — SvelteKit has server-side rendering.

```
Browser → SvelteKit server route → reads /Volumes/HomeRAID/stories/{id}/project.json
Browser → SvelteKit server route → proxies Immich thumbnail API (avoids CORS)
```

### R4: Authentication

**Decision**: The app uses the same Immich API key from `/Volumes/HomeRAID/immich/api-key.txt`. No user login needed — it's a local network app. The API key is stored server-side, never exposed to the browser.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First | PARTIAL | E2E browser tests validate the workflow. Unit tests for data logic. Not strict TDD for UI components. |
| II. Three-Layer Pyramid | PARTIAL | E2E tests primary. No unit tests for Svelte components (low value). |
| III. AI-Interaction First | PASS | UI is the bridge between user and AI — selections feed into Claude's pipeline |
| IV. Simplicity / YAGNI | PASS | Minimal app — scene list + grid + select/deselect. No editor features (deferred to IMP-013). |
| V. Privacy / Local-First | PASS | Runs on local network only. No external services. API key server-side. |

## Project Structure

```text
setup/selection-ui/                    # NEW: SvelteKit app
├── package.json
├── svelte.config.js
├── vite.config.ts                     # PWA config here
├── src/
│   ├── app.html                       # HTML shell
│   ├── app.css                        # Tailwind imports
│   ├── routes/
│   │   ├── +layout.svelte             # App layout (header, nav)
│   │   ├── +page.svelte               # Home / project list
│   │   ├── project/[id]/
│   │   │   ├── +page.svelte           # Scene list view
│   │   │   ├── +page.server.ts        # Load project.json + scene data
│   │   │   └── scene/[sceneId]/
│   │   │       ├── +page.svelte       # Thumbnail grid view
│   │   │       └── +page.server.ts    # Load scene assets
│   │   └── api/
│   │       ├── project/[id]/+server.ts          # Read/write project.json
│   │       ├── project/[id]/select/+server.ts   # Update deselected_ids
│   │       ├── thumbnail/[assetId]/+server.ts   # Proxy Immich thumbnails
│   │       └── favorite/[assetId]/+server.ts    # Toggle Immich favorite
│   └── lib/
│       ├── immich.ts                  # Immich API client (server-side)
│       ├── project.ts                 # Project.json read/write
│       └── types.ts                   # TypeScript types
├── static/
│   ├── manifest.json                  # PWA manifest
│   └── icons/                         # App icons
└── tests/
    └── e2e/                           # Playwright E2E tests
```

## Implementation Steps

### Step 1: Setup (install Node, scaffold SvelteKit, configure PWA)
### Step 2: Server-side API routes (project.json read/write, Immich proxy)
### Step 3: Scene list page (thumbnails, counts, include/exclude)
### Step 4: Scene detail grid (thumbnail grid, select/deselect, favorites)
### Step 5: Photo detail view (full-screen, swipe navigation)
### Step 6: Batch operations (select all, deselect all, photos only, videos only)
### Step 7: PWA manifest + service worker
### Step 8: Update SKILL.md (Claude gives selection UI link)
### Step 9: E2E test with real project
