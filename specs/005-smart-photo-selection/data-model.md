# Data Model: Smart Photo & Video Selection

## Project File (replaces scenario.json)

```json
{
  "id": "2026-03-31-miami-trip-march-2026",
  "title": "Miami Trip March 2026",
  "request": "Build a clip of our recent trip to Miami. Speed boat, vizcaya garden, sunset must have",
  "state": "searching | selecting | previewing | approved | generated",
  "created_at": "2026-04-08T00:00:00Z",
  "updated_at": "2026-04-08T00:00:00Z",

  "search_params": {
    "queries": ["miami trip", "speed boat", "vizcaya garden", "sunset"],
    "date_range": { "after": "2026-03-28", "before": "2026-04-02" },
    "city": "Miami",
    "person_names": []
  },

  "must_haves": [
    {
      "keyword": "speed boat",
      "search_variations": ["speed boat", "speedboat", "boat ride"],
      "selected_asset_id": "uuid-...",
      "candidates": ["uuid-1", "uuid-2", "uuid-3"]
    }
  ],

  "candidate_pool": [
    {
      "asset_id": "uuid-...",
      "type": "IMAGE",
      "filename": "IMG_7305.HEIC",
      "mime_type": "image/heic",
      "taken_at": "2026-03-31T14:30:00Z",
      "width": 4032,
      "height": 3024,
      "city": "Miami",
      "thumbhash": "mxgOFQJvh1uIeJmYeHd4dyl6gLMH",
      "face_count": 2,
      "description": "Two people on a speed boat",
      "duration": null,
      "score": {
        "faces": 0.4,
        "relevance": 0.25,
        "diversity": 0.18,
        "resolution": 0.1,
        "total": 0.93
      },
      "burst_group_id": "bg-001",
      "is_must_have": false,
      "source_query": "miami trip"
    }
  ],

  "burst_groups": {
    "bg-001": {
      "primary_asset_id": "uuid-...",
      "alternate_asset_ids": ["uuid-alt1", "uuid-alt2"],
      "timestamp_range": ["2026-03-31T14:30:00Z", "2026-03-31T14:30:04Z"]
    }
  },

  "scenes": [
    {
      "id": "scene-001",
      "label": "Speed boat tour",
      "time_range": ["2026-03-31T14:00:00Z", "2026-03-31T15:30:00Z"],
      "candidate_count": 45,
      "budget": 5
    }
  ],

  "timeline": [
    {
      "position": 1,
      "asset_id": "uuid-...",
      "type": "IMAGE",
      "caption": "Two people on a speed boat",
      "duration": 4.0,
      "trim_start": null,
      "trim_end": null,
      "transition": "crossfade",
      "scene_id": "scene-001"
    },
    {
      "position": 2,
      "asset_id": "uuid-video-...",
      "type": "VIDEO",
      "caption": "Boat ride through Biscayne Bay",
      "duration": 12.5,
      "trim_start": 0.0,
      "trim_end": 12.5,
      "transition": "crossfade",
      "scene_id": "scene-001"
    }
  ],

  "budget": {
    "total": 25,
    "formula": "base 10 + 5 per day",
    "trip_days": 3,
    "per_scene_overrides": {}
  },

  "music": {
    "type": "bundled | user | none",
    "mood": "upbeat",
    "track": "track1",
    "path": null
  },

  "preview": {
    "album_id": null,
    "share_key": null
  }
}
```

## State Transitions

```
searching → selecting → previewing → approved → generated
                                  ↑              |
                                  └──────────────┘
                                  (back to previewing)
```

- `searching`: Multi-query search in progress, building candidate pool
- `selecting`: Scoring, dedup, budget allocation in progress
- `previewing`: Timeline presented to user, awaiting approval or refinement
- `approved`: User approved, ready for video assembly
- `generated`: Video assembly complete, output.mp4 exists

## Key Relationships

- A **Project** has one **Candidate Pool** (all matching assets)
- A **Candidate Pool** is partitioned into **Burst Groups** (by timestamp proximity)
- A **Candidate Pool** is partitioned into **Scenes** (by 30-min time gaps)
- Each **Burst Group** has 1 primary and 0-3 alternates
- A **Timeline** is an ordered subset of the Candidate Pool
- Each **Timeline Item** belongs to exactly one **Scene**
- **Must-have Items** are guaranteed slots in the Timeline
- A **Project** optionally has a **Preview Album** (Immich shared album for mobile review)

## Backward Compatibility

The v1 `scenario.json` format is NOT supported by the new project file. The old `manage_scenario.py` functions (`create_scenario`, `add_item`, etc.) will be replaced by new functions in `manage_project.py`. The v1 skill workflow will be updated to use the new format.
