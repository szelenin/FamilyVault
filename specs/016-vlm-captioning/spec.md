# Feature Specification: IMP-018 VLM Captioning & Extraction

**Feature Branch**: `016-vlm-captioning`
**Created**: 2026-06-14
**Status**: Draft
**Input**: User description: "Implement IMP-018 — VLM Captioning & Extraction (understanding layer)…" (see PRD `docs/PRD.md` IMP-018 / R097–R101 and the approved technical design `docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md`)

## Overview

Today the archive can only be searched by shallow concept tags and by who is in a photo (the existing photo server's CLIP + face recognition). It cannot answer "what is happening" ("my son *playing* piano") or "find the photo of the restaurant menu" (text in the image). This feature builds an **understanding-layer index**: for every photo and video it produces a rich natural-language **description** of what is happening, extracts any **on-screen text**, and stores a **semantic representation** so the library becomes searchable by meaning — in any of the household's languages. Identity ("who") remains the photo server's job; this feature never tries to recognise specific people.

It runs as an **unattended batch indexer** on a memory-constrained home server, so it must be safe to run repeatedly, resumable after interruption, bounded in disk use, and able to manage system memory automatically.

## Clarifications

### Session 2026-06-14

- Q: How are the search-accuracy criteria validated in IMP-018, given fusion ranking is deferred to IMP-020? → A: IMP-018 does a smoke-level check (a handful of known queries return the correct asset via basic hybrid text∪semantic retrieval); the quantitative 80/90/80% accuracy targets move to IMP-020 (fusion).
- Q: In what language are the VLM descriptions stored? → A: English (single canonical language); cross-language search (EN/RU/UK queries) works via the multilingual semantic representation — descriptions are not translated/duplicated.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Searchable understanding of photos (Priority: P1)

The operator runs the indexer over the photo library. Each photo gets a written description of what is happening plus any visible text, and a semantic representation, stored in the index keyed to the photo. The operator (and downstream search) can then find photos by **meaning** ("kids playing in the snow") and by **visible text** ("the menu from the Italian place"), including when the query is phrased in a different language than the description.

**Why this priority**: This is the baseline that proves the entire spine — extraction, the index, semantic + text search — on the cheaper, simpler media type. It delivers standalone value (concept/text photo search the archive never had) before any video work.

**Independent Test**: Run the indexer on a small photo set; verify every photo has a non-empty description (or a recorded non-error status), visible text is captured where present, and a meaning-based query and a text-based query each return the expected photo.

**Acceptance Scenarios**:

1. **Given** a photo of a child at a piano, **When** the operator searches "playing piano", **Then** that photo is returned among the top results even though the stored description uses different words.
2. **Given** a photo containing a restaurant menu, **When** the operator searches for text printed on the menu, **Then** that photo is returned.
3. **Given** a query in Russian or Ukrainian for a concept whose description was written in English, **When** the operator searches, **Then** the matching photo is still returned.
4. **Given** the library already indexed, **When** the operator runs the indexer again with no changes, **Then** no photo is re-processed.

---

### User Story 2 - Understanding of videos, including the moment something happens (Priority: P2)

The operator runs the indexer over videos. Each video gets a video-level description of what happens across the clip, shorter descriptions tied to **timestamps** (so a specific moment can be located), and any on-screen text. Videos become searchable by activity and text the same way photos are, and the operator can find *when* in a clip something occurs.

**Why this priority**: Videos are where "what is happening" matters most (a still frame can't distinguish *sitting at* vs *playing* a piano) and where the technical complexity lives. It builds on the proven photo spine.

**Independent Test**: Run the indexer on a few short clips (one single-shot, one multi-scene); verify each has a video-level description, at least one timestamped segment, on-screen text where present, and that an activity query returns the right clip.

**Acceptance Scenarios**:

1. **Given** a multi-scene trip video, **When** indexed, **Then** the description reflects the distinct scenes (not just the first frame) and at least one timestamped segment is recorded.
2. **Given** a single continuous home clip, **When** indexed, **Then** it still produces a meaningful description (the system does not degenerate to one frame).
3. **Given** a clip where text appears (a sign, a title card), **When** indexed, **Then** that text is captured and is searchable.

---

### User Story 3 - Safe, unattended, resumable batch indexing (Priority: P2)

The operator starts an indexing run and walks away. The run processes only what still needs work, bounds its disk use, and manages memory automatically — freeing system memory only when it is actually low, and restoring everything afterward — so it neither crashes the machine nor disrupts the running photo server unnecessarily. If the run is interrupted, the next run continues where it left off.

**Why this priority**: The library is large and the home server is memory-constrained; without automatic resource management and resumability the feature is not usable in practice.

**Independent Test**: Start a run, interrupt it mid-way, and re-run; verify completed assets are not re-processed and the run finishes. Simulate low available memory; verify the run frees memory automatically, completes without an out-of-memory failure, and the photo server is running again afterward. Verify staging disk never exceeds the configured budget.

**Acceptance Scenarios**:

1. **Given** a run interrupted after some assets are done, **When** the operator re-runs, **Then** already-completed assets are skipped and the run completes.
2. **Given** the machine is low on free memory at the start of a heavy phase, **When** the run proceeds, **Then** it automatically frees enough memory (least-disruptive first), completes without an out-of-memory crash, and restores the photo server afterward.
3. **Given** a default run with ample memory, **When** it proceeds, **Then** it does **not** disrupt the photo server unnecessarily.
4. **Given** an asset changed in the source after it was indexed, **When** the operator re-runs, **Then** only the changed asset is re-processed.
5. **Given** any single asset fails to process, **When** the run continues, **Then** the failure is recorded and the rest of the batch still completes.

---

### User Story 4 - Environment readiness & missing-preview remediation (Priority: P3)

Before doing heavy work, the operator can confirm the environment is ready. A run will not start against a half-installed environment — it stops immediately and tells the operator exactly what to install or start. Assets that cannot be fetched because they lack a usable image are not silently dropped: they are recorded distinctly and the operator gets an actionable report on how to make them indexable, then a later run picks them up.

**Why this priority**: Prevents wasted long-running batches and silent data gaps; turns setup failures into clear, fixable messages.

**Independent Test**: Run the readiness check with a deliberately missing dependency and verify it fails fast with a specific fix instruction. Run against assets known to lack a usable image and verify they are reported with remediation steps rather than counted as successes or hard errors.

**Acceptance Scenarios**:

1. **Given** a required component is missing, **When** the operator starts a run (or the readiness check), **Then** it stops within seconds and names the missing component and the exact remediation, before any heavy work begins.
2. **Given** the operator intends to index only one media type, **When** readiness is checked, **Then** only the components needed for that media type are required (the other type's components are not demanded).
3. **Given** assets without a usable image, **When** a run completes, **Then** those assets are reported separately (count + identifiers + remediation steps) and a subsequent run re-attempts them once remediated.

---

### Edge Cases

- **No usable preview/image** for an asset → recorded as a distinct, non-error status; reported with remediation; never silently skipped.
- **Video with no detectable scene changes** (single continuous shot) → falls back to evenly-spaced frames so it still yields a description.
- **Very long video** that exceeds the per-pass frame budget → summarised by combining results across windows rather than failing.
- **Insufficient memory** for the current phase → memory is freed automatically (least-disruptive first); if it still cannot proceed and the policy forbids disruption, it stops with a clear message rather than crashing.
- **Interruption / crash mid-run** → progress is durable; the next run resumes without redoing completed work.
- **Changed source asset** → detected and re-processed; unchanged assets are not.
- **Processing failure on one asset** (timeout, resource error) → recorded as retryable; never aborts the batch.
- **Re-run with no changes** → zero assets processed (idempotent).
- **On-screen text repeated across many video frames** → captured once (de-duplicated), not repeated.
- **Index loss on the working disk** → the index is derived/regenerable; a recent backup avoids re-doing expensive work.

## Requirements *(mandatory)*

### Functional Requirements

**Extraction & index (R097–R099, R101)**
- **FR-001**: System MUST generate, for each photo, a natural-language description of what is happening (activity, context, relationships), stored in a **single canonical language (English)**, keyed to the asset.
- **FR-002**: System MUST generate, for each video, a video-level description plus timestamped segment descriptions that allow locating *when* something happens.
- **FR-003**: System MUST extract visible on-screen text (OCR) from photos and videos and store it as a searchable field, de-duplicating text repeated across video frames.
- **FR-004**: System MUST store a semantic representation of each (English) description that enables meaning-based retrieval, including **cross-language queries** — a query in any household language (e.g. RU/UK) MUST match the English description without storing translations. The query MUST be embedded with the same multilingual representation used for descriptions.
- **FR-005**: System MUST make the index searchable both by meaning (semantic) and by exact text (names, on-screen text).
- **FR-006**: System MUST key every index entry to the source asset identifier and cache the source filter fields needed for downstream ranking (date, location, people identifiers, favourite flag) without re-deriving identity itself.
- **FR-007**: System MUST NOT attempt to identify specific named people from image content; "who" is resolved via the existing photo server's person identifiers.

**Batch execution, incremental, resilience (R100)**
- **FR-008**: System MUST run as a re-runnable batch that processes only assets not yet indexed, assets whose source changed, or assets whose extraction is from a superseded version.
- **FR-009**: System MUST persist progress durably so an interrupted run resumes without re-processing completed assets.
- **FR-010**: System MUST isolate per-asset failures: one asset's failure MUST NOT abort the batch; the failure MUST be recorded and be retryable.
- **FR-011**: System MUST bound working/staging disk usage to a configurable budget and reclaim staging space as it progresses.
- **FR-012**: System MUST allow scoping a run to a single media type (photos only or videos only) or all.
- **FR-013**: System MUST back up the index after a run so an index loss does not force re-doing the expensive extraction.

**Automatic resource governance**
- **FR-014**: System MUST manage memory automatically: before a heavy phase it MUST assess available memory against the phase's need and free memory only when actually low.
- **FR-015**: When freeing memory, the system MUST escalate least-disruptively (release only the resources the current phase does not need, then pause the photo server's services, then the virtualization layer) and MUST restore whatever it stopped after the phase.
- **FR-016**: System MUST load only the resources required for the current phase and MUST NOT require both media types' resources to be present at once.
- **FR-017**: System MUST provide a policy override to force resource-freeing, to forbid it (proceed if possible, otherwise stop with a clear message), or to decide automatically (default).

**Environment readiness & remediation**
- **FR-018**: System MUST verify, before heavy work, that the components required for the requested run are available, and MUST stop immediately with a specific remediation message if any are missing — scoped to the requested media type.
- **FR-019**: System MUST provide a one-step setup path that installs/prepares all required components and documents known environment pitfalls.
- **FR-020**: System MUST record assets lacking a usable image as a distinct status (neither success nor hard error) and produce an actionable remediation report; a later run MUST re-attempt them once remediated.
- **FR-021**: System MUST expose operator commands to: check readiness, run indexing, show status counts, produce the remediation report, retry failed/unremediated assets, and perform a quick search check of the index.

### Key Entities *(include if feature involves data)*

- **Asset index entry**: one record per source asset — its type (photo/video), processing status, description, extracted text, semantic representation, cached source filter fields (date/location/people/favourite), provenance (which extractor/version produced it), a change-detection fingerprint, and timestamps.
- **Video segment**: a timestamped slice of a video with its own short description and any on-screen text; many per video; enables moment-level retrieval.
- **Run record**: one per batch run — start/finish and outcome counts (done / no-usable-image / error / skipped) — the source for status and remediation reporting.
- **Index**: the durable store of all of the above, kept on fast local storage, periodically backed up to bulk storage; derived and regenerable from the source library.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a photo run, 100% of processable photos have a stored description and extracted-text field (or a recorded non-error status); none are silently skipped.
- **SC-002**: **Smoke-level (IMP-018):** a small set of known queries each return the correct asset via basic hybrid (text ∪ semantic) retrieval — a build-check that the stored descriptions/text/embeddings are usable. *(The tuned accuracy thresholds — meaning-based ≥80%, exact on-screen-text ≥90% — are validated in IMP-020 once fusion ranking exists.)*
- **SC-003**: **Smoke-level (IMP-018):** at least one cross-language query (different language than the stored description) returns the correct asset, confirming multilingual semantic retrieval works. *(The ≥80% cross-language threshold is validated in IMP-020.)*
- **SC-004**: Each indexed video yields a video-level description and at least one timestamped segment; multi-scene clips reflect more than one scene.
- **SC-005**: Re-running with no source changes processes zero assets (fully idempotent); after a changed asset, exactly the changed asset is re-processed.
- **SC-006**: An interrupted run, when re-run, re-processes zero already-completed assets and goes on to finish.
- **SC-007**: A run started when free memory is below the phase's need completes without an out-of-memory failure, and the photo server is running again at the end.
- **SC-008**: With ample memory, a default run leaves the photo server running throughout (no unnecessary disruption).
- **SC-009**: Working/staging disk never exceeds the configured budget at any point during a run.
- **SC-010**: Starting a run against a missing required component stops within ~5 seconds with a specific remediation message, before any heavy work.
- **SC-011**: Assets lacking a usable image are 100% reported (count + identifiers + remediation), and re-appear as processed after remediation + re-run.

## Assumptions

- The existing self-hosted photo server (Immich) is the source of assets and of identity/face data, is reachable during the fetch phase, and exposes per-asset images and the cached filter fields used for ranking. Identity is never re-derived from pixels.
- The host is the project's Apple M4 Mac Mini (24 GB memory) with ample fast local storage for the index and a bounded staging area; bulk storage is available for index backup. Specific model, runtime, sampling, and storage choices are fixed in the technical design.
- The local AI models needed for description, text extraction, and semantic representation can be installed/prepared on this host; the one-step setup path provisions them. (See `docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md`.)
- The index is **derived and regenerable** from the source library; loss is recoverable by re-running (mitigated by backups).
- Delivery is phased: photos baseline first (US1), then video (US2), then automatic resource governance hardening (US3); readiness/remediation (US4) is built alongside from the start.
- **Out of scope** (separate PRD items): fusion ranking that combines these signals and the multilingual concept-search swap (IMP-020); audio understanding — speech/sound (IMP-019); image-quality and face-expression signals (IMP-021/IMP-022). This feature produces and stores the signals; ranking that *combines* them is IMP-020.

## Dependencies

- Source photo server (Immich) reachable with valid credentials during the fetch phase.
- Ability to pause/resume the photo server and its virtualization layer on the host (for automatic memory governance).
- The approved technical design `docs/superpowers/specs/2026-06-13-imp-018-vlm-captioning-design.md` (architecture, models per case, schema, sampling, governor) and PRD IMP-018 (R097–R101).
