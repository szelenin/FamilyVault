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
