# Timeline Selection UX — Options Analysis

**Date**: 2026-04-11  
**Context**: IMP-007 — user needs to browse photos by scene and select/deselect items for the clip. Must work on mobile.

## The Problem

The user browses 500+ trip photos organized by scenes. They need to:
- See all photos/videos in a scene
- Remove items they don't want
- Add items from other scenes
- Tell Claude "I'm done, use what's left"

Current approach (text commands to Claude) doesn't scale — the user said "I see photos I want to remove but I can't easily tell you which ones."

---

## Option 1: Immich Albums (one per scene)

**How it works**: Claude creates one Immich album per scene. User opens each album in Immich app, removes unwanted photos. Tells Claude "done." Claude reads the albums and uses whatever's left.

**Development effort**: 0 days (just a workflow change in SKILL.md)

| Pros | Cons |
|------|------|
| Zero development — works today | Multiple albums clutter Immich |
| Immich mobile app works great | Can't see scene metadata (labels, counts) in Immich |
| User already knows Immich UI | Removing photos is destructive (no undo at album level) |
| Desktop + mobile | No batch select/deselect |
| | Can't compare across scenes |
| | Need to clean up albums after |

**Mobile**: Excellent (Immich native app)  
**Integration**: Strong (Claude reads albums via API)

---

## Option 2: Custom Web UI

**How it works**: Build a lightweight web app (HTML/JS/CSS) hosted on the Mac Mini. Shows photos grouped by scene with checkboxes. User selects/deselects, clicks "Done." The app saves selections to project.json or creates an Immich album.

**Development effort**: 3-5 days MVP, 1-2 weeks polished

**Tech options**:
- Simple: Vanilla HTML + JS + Immich API
- Polished: Svelte + @immich/ui (Immich's official component library, Tailwind CSS)
- The app would be accessible at `http://macmini:PORT`

| Pros | Cons |
|------|------|
| Complete control over UX | 3-5 days development |
| Scene-based layout with labels | Need to host/deploy |
| Click-to-select, batch operations | Another service to maintain |
| Mobile responsive | Authentication/security |
| Can show scene metadata, counts | Separate from Immich (different URL) |
| Undo/redo possible | |
| Drag to reorder | |
| Can integrate with Claude via project.json | |

**Mobile**: Excellent (responsive web)  
**Integration**: Excellent (reads/writes project.json directly)

---

## Option 3: Immich Plugin/Extension

**How it works**: Write a custom page or extension inside Immich itself. Users would access it from Immich's navigation.

**Development effort**: Unknown — **Immich does NOT have a plugin system** (as of v2.6.3). A GitHub discussion (#13337) requests it, but no timeline from the Immich team.

| Pros | Cons |
|------|------|
| Would be native to Immich | Plugin system doesn't exist |
| No separate app | Would require forking Immich |
| Consistent look and feel | Maintenance burden on Immich upgrades |
| | No timeline from Immich team |

**Mobile**: Would match Immich's mobile support  
**Integration**: Would be ideal but **not feasible today**

---

## Option 4: Progressive Web App (PWA)

**How it works**: Same as Option 2 but packaged as a PWA — user adds it to phone home screen, works like a native app, can work offline.

**Development effort**: 4-6 days (slightly more than basic web UI for PWA features)

| Pros | Cons |
|------|------|
| Feels like a native app | Slightly more dev work than plain web |
| Works offline (cached) | Still needs initial network connection |
| Add to home screen | Not in app stores |
| Push notifications possible | |
| All Option 2 benefits | |

**Mobile**: Excellent (home screen app)  
**Integration**: Same as Option 2

---

## Option 5: MCP Server + Claude Code

**How it works**: Build an MCP server that connects Claude Code directly to Immich. Claude can call tools like `list_scenes()`, `show_scene_photos()`, `select_photo()`, `get_selection()`. No visual UI — Claude manages the selection through conversation, but with structured data access.

**Development effort**: 2-4 days

| Pros | Cons |
|------|------|
| Deep Claude Code integration | No visual browsing — still text-based |
| Standardized (MCP is Anthropic's official protocol) | Desktop Claude Code only (no mobile) |
| Can be shared/reused | User still can't SEE photos in Claude mobile |
| Clean tool interface | |
| Can combine with visual options | |

**Mobile**: No (Claude Code desktop only)  
**Integration**: Excellent (purpose-built for Claude)

---

## Option 6: Telegram Bot

**How it works**: A Telegram bot sends scene photos as albums, shows selection buttons. User taps to select/deselect. Bot stores selections and creates the Immich album.

**Development effort**: 3-7 days

| Pros | Cons |
|------|------|
| Native mobile (Telegram is installed) | Photo previews are small in Telegram |
| Conversational workflow | Another messaging app |
| Inline buttons for selection | Rate limits for media-heavy workflows |
| Stateful (remembers selections) | Requires bot server |
| Works on iOS + Android | Not ideal for browsing many photos |

**Mobile**: Excellent (Telegram native app)  
**Integration**: Medium (bot bridges Immich and Claude)

---

## Option 7: Claude Inline Visuals (HTML artifacts)

**How it works**: Claude generates an interactive HTML page inline in chat. Shows photo grid with click-to-select. User interacts directly in Claude's interface.

**Development effort**: 1-3 days

| Pros | Cons |
|------|------|
| No separate app or deployment | Does NOT work on Claude mobile app |
| Interactive within Claude chat | Can't connect to Immich API directly |
| Quick to prototype | Photos must be passed as data (slow) |
| | Single-page, stateless |
| | Limited JavaScript capabilities |

**Mobile**: NO — only Claude web/desktop  
**Integration**: Medium (data must be passed manually)

---

## Comparison Matrix

| Option | Dev Time | Mobile | Desktop | Visual | Integration | Maintenance |
|--------|----------|--------|---------|--------|-------------|-------------|
| 1. Immich Albums | 0 days | Excellent | Excellent | Good | Strong | None |
| 2. Custom Web UI | 3-5 days | Excellent | Excellent | Excellent | Excellent | Low |
| 3. Immich Plugin | N/A | — | — | — | — | — |
| 4. PWA | 4-6 days | Excellent | Excellent | Excellent | Excellent | Low |
| 5. MCP Server | 2-4 days | No | Good | No | Excellent | Low |
| 6. Telegram Bot | 3-7 days | Excellent | Good | Medium | Medium | Medium |
| 7. Claude Visuals | 1-3 days | No | Good | Good | Medium | None |

---

## Recommendation

### Immediate (today): Option 1 — Immich Albums

Use one album per scene. Zero development. The user already knows Immich. Good enough for testing the workflow.

### Short-term (this week): Option 2 — Custom Web UI

Build a simple responsive web page hosted on the Mac Mini:
- Scene-based photo grid with thumbnails from Immich API
- Tap/click to select/deselect
- "Done" button writes selection to project.json
- Claude reads the selection and builds the timeline
- Accessible at `http://macmini:3000/project/PROJECT_ID`
- Uses Immich's `@immich/ui` Svelte components for consistent look

This gives the best balance of:
- Full control over scene-based UX
- Mobile + desktop support
- Direct integration with project.json
- Low maintenance (static HTML served from Mac Mini)

### Optional add-on: Option 5 — MCP Server

For Claude Code desktop users, an MCP server provides structured tool access. But this is a complement to the visual UI, not a replacement.

### Not recommended:
- Option 3 (Immich plugin) — doesn't exist
- Option 6 (Telegram) — adds another app, small previews
- Option 7 (Claude visuals) — no mobile support
