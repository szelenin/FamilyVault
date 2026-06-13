# FamilyVault — Model Spec for Intelligent Search

**Purpose of this document.** Hand-off spec for the FamilyVault development session. It defines the *additional* models FamilyVault needs to layer on top of Immich to support intelligent search (e.g. "videos where my son plays piano"). Focus is on **VLM captioning/extraction** and **audio understanding** — the two capability gaps Immich does not cover. Hardware target is the **M4 Mac Mini (24 GB unified memory)** today, with notes on a future GPU-box upgrade path.

---

## 1. What Immich already provides (do NOT rebuild)

| Capability | Immich feature | FamilyVault uses it via |
|---|---|---|
| Face detection + clustering | Built-in ML (face detection + facial recognition jobs) | Immich API → person IDs |
| Person identity ("who") | Named people, merge, DOB, favorites | Immich API → assets-by-person |
| Semantic image search (CLIP) | "Smart Search" (configurable CLIP model) | Immich API; can swap to **multilingual CLIP** model |
| Basic metadata | EXIF, dates, geolocation | Immich API |

**Key implications:**
- **Face/identity is solved by Immich.** FamilyVault must NOT try to re-identify people with a VLM. A VLM says "a young boy"; Immich knows it's *your son*. Resolve "who" through Immich person IDs.
- **Switch Immich to a multilingual CLIP model** (ML settings) so concept search works across English/Russian/Ukrainian. This triggers a one-time full re-index of the library — do it early. This is config, not a FamilyVault model.

---

## 2. The capability gaps FamilyVault must fill

Three things Immich does not do, in priority order:

1. **VLM captioning/extraction** — rich descriptions of *what is happening* (activities, context, relationships) beyond CLIP's shallow concept match. This is the core add.
2. **Audio understanding** — speech transcription (Whisper) + sound-event detection (e.g. "piano music"). **Not optional.** For "playing piano," the soundtrack is often the strongest and cheapest confirmation signal; a still frame can't distinguish *sitting at* vs *playing* a piano, but audio can.
3. **Video frame handling** — sampling frames from clips and aggregating per-frame results into a video-level conclusion. This is pipeline logic wrapping the VLM, not a separate model.

The FamilyVault layer also owns **alias/multilingual name mapping** (misspellings, cross-script names like Misha/Миша/Михаил → one Immich person ID). This is application logic, not a model — noted here so it isn't confused with a model dependency.

---

## 3. VLM captioning models (the core recommendation)

All sizes below are Q4 (~0.5 GB per billion params is the rule of thumb; MoE memory is driven by *total* params, speed by *active* params). Mac Mini has 24 GB unified, shared across the OS and any concurrently loaded models — so realistic headroom for one model is ~18–20 GB if it's the only large thing resident.

### Recommended family: Qwen3-VL

Current-generation, strong multimodal reasoning, strong video/temporal support, available in Ollama. Released Oct 2025 (4B/8B/30B-A3B). Variants exist in **Instruct** (faster, for captioning) and **Thinking** (slower, for harder reasoning) — **use Instruct for ingest captioning**.

| Model | Type | ~VRAM (Q4) | Context | Mac Mini (24GB) | Notes |
|---|---|---|---|---|---|
| **Qwen3-VL 4B** | dense | ~3.3 GB | 256K | ✅ fast (~20–30 tok/s) | Minimum viable. Good for tagging + basic captions. |
| **Qwen3-VL 8B** ⭐ | dense | ~6.1 GB | 256K | ✅ ~12–20 tok/s | **Recommended default.** Best quality/speed/footprint balance on the Mini. Leaves room for audio + embeddings resident alongside. |
| **Qwen3-VL 30B-A3B** | MoE (3B active) | ~20 GB | 256K | ⚠️ fits but tight/slow (~6–12 tok/s); crowds out other models | Quality ceiling on the Mini. Better suited to the GPU box. |

**Why 8B is the default:** captioning is a **batch ingest job** (runs once per asset, slow-but-fine is acceptable), so the Mini doesn't need blazing speed. 8B comfortably coexists with Whisper (~3 GB) + an embedding model (~1 GB) inside 24 GB, which matters because FamilyVault wants several small models *resident together*, not one giant one.

### Alternatives worth knowing
- **Qwen2.5-VL 7B** — previous gen, very mature, excellent video support (dynamic resolution/frame-rate, hour-long video comprehension, event localization). Safe fallback if a Qwen3-VL quirk shows up in Ollama. ~6 GB.
- **InternVL3 / InternVL3.5 8B** — comparable quality, strong visual grounding. Good A/B candidate. ~6 GB.

### Video temporal note
Qwen3-VL adds **text–timestamp alignment** (reasoning over *when* events occur in a clip), and Qwen2.5-VL already supports hour-long video with event localization. This is directly useful for "find the moment he's *playing*" rather than just "this clip contains a piano." FamilyVault still drives frame sampling itself; the model interprets the sampled frames.

---

## 4. Audio models (required, not optional)

Two distinct jobs. Both run comfortably on the Mac Mini (Whisper is Metal-accelerated via whisper.cpp).

### 4a. Speech-to-text — Whisper
- **whisper-large-v3** — 1.55B params, ~99 languages, ~3 GB (FP16) / ~2 GB (INT8 via faster-whisper). Best accuracy + full multilingual (important for RU/UK households). Use for accuracy-critical batch transcription.
- **whisper-large-v3-turbo** — 809M params, 4 decoder layers (vs 32), ~48% faster, minor accuracy cost. Use if ingest throughput matters more than peak accuracy.
- **Runtime:** `whisper.cpp` (Metal) or `faster-whisper` (CTranslate2, INT8, ~4–5× faster, lower memory). On Apple Silicon, whisper.cpp + Metal is the natural fit.
- **Multilingual matters here:** large-v3 transcribes RU/UK speech, feeding the FamilyVault text index in-language.

