# IMP-018 — Error Taxonomy & Remediation Ladder (design)

**Date**: 2026-06-14
**Feature**: extends `016-vlm-captioning` (US4 — readiness & remediation)
**Status**: approved (brainstorm) → pending implementation plan

## Problem

The understanding-layer indexer isolates per-asset failures (`status=error`, batch
continues) but records only a free-text `error` message. There is no way to:

- group failures by *cause*,
- know *what to change* to fix a class of failures, or
- track *what was already tried* on an asset.

Concretely: a live photo run left 3 of 5 assets `error` with empty model output.
Investigation showed the real cause was `finish_reason=length` — `qwen3-vl` (a
reasoning model) spent the entire available context (`num_ctx=4096`, ~2.8k of it
the image) emitting hidden `reasoning` tokens and never produced the JSON answer.
The fix (more context, and/or disabling thinking) is *cause-specific* — which is
exactly the knowledge the system currently throws away.

## Goal

Turn opaque failures into a **diagnose → escalate → record** loop:

1. Every failure is stored with a **typed error code** + the **raw reason**
   (`finish_reason`, token usage).
2. A **static remediation ladder** maps each code to an ordered list of actions.
3. An operator/AI-driven **`remediate`** pass applies the *next* rung to the
   still-failing assets, re-runs them, and **records what was applied**.
4. When an asset's ladder is exhausted and it still fails, it is flagged for
   manual intervention (never re-queued forever).

Non-goals: automatic in-run self-healing (decided against — keeps the batch
predictable); folding `no_preview` into this ladder (it keeps its own Immich
preview-regeneration remediation from US4).

## Decisions (from brainstorm)

- **Operator/AI-driven**, not automatic in-run. The run records categorized
  errors; a separate `remediate` pass (re-)invoked by the operator or AI escalates.
- **Typed exceptions carry the code** (assigned at the point of failure), not
  derived by message pattern-matching.
- **Static ladder in code**; per-asset error code + applied-step history in the DB.
- **One rung per `remediate` pass** (each pass recorded separately); re-invoke to
  escalate. Auto-escalate-through-the-whole-ladder is a possible later flag (YAGNI now).

## Error taxonomy

Granular codes, derived so each maps cleanly to one ladder. `finish_reason` is the
discriminator for the "no usable content" family:

| Code | Derived from | Ladder-remediable |
|---|---|---|
| `MODEL_TRUNCATED` | `finish_reason=length` (ran out of context) | yes — context-first |
| `MODEL_EMPTY` | empty content + `finish_reason=stop` (produced nothing) | yes — thinking-first |
| `PARSE_ERROR` | non-empty but unparseable JSON | yes |
| `TIMEOUT` | request timed out | yes |
| `MODEL_UNREACHABLE` | transport/connection to Ollama failed | no → manual (service issue) |
| `FETCH_ERROR` | Immich download errored (not missing-preview) | retry as-is |
| `UNKNOWN` | uncategorized | no → manual |

The chain: raw `finish_reason` (stored) → granular `error_code` (stored, drives the
ladder) → ladder picks the action. The code is the *actionable* category; the raw
reason + token counts are the *evidence*.

## Data model changes

### `assets` (new columns)
| Column | Type | Notes |
|---|---|---|
| `error_code` | TEXT | the typed code; NULL unless `status=error` |
| `remediation_level` | INTEGER NOT NULL DEFAULT 0 | rungs already applied (denormalized for fast escalation queries) |
| `error_detail` | TEXT (JSON) | raw evidence: `{finish_reason, prompt_tokens, completion_tokens}` — for audit and ladder tuning |

`error` (free-text message) stays.

### `remediation_attempts` (new child table — the applied-step audit trail)
| Column | Type | Notes |
|---|---|---|
| `asset_id` | TEXT FK → assets(asset_id) ON DELETE CASCADE | |
| `run_id` | INTEGER | the remediation run that made this attempt |
| `pass_no` | INTEGER | 1-based attempt index for this asset |
| `error_code` | TEXT | code being remediated |
| `action_json` | TEXT (JSON) | the action applied, e.g. `{"label":"ctx-8k","num_ctx":8192}` |
| `outcome` | TEXT | `done` \| `error` (result of the re-run) |
| `created_at` | TEXT | ISO timestamp |
| PK | (`asset_id`, `pass_no`) | |

`remediation_level` on the asset equals `COUNT(*)` of its attempts (kept
denormalized so escalation selection avoids a join).

## The ladder (static, in code) — `caption/remediation.py`

