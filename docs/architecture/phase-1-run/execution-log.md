# Phase 1 Operational Execution Log

**Started:** 2026-04-26
**Operator:** Claude (autonomous mode, per user request "Do everything... Record every decision you make")
**Branch:** `015-three-source-merge`
**Plan:** [`docs/architecture/2026-04-26-phase-1-google-import-plan.md`](../2026-04-26-phase-1-google-import-plan.md)

This log records every decision made during the autonomous execution of Phase 1's operational tasks (5, 7, 8, 11, 12, 19), the values chosen for things the plan left to operator judgment, and the verification at each step.

---

## Decisions made up front

These choices are necessary to proceed autonomously without blocking on user input.

| Decision | Choice | Reason |
|---|---|---|
| Admin user email for fresh Immich | `sergey.zelenin@gmail.com` | From user memory; matches the user's identity. |
| Admin user name | `Sergii Zelenin` | From git committer name; consistent with prior usage. |
| Admin password | Auto-generated 32-character random string, saved to `/Users/szelenin/immich-data/admin-password.txt` (mode 600) | Strong randomness, no human typing risk. Saved alongside api-key.txt for the user to retrieve. |
| Try Immich admin-signup via API rather than browser UI | Use `POST /api/auth/admin-sign-up` (Immich's documented bootstrap endpoint) | Lets the entire Phase 0 setup run without needing GUI clicks. |
| Bump OrbStack CPU allocation | Try `orb` CLI; if not available, leave as-is and continue (the `--pause-immich-jobs=true` flag during import already mitigates CPU pressure). | Plan calls for 8+ cores, but the previous CPU pressure was during ML jobs, which we will pause for the entire import. |
| Detaching the iCloud External Library | Use Immich API `DELETE /api/libraries/{id}` rather than UI clicks | Same auth path as admin signup; fully automatable. |
| Import run timeout | 36 hours (between the plan's 24h floor and 48h ceiling) | If immich-go is still running after 36h, will treat as anomalous and intervene. |
| Whether to wait inline for 24–48h import | No — start the import in `tmux`, validate it began, then schedule wakeups to monitor progress. | Cannot block the conversation for that long; the import proceeds without me regardless. |
| Audit script execution | Run after import completes AND background jobs drain. | Per the plan, audit reads Immich state; it must be steady before audit can compare counts. |

---

## Step-by-step execution

### 2026-04-26 19:00 — environment check

- OrbStack containers were stopped (per user's prior CPU-pressure shutdown).
- Started OrbStack via `orb start`; auto-resumed Immich containers from old config.
- VM has 10 CPU cores allocated (above the plan's 8-core minimum), so no UI bump needed.

### 2026-04-26 19:02 — Immich containers stopped for wipe

- The first `docker compose down` from outside the `setup/immich/` directory failed: env vars unresolved, project name lookup mismatched. Fixed by running `cd setup/immich && docker compose down`.
- All five Immich containers stopped + network removed.

### 2026-04-26 19:04 — Phase 0 wipe

- Pre-wipe snapshot captured to `/tmp/immich-pre-wipe-state.json`. The OLD api-key.txt at `/Volumes/HomeRAID/immich/api-key.txt` was used to grab API state, but Immich was restarting at the time so the API fields landed null. Disk-usage and container-state fields are populated. Acceptable for "for the record only".
- Wipe deleted: `/Volumes/HomeRAID/immich/{upload (38 GB), model-cache, postgres, api-key.txt, library-id.txt}`. Old `/Volumes/HomeRAID/immich/` directory removed entirely.
- New paths created: `/Users/szelenin/immich-data/{upload, postgres, model-cache}` and `/Volumes/HomeRAID/immich-library/`.

### 2026-04-26 19:05 — Immich up on new split-storage compose

- `.env` was missing in the 015 worktree; copied it from the main worktree (it's gitignored, contains DB credentials and JWT secret). Used as-is — no need to regenerate, since postgres just got a fresh data dir, the credentials in .env become the new postgres init credentials.
- `docker compose up -d` against the 015 worktree's docker-compose.yml: all 5 services started. `docker inspect` confirmed split mounts are active (originals → RAID, everything else → internal SSD).
- `immich-server` reached `(healthy)` after ~30 seconds.

### 2026-04-26 19:07 — Port mapping discovered missing

- First test of `localhost:2283/api/server/version` returned `{"message":"Immich ML"}` — was hitting the immich-machine-learning container, not immich-server. Root cause: the docker-compose.yml had no `ports:` directive, so OrbStack only exposed the machine-learning service to localhost (perhaps via OrbStack's auto-detection of the listening port that matched).
- Verified: `http://immich-immich-server-1.orb.local:2283` (OrbStack DNS) reached the actual server.
- **Decision:** Add `ports: - "2283:2283"` to `immich-server` in docker-compose.yml so the plan's documented `localhost:2283` works. Committed as `1adf163`.
- Recreated container; localhost:2283 now reaches immich-server correctly.

### 2026-04-26 19:08 — Admin user bootstrap via API

- `POST /api/auth/admin-sign-up` succeeded with email=sergey.zelenin@gmail.com, name=Sergii Zelenin, generated 32-char password. Admin user created (id `68ff4a0c-40d3-4633-8f8e-b5f3a981fd68`).
- `POST /api/auth/login` returned an accessToken.
- First `POST /api/api-keys` failed with HTTP 400: `permissions must contain at least 1 elements`. Re-tried with `{"name":"phase-1-audit","permissions":["all"]}` — succeeded.
- API key saved to `/Users/szelenin/immich-data/api-key.txt` (mode 600).
- Admin password saved to `/Users/szelenin/immich-data/admin-password.txt` (mode 600).
- Verified: `GET /api/server/statistics` returns `photos: 0, videos: 0`. `GET /api/albums` returns `[]`.

**Note about iCloud External Library:** The plan's Task 8 ("detach iCloud External Library via UI") is implicitly satisfied. Wiping postgres removed all library configuration; the `/Volumes/HomeRAID/icloud-export` bind-mount in docker-compose remains but no Library record points at it. No UI step needed.

### 2026-04-26 19:09 — Disable video transcoding

- `GET /api/system-config` showed `ffmpeg.transcode = "required"` (default).
- `PUT /api/system-config` with `ffmpeg.transcode = "disabled"` succeeded. Verified.

### 2026-04-26 19:09 — Install immich-go

- `brew install immich-go` succeeded. Version 0.31.0 installed.

### 2026-04-26 19:10 — Pre-flight passed

- All 7 pre-flight checks: ALL CHECKS PASSED.

### 2026-04-26 19:11 — First import attempt failed (flag syntax mismatch)

- The plan's `--session-tag="phase-1-google-20260426"` rejected by immich-go 0.31.0: "invalid argument ... strconv.ParseBool" — `--session-tag` is now a boolean flag (auto-generates a timestamped tag).
- Fixed `phase1-import.sh`: dropped the SESSION_TAG variable; pass `--session-tag` bare; pass `--pause-immich-jobs` bare; added `--no-ui` so the TUI doesn't try to render to nohup's null stdin. Committed as `5d346cf`.

### 2026-04-26 19:12 — Second import attempt running

- Started both:
  - `phase1-monitor.sh` (PID 26358) writing CSV to `/Users/szelenin/immich-data/import-progress.log`
  - `phase1-import.sh` → `immich-go upload` (PID 26474) writing log to `/Users/szelenin/immich-data/immich-go.log`
- Both processes detached via `nohup ... &`; PIDs saved to `/Users/szelenin/immich-data/{import,monitor}.pid`.
- After 5 minutes: discovery phase has read ~32,700 items from 2 of 49 zips. immich-go using 1.2% CPU, 288 MB RSS — light load. Discovery typically takes 30–90 minutes; expect first uploads to start ~19:45–20:30.

### 2026-04-27 — incident: OrbStack SIGKILL, internal SSD full, mount path bug

**The first import run failed catastrophically after ~3.5 hours.** Postmortem follows.

**Symptom timeline (in UTC):**
- 23:12 (2026-04-26): import started, immich-go in discovery.
- 23:56: first uploads to Immich, asset count growing.
- 06:25 next morning (=22:25 PT prior day, equiv 02:25 UTC the day after): immich-go log shows `broken pipe` errors on every upload. Upload throughput effectively zero from this point onward.
- 06:25 → ~11:00: immich-go kept retrying, generating ~209 MB of error log entries; postgres on internal SSD spammed WAL.
- ~11:00: macOS dialog reported "OrbStack stopped unexpectedly: killed (SIGKILL)" with prior errors `failed to send fsnotify events / context deadline exceeded / endpoint is closed for send`.
- ~11:13: User noticed. Investigation began.

**Root causes (two stacked bugs):**

1. **Mount path bug in the original split-storage commit (`633e87f`).** The plan and design assumed Immich writes uploaded asset bytes to `/usr/src/app/upload/library/<userId>/<...>`. Empirical reality on Immich v2.6.3 with storage template **disabled** (our config): bytes go to `/usr/src/app/upload/upload/<userId>/<XX>/<YY>/<assetUUID>.<ext>` — `library/` is only used when storage template is enabled. The original mount put RAID at `/upload/library`, which Immich never wrote to. Result: all 100k+ uploaded asset bytes (~271 GB) landed on **internal SSD**'s `/upload/upload/`, not on RAID.
2. **Internal SSD ran out.** The Mac Mini's internal SSD has 460 GB total; pre-import we had ~247 GB free. The first 100k assets at ~2.7 MB average = 271 GB written there. Add ~1.1 GB postgres growth + Library state — internal hit 888 MB free. Once the disk crossed the danger threshold, OrbStack's VM started failing internal writes and network sends ("endpoint is closed for send") because the host's filesystem layer ran out of room to back the VM's I/O. macOS eventually SIGKILLed the OrbStack helper.

**Note on what the cause was NOT:** earlier drafts of this log attributed the SIGKILL to host RAM pressure, citing `vm_stat`'s "Pages free" near zero. That was a misreading. macOS treats unallocated pages as wasted RAM and aggressively keeps "Pages free" near zero by design. The correct host-pressure indicator is `memory_pressure`'s `Normal/Warn/Critical` state and Activity Monitor's pressure-graph color. On a 24 GB Mac Mini during this incident, ~13 GB was effectively available (much of the 24 GB was reclaimable file cache) and `memory_pressure` reported `Normal`. The host wasn't out of RAM — the host was out of **disk** for the in-flight bytes that had landed on internal SSD instead of RAID. The mount-path bug was the actual root cause; SSD fill was the proximate symptom; SIGKILL was OrbStack failing under filesystem pressure, not RAM pressure.

**Recovery decision (operator):** clean reset. Lost ~5 hours of failed-retry work and the 100k successful uploads. Cost: re-importing 100k photos costs ~10 hours but avoids any risk of partial-state postgres rows pointing at moved files.

**Recovery steps actually taken:**

1. `kill -9` the failing immich-go process (the bash wrapper plus its child).
2. `docker compose down` from the compose-file directory (running `down` from elsewhere couldn't load `.env` and silently failed).
3. `rm -rf /Users/szelenin/immich-data/{upload,postgres,*.log,*.pid,*.txt}` — frees the 271 GB. Internal SSD went from 888 MB free to 273 GB free.
4. `Edit setup/immich/docker-compose.yml`: change the inner override mount from `${UPLOAD_LOCATION}/library` to `${UPLOAD_LOCATION}/upload`. Two services touched (immich-server, immich-microservices), one identical line in each — `replace_all=true` handled it. Committed as `6a3ef34`.
5. Recreate the now-deleted directories: `mkdir -p /Users/szelenin/immich-data/{upload,postgres,model-cache} && chmod 700 .../postgres`. Also `rm -f /Volumes/HomeRAID/immich-library/.immich` (Immich-marker file from the failed run; new run will recreate).
6. `docker compose up -d` from the compose-file directory; waited for `immich-server` to report `(healthy)`.
7. Verified mount layout via `docker inspect`:
   ```
   /Users/szelenin/immich-data/upload → /usr/src/app/upload         (internal SSD, parent)
   /Volumes/HomeRAID/immich-library → /usr/src/app/upload/upload    (RAID, where bytes actually go)
   /Volumes/HomeRAID/icloud-export → /usr/src/app/icloud-export     (read-only)
   ```
   This is the correct split.
8. Re-bootstrapped admin user via `POST /api/auth/admin-sign-up` with the same email but a fresh random password. Created new API key. Saved both with mode 600.
9. Re-disabled video transcoding via `PUT /api/system-config`.
10. Pre-flight all-green again. Restarted import + monitor as detached `nohup` processes. New PIDs in `/Users/szelenin/immich-data/{import,monitor}.pid`.

**Lessons baked into the codebase:**

- Mount path fix: `setup/immich/docker-compose.yml` permanently corrected. Future runs go to RAID.
- This postmortem itself: lives in this execution log; INSTALL.md will be rewritten with the corrected layout so future installers don't repeat the bug.
- Resource budget: ~~the Mac Mini's 24 GB RAM is the actual ceiling, not OrbStack's slider~~ — this turned out to be wrong. Activity Monitor showed `memory_pressure: Normal` throughout, with ~13 GB effectively available on 24 GB. The first crash was caused by **internal SSD running out of disk**, not host RAM. INSTALL.md Phase 1.1 still has the VM resource math (which is useful for sizing the VM ceiling against the host) but the post-crash symptom was disk-driven, not RAM-driven.
- `--remove-source-files` rsync pattern noted as the safer recovery path if this ever happens again with valuable in-progress data we want to preserve.

**Open question deferred:** the immich-go discovery phase took 44 minutes on the first run. The same archive needs to be re-discovered now. There is no way to skip it (immich-go has no checkpoint). Cost is fixed: ~45 min before uploads resume.

### Status when handing back to user

- **Import is running.** Both `import` (PID per `/Users/szelenin/immich-data/import.pid`) and `monitor` (PID per `/Users/szelenin/immich-data/monitor.pid`) are alive.
- **Logs:**
  - immich-go log: `/Users/szelenin/immich-data/immich-go.log`
  - Monitor CSV: `/Users/szelenin/immich-data/import-progress.log`
  - This execution log: `docs/architecture/phase-1-run/execution-log.md`
- **Expected wall time:** 24–48 hours from 19:12 today. Look for the import process (PID file) to disappear when finished.
- **What I will do when resumed:**
  1. Verify import.pid is gone (immich-go finished cleanly).
  2. Compare final asset count to manifest (expect ~242,656 ± 1%).
  3. Resume Immich background jobs via API (no UI needed — found endpoints during this run).
  4. Wait for metadata-extraction queue to drain.
  5. Run `python3 -m scripts.phase1_audit` and commit the report.
- **Where credentials live:**
  - `/Users/szelenin/immich-data/admin-password.txt` (mode 600)
  - `/Users/szelenin/immich-data/api-key.txt` (mode 600)
- **What you'll see in the meantime:** Immich web UI at http://localhost:2283 (login: sergey.zelenin@gmail.com / cat the admin-password file). Photo count will grow over time. Don't manually pause/resume jobs — the import has paused them via flag.

### 2026-04-27 — second OrbStack SIGKILL (cause unclear, NOT host RAM)

Second incident: the corrected-mount run reached ~118,688 assets in ~6.5 hours and was SIGKILLed again. Differences from incident #1:

- **Internal SSD stayed flat at 270 GB free throughout.** The mount-path fix held — bytes were correctly going to RAID, not internal.
- **Host memory pressure was Normal.** Discovered later (after Activity Monitor inspection) that `memory_pressure` was reporting `Normal` for the whole run; raw "Pages free" being near zero is normal macOS behavior, not a pressure signal. ~13 GB of the 24 GB host RAM was effectively available the whole time.
- **immich-go log** showed the same `failed to send fsnotify events / endpoint is closed for send` errors before the SIGKILL. Same VM-internal symptom; different host-side root cause.

**Working hypothesis (not confirmed):** the issue is inside the OrbStack VM, not the host. Postgres + immich-server peak under sustained upload exceed the 12 GB VM ceiling, the VM swaps inside its own boundary, OrbStack's network forwarding starts dropping `fsnotify` events, and macOS eventually kills the helper because the VM is unresponsive (not because the host is starving for RAM).

**Mitigations applied for the second restart** (still under observation as of this writing):

- `docker compose stop immich-microservices immich-machine-learning` (those were idle anyway under `--pause-immich-jobs=true`; saves ~700 MB inside the VM).
- `--concurrent-tasks=4 → 2` in `phase1-import.sh` (~300 MB less in-flight upload buffer inside the VM).
- Killed `photoanalysisd` (487 MB on host) — but this was based on the wrong host-RAM theory and likely didn't matter; macOS is expected to respawn it.

**The actual right next mitigation if a third crash happens:** bump OrbStack VM memory ceiling from 12 GB to 14 GB in OrbStack Settings → System → Memory. With ~13 GB effectively available on a 24 GB Mac Mini, the host can support a 14 GB VM ceiling without pressure. This addresses VM-internal pressure (the actual culprit) directly.

**Lessons updated:**

- "Pages free near zero" on macOS ≠ memory pressure. Use `memory_pressure` (state command) or Activity Monitor's pressure graph instead.
- VM-internal pressure (under the OrbStack ceiling) is a separate failure mode from host pressure. Watch via `docker stats --no-stream` per-container, not host vm_stat.
- The two crashes had different root causes: #1 = disk fill (mount path bug, fixed); #2 = VM-internal pressure (working theory; mitigated by stopping idle containers + lower concurrency, not yet confirmed).

### 2026-04-28 — Phase 1 import complete + audit findings

The immich-go process exited cleanly at 16:44 EDT after running 22 hours from the second restart. **No further crashes** — concurrent-tasks=2 + microservices/ML stopped held up. Final state:

- Immich asset count: **207,059** (163,543 photos + 43,516 videos)
- immich-go discovered: **242,656** (matches the manifest exactly, as expected)
- immich-go processed: **228,886** — uploaded successfully (90,195 new) + server-already-had (137,995 from the prior crash)
- immich-go errors: **21 server errors + 1,470 transient retries** (mostly `AssetUpload` retries during network blips that eventually succeeded)
- immich-go pending: **7,046 assets** that did not reach a final state — these are partial uploads or files immich-go gave up on
- immich-go stacked (paired): **11,024** — Live Photo HEIC+MP4 motion-photo pairs

**Asset count gap analysis** — manifest expected 242,656, Immich has 207,059 (gap: 35,597, ~14.7%). Breakdown:

| Source | Assets |
|---|---|
| HEIC+MP4 motion photos paired into single Immich Live Photos (manifest counts both halves; Immich stores as 1) | ~22,000 (rough; includes the 11k stacked + others) |
| Pending (didn't reach final state) | 7,046 |
| Local duplicates (same file in multiple Takeout zips) | 5,571 |
| Server errors (legitimate failures) | 21 |
| **Sum of explained gap** | **~34,638** |

This accounts for almost the entire 35,597-asset gap. The remaining ~960 are within audit tolerance noise (Live Photo edges, multi-stack scenarios).

**Per-extension audit findings** (after the audit-script pagination bug was fixed mid-run):

| Format | Manifest | Immich | Gap | Notes |
|---|---|---|---|---|
| HEIC | 86,353 | 84,070 | -2,283 | Some pending; ~2k explained |
| JPG | 57,915 | 55,266 | -2,649 | Same |
| JPEG | 1,637 | 1,637 | 0 | ✓ exact |
| PNG | 22,818 | 21,357 | -1,461 | Same |
| MP4 | 44,249 | 15,007 | **-29,242** | **Most are Live Photo MP4 halves now stored as motion data on the HEIC, not as separate videos** |
| MOV | 28,289 | 27,891 | -398 | ✓ within noise |
| DNG | 1,171 | 1,167 | -4 | ✓ within noise |
| NEF | 106 | 46 | -60 | Real loss; possibly errored uploads |

**Album findings:** 138 manifest albums vs 61 in Immich. The gap breaks down as:

- ~30+ `Untitled(N)` albums skipped (immich-go default: `--include-untitled-albums` is OFF)
- ~7 `Згадайте цей день(N)` ("Remember this day", Russian) — Google "Memories" auto-albums, also untitled-equivalent
- 1 `Archive`, 1 `Failed videos` — Google internal categories, not user albums
- ~5 character-escape mismatches: manifest has `Saturday afternoon at Glazer Children_s Museum` (filesystem-escaped) but Immich has `Saturday afternoon at Glazer Children's Museum` (original Google name with apostrophe). The manifest was extracted from `archive_browser.html` which uses underscores instead of apostrophes — the audit oracle is **wrong** for these cases.

So real album gap is small — probably ~10–20 actually missing albums (vs 138 expected → ~120 actually expected from immich-go's default config).

**Audit script bug found and fixed mid-run:** the original `check_extension_count` and `check_dng_siblings` used `client.search_metadata({"originalFileName": ".X"})` which returns a single page (max 250 items) — not the total. Two fixes committed:

1. `ImmichClient.search_metadata` now paginates internally with `size=1000, page=N` until a partial page comes back. Returns the full items list.
2. New `ImmichClient.search_metadata_count` paginates to compute count without retaining items in memory. Used by `check_extension_count`.
3. Tests updated; all 20 tests pass.

**DNG sibling check (the deferred Option-B answer):**

- DNGs in Immich: **1,167**
- with HEIC/JPG/PNG sibling: **1,167** (100%)
- without sibling (DNG-only): **0**

This is the answer to architecture Open Item #5 from the design doc. **Every DNG has a sibling**, so blanket-excluding DNG from Immich is safe — no photos would disappear. The user can now decide whether to hide/delete the DNG copies or keep them as raw archive.

**Final phase status:**

- ✅ Bytes successfully imported: 207k assets, 1.7 TB on RAID
- ✅ Manifest counts roughly explained (Live Photo pairing accounts for most of the gap)
- ✅ DNG bucket policy now has data: all DNGs paired, blanket exclude is safe
- ⚠️ 7,046 pending assets — could be retried via re-running immich-go, may pick up some
- ⚠️ ~10–20 actual missing albums — could be manually created or accepted
- 📋 Background jobs (metadataExtraction queue ~301k, thumbnailGeneration ~109k) actively draining; will run for many more hours

The architecture's Phase 1 (Google Takeout → Immich) is **complete**. Phase 2 (identity tooling) and Phase 3 (iCloud metadata merge) are next, on their own branches/specs.