### 4b. Sound-event detection — "is there piano music?"
Whisper only transcribes *speech*; it will not tell you a piano is playing. For non-speech audio events you need a separate, tiny model:
- **CLAP** (Contrastive Language-Audio Pretraining) — produces audio embeddings searchable by text ("piano music", "applause", "laughter"). Best fit for *searchable* audio, mirrors how CLIP works for images. Small.
- **PANNs / YAMNet** — pretrained audio tagging (AudioSet classes incl. musical instruments). Lightweight classifiers if you prefer fixed labels over embeddings.

**For the piano use case, CLAP is the high-leverage pick:** it lets "playing piano" match the *soundtrack* directly, and it's cheap enough to run on every video at ingest.

---

## 5. The "son playing piano" query — how the models combine

This is fusion logic in the FamilyVault layer, combining independent signals:

```
WHO  → Immich person ID for "son"        (Immich face recognition)
WHAT → "piano" in VLM caption text       (Qwen3-VL 8B, sampled frames)
     → OR CLIP concept match             (Immich multilingual smart search)
PLAY → piano sound in audio track        (CLAP / PANNs)   ← strongest "playing" signal
     → OR speech cues from transcript     (Whisper)
```

Ranking = weighted combination. A clip with **son's face + piano visible + piano audio** ranks above one with only a visual match. The "intelligent" part lives in this fusion, not in any single model.

**v1 vs v2:**
- **v1 (ship first):** Immich faces + Qwen3-VL 8B captions. Works "mostly."
- **v2 (reliable):** add Whisper + CLAP audio. Turns "mostly works" into "reliable," especially for activity verbs like *playing*.

---

## 6. Ingest vs query-time (where models run)

- **Ingest (batch, per asset, slow-OK):** VLM captioning, Whisper transcription, CLAP audio tagging, embedding generation. Store all outputs (captions, transcripts, audio tags, embeddings) in FamilyVault's own index keyed to the Immich asset/person IDs. Run heavy VLM captioning **selectively** — not a 30B on every photo; caption on a schedule or on first query.
- **Query-time (fast):** retrieve from the precomputed index + fuse signals. No heavy model load needed for a typical search. Optionally call the VLM on-demand for a hard, contextual query.

This split is why the Mac Mini is viable: the expensive work is amortized at ingest; queries hit a precomputed index.

---

## 7. Model serving on the Mini

- **Runtime:** **Ollama** — easiest for mixed models, auto load/unload of idle models, OpenAI-compatible API at `http://localhost:11434/v1/`. Lets FamilyVault address models by name and swap per task.
- **Resident-together budget (24 GB):** Qwen3-VL 8B (~6) + Whisper large-v3 (~3) + CLAP (small) + embeddings (~1) ≈ ~10–11 GB → fits with headroom. The 30B-A3B (~20 GB) does NOT fit alongside others — it would force load/unload swapping.
- **Load/unload on demand:** Ollama unloads idle models after a timeout, so you can *appear* to have many models on limited memory at the cost of a few seconds' reload latency when switching. Fine for a home server with bursty traffic.
- **Pull commands:**
  - `ollama pull qwen3-vl:8b`
  - `ollama pull qwen3-vl:4b` (lighter fallback)
  - Whisper via `whisper.cpp` (Metal) or `faster-whisper` (not through Ollama)

---

## 8. GPU-box upgrade path (future, not v1)

If the Mini becomes the bottleneck (slow whole-library captioning, or you want richer 30B/larger captions resident alongside other models):

- **Single 24 GB GPU (used RTX 3090, ~$700–900; full build ~$1,750):** runs Qwen3-VL 30B-A3B fast (~40–70 tok/s), or 32B-class VLMs; 4–8× the memory bandwidth of the Mini → dramatically faster prefill/batch captioning. Same 24 GB model ceiling as the Mini but far faster.
- **Single RTX 4090 (~$2,100; build ~$3,080):** ~2× the 3090 on inference; pick if fast whole-library batch captioning is a priority.
- **Dual 3090 (48 GB; build ~$2,900):** only needed for 70B-class models or running a big LLM + big VLM **resident simultaneously**. Likely beyond FamilyVault v1.

**Recommended architecture:** keep the Mac Mini as the always-on orchestrator (light models, MCP, query-time fusion); add a GPU box later that powers on only for heavy batch jobs (wake-on-LAN to avoid idle power). Spec any first build with PSU/mobo headroom for a second card.

> Note: GPU prices and exact model availability shift; re-verify before purchase. Model sizes/tags here reflect Ollama listings as of mid-2026 and should be confirmed at integration time.

---

## 9. Shopping list (models to integrate)

| Need | Model | Size (Q4) | Runtime | Priority |
|---|---|---|---|---|
| VLM captioning | **Qwen3-VL 8B (Instruct)** | ~6 GB | Ollama | v1 |
| VLM fallback | Qwen2.5-VL 7B or InternVL3 8B | ~6 GB | Ollama | A/B test |
| VLM quality ceiling | Qwen3-VL 30B-A3B | ~20 GB | Ollama (GPU box) | v2/GPU |
| Speech-to-text | Whisper large-v3 (or turbo) | ~2–3 GB | whisper.cpp / faster-whisper | v2 (required) |
| Sound events | CLAP (or PANNs/YAMNet) | small | python | v2 (required) |
| Multilingual concept search | swap Immich CLIP → multilingual CLIP | n/a (Immich) | Immich ML settings | early config |

Everything in the v1/v2 rows fits and runs on the 24 GB Mac Mini together. The GPU box is an optimization, not a prerequisite.