```python
class Action:
    label: str            # human/audit label, e.g. "ctx-8k"
    params: dict          # captioner overrides: num_ctx / no_think / timeout / max_tokens

REMEDIATIONS: dict[ErrorCode, list[Action]] = {
    ErrorCode.MODEL_TRUNCATED: [
        Action("ctx-8k",   {"num_ctx": 8192}),
        Action("ctx-16k",  {"num_ctx": 16384}),
        Action("no-think", {"num_ctx": 16384, "no_think": True}),
    ],
    ErrorCode.MODEL_EMPTY: [
        Action("no-think", {"no_think": True}),
        Action("retry",    {}),
    ],
    ErrorCode.PARSE_ERROR: [
        Action("no-think", {"no_think": True}),
    ],
    ErrorCode.TIMEOUT: [
        Action("timeout-2x", {"timeout": 600}),
    ],
    ErrorCode.MODEL_UNREACHABLE: [],   # empty ladder → straight to manual
    ErrorCode.FETCH_ERROR: [Action("retry", {})],
    ErrorCode.UNKNOWN: [],
}

def next_action(code, level) -> Action | None:
    ladder = REMEDIATIONS.get(code, [])
    return ladder[level] if level < len(ladder) else None   # None = exhausted
```

## `remediate` command — `index_cli.py`

`remediate [--code CODE] [--limit N] [--dry-run]` (operator/AI-driven, one rung/pass):

1. Group `status=error` rows by `error_code` (shared with `report`).
2. Select rows where `next_action(code, remediation_level)` is not None (rungs remain),
   optionally filtered to `--code` and capped by `--limit`.
3. Per asset: `action = next_action(code, level)` → re-run **the same caption pipeline
   with the action's param overrides** → write a `remediation_attempts` row
   (`pass_no = level+1`, action, outcome) and bump `remediation_level`.
   - success → `status=done`, `error*`/`error_code` cleared.
   - still failing → stays `error` (and may carry a new `error_code`/`error_detail`
     if the failure cause changed); next pass escalates.
4. Rows where `next_action(...)` is None and still `error` → **exhausted**: reported
   separately as needing manual intervention; never re-queued.
5. Pass summary recorded in `runs`.

`report` is enriched to print, per code: count, sample IDs, and the **next action that
would be applied** (`next_action`), plus a separate **exhausted/manual** bucket.

`no_preview` is untouched here — it keeps its own status and Immich preview-regeneration
remediation (US4 FR-020).

## Implementation implications

- **Switch the photo client to Ollama's native `/api/chat`.** The current
  OpenAI-compatible `/v1/chat/completions` endpoint does not expose `num_ctx` or a
  thinking toggle. `/api/chat` accepts `"options": {"num_ctx": N}` and `"think": false`,
  and returns the fields we need. The captioner must **surface `finish_reason` + token
  usage** (not just content) so failures classify into the right code.
- **Thread an `options`/overrides dict** through `caption(...)` → `_build_payload(...)`
  so a remediation pass can inject `num_ctx` / `no_think` / `timeout` per re-run.
- The immediate live-run fix (raise `num_ctx`, `/no_think`) is simply **rung 0/1 of the
  `MODEL_TRUNCATED` ladder** — no separate one-off patch.

## Testing (TDD, per constitution)

- **Unit**
  - classification: `finish_reason=length`→`MODEL_TRUNCATED`; empty+`stop`→`MODEL_EMPTY`;
    non-empty unparseable→`PARSE_ERROR`; transport→`MODEL_UNREACHABLE`; timeout→`TIMEOUT`.
  - ladder: `next_action` returns the right rung by level; returns None when exhausted.
  - `remediate` orchestration (mocked model): a `MODEL_TRUNCATED` asset gets `ctx-8k`
    on pass 1, records an attempt, bumps level; second pass applies `ctx-16k`; an
    exhausted asset is skipped and flagged.
  - DB: new columns round-trip; `remediation_attempts` insert + history query;
    `error_detail` JSON stored/parsed.
- **e2e (faked model):** an asset that fails pass 0 then succeeds once the override is
  present → ends `done` with a 2-row attempt history; `report` shows the exhausted
  bucket correctly for a no-ladder code.

## Scope & sequencing

Folds into `016-vlm-captioning` as added US4 tasks (enriches `report`; adds
`remediate`; adds the data-model columns + `remediation_attempts` table; refactors the
photo client to `/api/chat` with `options`). Not a new feature number. Backward
compatible: `error_code`/`error_detail` are nullable; existing `error` rows simply have
no code until they next fail through the new path.
