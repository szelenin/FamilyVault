<script lang="ts">
  import FilmstripTrimmer from '$lib/FilmstripTrimmer.svelte';
  let { data } = $props();
  let scenes = $state(data.scenes);
  let removedToast = $state<{id: string, label: string} | null>(null);
  let undoTimer: ReturnType<typeof setTimeout> | null = null;
  let expandedScene = $state<string | null>(null);
  let editingNote = $state<string | null>(null);
  let noteText = $state("");
  let saving = $state(false);

  // Detail overlay state
  let detailItem = $state<{asset_id: string, type: string, duration: string | null} | null>(null);
  let detailIndex = $state(-1);
  let detailSceneId = $state<string | null>(null);
  let sceneItemsCache = $state<Record<string, Array<{asset_id: string, type: string, duration: string | null}>>>({});
  let loadingDetails = $state<string | null>(null);

  // Item deselect undo state
  let itemUndoToast = $state<{sceneId: string, assetId: string} | null>(null);
  let itemUndoTimer: ReturnType<typeof setTimeout> | null = null;

  // Trim state
  let trimStart = $state(0);
  let trimEnd = $state(0);
  let trimDuration = $state(0);
  let videoEl: HTMLVideoElement | null = null;
  let videoTrims = $state<Record<string, {start: number, end: number}>>(data.videoTrims || {});

  function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
  }

  function formatTrimTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  async function saveNote(sceneId: string) {
    saving = true;
    await fetch(`/api/project/${data.projectId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scene_id: sceneId, note: noteText }),
    });
    const scene = scenes.find(s => s.id === sceneId);
    if (scene) scene.note = noteText;
    editingNote = null;
    saving = false;
  }

  function startEditing(sceneId: string, currentNote: string) {
    editingNote = sceneId;
    noteText = currentNote;
  }

  function toggleExpand(sceneId: string) {
    if (expandedScene === sceneId) {
      expandedScene = null;
    } else {
      expandedScene = sceneId;
      fetchSceneDetails(sceneId);
    }
  }

  async function fetchSceneDetails(sceneId: string) {
    if (sceneItemsCache[sceneId]) return;
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    loadingDetails = sceneId;
    const items: Array<{asset_id: string, type: string, duration: string | null}> = [];
    // Fetch in parallel batches of 10
    for (let i = 0; i < scene.selectedIds.length; i += 10) {
      const batch = scene.selectedIds.slice(i, i + 10);
      const results = await Promise.all(
        batch.map(async (id: string) => {
          try {
            const resp = await fetch(`/api/asset/${id}/info`);
            const info = await resp.json();
            return { asset_id: id, type: info.type, duration: info.duration };
          } catch {
            return { asset_id: id, type: "IMAGE", duration: null };
          }
        })
      );
      items.push(...results);
    }
    sceneItemsCache[sceneId] = items;
    sceneItemsCache = { ...sceneItemsCache }; // trigger reactivity
    loadingDetails = null;
  }

  async function removeScene(sceneId: string) {
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;

    const removedScene = { ...scene };
    scenes = scenes.filter(s => s.id !== sceneId);
    removedToast = { id: sceneId, label: scene.label || scene.id };

    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(async () => {
      const resp = await fetch(`/api/project/${data.projectId}`);
      const project = await resp.json();
      const current = new Set(project.deselected_ids || []);
      for (const id of removedScene.selectedIds) current.add(id);
      await fetch(`/api/project/${data.projectId}/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deselected_ids: [...current] }),
      });
      removedToast = null;
    }, 5000);
  }

  function undoRemove() {
    if (!removedToast) return;
    if (undoTimer) clearTimeout(undoTimer);
    const scene = data.scenes.find(s => s.id === removedToast!.id);
    if (scene) scenes = [...scenes, scene];
    removedToast = null;
  }

  // --- Detail overlay ---

  function initTrimForItem(item: {asset_id: string, type: string, duration: string | null}) {
    if (item.type !== "VIDEO") return;
    const dur = parseDuration(item.duration);
    trimDuration = dur;
    const existing = videoTrims?.[item.asset_id];
    trimStart = existing?.start ?? 0;
    trimEnd = existing?.end ?? dur;
  }

  function openDetail(sceneId: string, index: number) {
    const items = sceneItemsCache[sceneId];
    if (!items || !items[index]) return;
    detailSceneId = sceneId;
    detailIndex = index;
    detailItem = items[index];
    initTrimForItem(detailItem);
  }

  function closeDetail() {
    detailItem = null;
    detailIndex = -1;
    detailSceneId = null;
  }

  function prevDetail() {
    if (!detailSceneId || detailIndex <= 0) return;
    detailIndex--;
    detailItem = sceneItemsCache[detailSceneId][detailIndex];
    initTrimForItem(detailItem);
  }

  function nextDetail() {
    if (!detailSceneId) return;
    const items = sceneItemsCache[detailSceneId];
    if (detailIndex >= items.length - 1) return;
    detailIndex++;
    detailItem = items[detailIndex];
    initTrimForItem(detailItem);
  }

  function currentSceneItems() {
    if (!detailSceneId) return [];
    return sceneItemsCache[detailSceneId] || [];
  }

  // --- Item deselect ---

  async function deselectItem(sceneId: string, assetId: string) {
    // Close detail if we're deselecting the current item
    if (detailItem && detailItem.asset_id === assetId) {
      const items = sceneItemsCache[sceneId];
      if (items && items.length > 1) {
        // Advance to next or prev
        if (detailIndex < items.length - 1) {
          // Will shift down after removal, so same index points to next
        } else {
          detailIndex = Math.max(0, detailIndex - 1);
        }
      } else {
        closeDetail();
      }
    }

    // Remove from scene
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    scene.selectedIds = scene.selectedIds.filter((id: string) => id !== assetId);
    scene.selectedCount = scene.selectedIds.length;

    // Update cache
    if (sceneItemsCache[sceneId]) {
      sceneItemsCache[sceneId] = sceneItemsCache[sceneId].filter(i => i.asset_id !== assetId);
      sceneItemsCache = { ...sceneItemsCache };
      // Update detail view
      if (detailSceneId === sceneId && sceneItemsCache[sceneId].length > 0) {
        detailIndex = Math.min(detailIndex, sceneItemsCache[sceneId].length - 1);
        detailItem = sceneItemsCache[sceneId][detailIndex];
      }
    }

    // Update photo/video counts (approximate — decrement based on removed type)
    const cached = sceneItemsCache[sceneId]?.find(i => i.asset_id === assetId);
    // Already removed from cache, so check original info
    // Just recalc from cache
    if (sceneItemsCache[sceneId]) {
      scene.photoCount = sceneItemsCache[sceneId].filter(i => i.type === "IMAGE").length;
      scene.videoCount = sceneItemsCache[sceneId].filter(i => i.type === "VIDEO").length;
    }

    scenes = [...scenes]; // trigger reactivity

    // If scene is now empty, remove it
    if (scene.selectedIds.length === 0) {
      scenes = scenes.filter(s => s.id !== sceneId);
      closeDetail();
    }

    // Show undo toast
    itemUndoToast = { sceneId, assetId };
    if (itemUndoTimer) clearTimeout(itemUndoTimer);
    itemUndoTimer = setTimeout(async () => {
      // Persist
      const resp = await fetch(`/api/project/${data.projectId}`);
      const project = await resp.json();
      const current = new Set(project.deselected_ids || []);
      current.add(assetId);
      await fetch(`/api/project/${data.projectId}/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deselected_ids: [...current] }),
      });
      itemUndoToast = null;
    }, 3000);
  }

  function undoItemDeselect() {
    if (!itemUndoToast) return;
    if (itemUndoTimer) clearTimeout(itemUndoTimer);
    const { sceneId, assetId } = itemUndoToast;
    // Restore to scene
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) {
      // Scene was removed (was last item) — restore from data
      const origScene = data.scenes.find(s => s.id === sceneId);
      if (origScene) {
        const restored = { ...origScene, selectedIds: [assetId], selectedCount: 1 };
        scenes = [...scenes, restored];
      }
    } else {
      scene.selectedIds = [...scene.selectedIds, assetId];
      scene.selectedCount = scene.selectedIds.length;
      scenes = [...scenes];
    }
    // Restore to cache
    if (sceneItemsCache[sceneId]) {
      // Re-add with unknown type (will refresh on next expand)
      sceneItemsCache[sceneId] = [...sceneItemsCache[sceneId], { asset_id: assetId, type: "IMAGE", duration: null }];
      sceneItemsCache = { ...sceneItemsCache };
    }
    itemUndoToast = null;
  }

  // --- Video trim ---

  function parseDuration(d: string | null): number {
    if (!d) return 30; // default
    // "0:00:05.123" or "00:05" or just seconds
    const parts = d.split(":");
    if (parts.length === 3) return +parts[0] * 3600 + +parts[1] * 60 + parseFloat(parts[2]);
    if (parts.length === 2) return +parts[0] * 60 + parseFloat(parts[1]);
    return parseFloat(d) || 30;
  }

  async function saveTrim() {
    if (!detailItem) return;
    await fetch(`/api/project/${data.projectId}/trim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: detailItem.asset_id, start: trimStart, end: trimEnd }),
    });
    // Update local state
    videoTrims[detailItem.asset_id] = { start: trimStart, end: trimEnd };
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!detailItem) return;
    if (e.key === "Escape") closeDetail();
    if (e.key === "ArrowLeft") prevDetail();
    if (e.key === "ArrowRight") nextDetail();
  }

  const totalSelected = $derived(scenes.reduce((s, sc) => s + sc.selectedCount, 0));
  const totalPhotos = $derived(scenes.reduce((s, sc) => s + sc.photoCount, 0));
  const totalVideos = $derived(scenes.reduce((s, sc) => s + sc.videoCount, 0));
  const estimatedSec = $derived(Math.round(totalPhotos * 4 + totalVideos * 8 - Math.max(0, totalSelected - 1) * 0.5));
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="mb-4">
  <a href="/project/{data.projectId}" class="text-blue-400 text-sm" data-testid="back-to-selection">&larr; Selection</a>
  <h1 class="text-xl font-bold mt-1">Your Story</h1>
  <p class="text-sm text-gray-400">{scenes.length} scenes · {totalSelected} items · ~{formatDuration(estimatedSec)}</p>
</div>

<div class="space-y-4 pb-20">
  {#if scenes.length === 0}
    <div class="text-center py-12 text-gray-500">
      <p class="text-lg mb-2">No scenes with selected items</p>
      <a href="/project/{data.projectId}" class="text-blue-400">← Go back to Selection</a>
    </div>
  {/if}
  {#each scenes as scene (scene.id)}
    <div class="bg-gray-900 rounded-lg overflow-hidden" data-testid="scene-card">
      <!-- Scene header -->
      <div class="p-3 flex items-start gap-3">
        <div class="text-gray-500 cursor-grab text-lg mt-1">≡</div>
        <div class="flex-1 min-w-0">
          <div class="font-medium">{scene.label || scene.id}</div>
          <div class="text-xs text-gray-400">
            {scene.selectedCount} items · ~{formatDuration(Math.round(scene.photoCount * 4 + scene.videoCount * 8 - Math.max(0, scene.selectedCount - 1) * 0.5))}
            {#if scene.cities?.length} · {scene.cities.join(", ")}{/if}
          </div>
        </div>
        <button onclick={() => removeScene(scene.id)}
                class="p-1 text-gray-500 hover:text-red-400 transition shrink-0"
                data-testid="remove-scene">
          ✕
        </button>
      </div>

      <!-- Thumbnail strip / expanded grid -->
      {#if expandedScene === scene.id}
        <div class="px-3 pb-2">
          <div class="flex gap-1 flex-wrap">
            {#each scene.selectedIds as assetId, i}
              <div class="relative w-14 h-14 shrink-0 cursor-pointer"
                   onclick={() => openDetail(scene.id, i)}
                   data-testid="expanded-thumbnail">
                <img src="/api/thumbnail/{assetId}"
                     alt="" class="w-full h-full object-cover rounded" loading="lazy" />
                <!-- X deselect button -->
                <button class="absolute -top-1 -right-1 w-5 h-5 bg-black/80 rounded-full flex items-center justify-center text-xs text-gray-300 hover:text-red-400"
                        onclick={(e) => { e.stopPropagation(); deselectItem(scene.id, assetId); }}
                        data-testid="deselect-item">✕</button>
                <!-- Video badge -->
                {#if sceneItemsCache[scene.id]?.find(it => it.asset_id === assetId)?.type === "VIDEO"}
                  <div class="absolute bottom-0 right-0 bg-black/70 px-1 py-0.5 rounded-tl text-[10px] flex items-center gap-0.5" data-testid="video-badge">
                    <span>▶</span>
                    {#if videoTrims?.[assetId]}
                      <span class="text-blue-400" data-testid="trim-badge">{formatTrimTime(videoTrims[assetId].start)}-{formatTrimTime(videoTrims[assetId].end)}</span>
                    {:else}
                      {#if sceneItemsCache[scene.id]?.find(it => it.asset_id === assetId)?.duration}
                        <span>{sceneItemsCache[scene.id].find(it => it.asset_id === assetId)?.duration}</span>
                      {/if}
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
          {#if loadingDetails === scene.id}
            <div class="text-xs text-gray-500 mt-1">Loading details...</div>
          {/if}
          <button class="text-xs text-gray-500 mt-1" onclick={() => expandedScene = null}>Collapse</button>
        </div>
      {:else}
        <button class="px-3 pb-2 cursor-pointer w-full text-left" data-testid="thumbnail-strip" onclick={() => toggleExpand(scene.id)}>
          <div class="flex gap-1 overflow-hidden">
            {#each scene.selectedIds.slice(0, 5) as assetId}
              <img src="/api/thumbnail/{assetId}"
                   alt="" class="w-14 h-14 object-cover rounded shrink-0" loading="lazy" />
            {/each}
            {#if scene.selectedIds.length > 5}
              <div class="w-14 h-14 bg-gray-800 rounded flex items-center justify-center text-xs text-gray-400 shrink-0">
                +{scene.selectedIds.length - 5}
              </div>
            {/if}
          </div>
          {#if scene.selectedIds.length > 5}
            <div class="text-xs text-gray-500 mt-1">Tap to see all {scene.selectedIds.length} items</div>
          {/if}
        </button>
      {/if}

      <!-- Story field -->
      <div class="px-3 pb-3">
        {#if editingNote === scene.id}
          <div class="space-y-2">
            <textarea
              bind:value={noteText}
              placeholder="Tell your story... memories, AI instructions, mood, anything"
              class="w-full bg-gray-800 text-white rounded-lg p-3 text-sm resize-none border border-gray-700 focus:border-blue-500 focus:outline-none"
              rows="3"
            ></textarea>
            <div class="flex gap-2 justify-end">
              <button onclick={() => editingNote = null}
                      class="px-3 py-1.5 text-xs text-gray-400">Cancel</button>
              <button onclick={() => saveNote(scene.id)}
                      class="px-3 py-1.5 bg-blue-600 rounded text-xs font-medium">
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        {:else if scene.note}
          <div class="bg-gray-800 rounded-lg p-3 cursor-pointer" data-testid="existing-note" onclick={() => startEditing(scene.id, scene.note)}>
            <div class="text-xs text-blue-400 mb-1">📝 Your story</div>
            <div class="text-sm text-gray-300">{scene.note}</div>
          </div>
        {:else}
          <button onclick={() => startEditing(scene.id, "")}
                  class="text-sm text-gray-500 hover:text-gray-300 transition"
                  data-testid="add-story">
            + Add your story
          </button>
        {/if}
      </div>
    </div>
  {/each}
</div>

<!-- Detail overlay -->
{#if detailItem}
  <div class="fixed inset-0 bg-black z-50 flex flex-col" data-testid="detail-overlay" onclick={closeDetail}>
    <!-- Top bar -->
    <div class="flex items-center justify-between p-4 bg-black/80" onclick={(e) => e.stopPropagation()}>
      <button onclick={closeDetail} class="text-white text-lg" data-testid="detail-close">✕</button>
      <div class="text-center" data-testid="detail-counter">
        <div class="text-sm text-gray-400">{detailIndex + 1} / {currentSceneItems().length}</div>
        {#if detailItem.type === "VIDEO"}
          <div class="text-xs text-yellow-400">{formatTrimTime(trimEnd - trimStart)} of {formatTrimTime(trimDuration)}</div>
        {/if}
      </div>
      <button onclick={() => { if (detailSceneId && detailItem) deselectItem(detailSceneId, detailItem.asset_id); }}
              class="px-3 py-1 bg-red-600/80 rounded-full text-sm font-medium"
              data-testid="detail-deselect">
        Remove
      </button>
    </div>

    <!-- Media -->
    <div class="flex-1 flex items-center justify-center overflow-hidden" onclick={(e) => e.stopPropagation()}>
      {#if detailItem.type === "VIDEO"}
        <video src="/api/video/{detailItem.asset_id}"
               poster="/api/thumbnail/{detailItem.asset_id}?size=preview"
               controls playsinline preload="metadata"
               bind:this={videoEl}
               class="max-w-full max-h-full object-contain"
               data-testid="detail-video"
               onloadedmetadata={() => {
                 if (videoEl) videoEl.currentTime = trimStart;
               }}
               ontimeupdate={() => {
                 if (videoEl && videoEl.currentTime >= trimEnd) {
                   videoEl.currentTime = trimStart;
                 }
               }} />
      {:else}
        <img src="/api/thumbnail/{detailItem.asset_id}?size=preview"
             alt="" class="max-w-full max-h-full object-contain"
             data-testid="detail-image" />
      {/if}
    </div>

    <!-- Filmstrip trim (always shown for videos) -->
    {#if detailItem.type === "VIDEO"}
      <div class="px-4 pt-3 pb-1 bg-black/90" onclick={(e) => e.stopPropagation()} data-testid="trim-ui">
        <FilmstripTrimmer
          videoSrc="/api/video/{detailItem.asset_id}"
          duration={trimDuration}
          bind:trimStart
          bind:trimEnd
          bind:videoEl
        />
      </div>
    {/if}

    <!-- Navigation + save -->
    <div class="flex items-center justify-between p-4 bg-black/80" onclick={(e) => e.stopPropagation()}>
      <button onclick={prevDetail}
              class="px-6 py-2 bg-gray-800 rounded-lg" class:opacity-30={detailIndex === 0}
              disabled={detailIndex === 0}
              data-testid="detail-prev">
        ← Prev
      </button>
      {#if detailItem.type === "VIDEO"}
        <button onclick={saveTrim}
                class="px-4 py-2 bg-blue-600 rounded-lg text-sm font-medium"
                data-testid="trim-save">
          Save Trim
        </button>
      {/if}
      <button onclick={nextDetail}
              class="px-6 py-2 bg-gray-800 rounded-lg" class:opacity-30={detailIndex === currentSceneItems().length - 1}
              disabled={detailIndex === currentSceneItems().length - 1}
              data-testid="detail-next">
        Next →
      </button>
    </div>
  </div>
{/if}

<!-- Undo toasts -->
{#if removedToast}
  <div class="fixed bottom-16 left-4 right-4 bg-gray-800 rounded-lg p-4 flex items-center gap-3 shadow-xl border border-gray-700 z-50">
    <span class="flex-1 text-sm">Removed "{removedToast.label}"</span>
    <button onclick={undoRemove}
            class="px-4 py-1.5 bg-blue-600 rounded-lg text-sm font-medium">Undo</button>
  </div>
{/if}

{#if itemUndoToast}
  <div class="fixed bottom-16 left-4 right-4 bg-gray-800 rounded-lg p-4 flex items-center gap-3 shadow-xl border border-gray-700 z-50">
    <span class="flex-1 text-sm">Item removed</span>
    <button onclick={undoItemDeselect}
            class="px-4 py-1.5 bg-blue-600 rounded-lg text-sm font-medium">Undo</button>
  </div>
{/if}

<!-- Summary bar -->
<div class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 p-3 flex items-center justify-between z-40" data-testid="summary-bar">
  <div class="text-sm text-gray-400" data-testid="summary-stats">{totalSelected} items · ~{formatDuration(estimatedSec)}</div>
  <a href="/project/{data.projectId}" class="text-sm text-blue-400" data-testid="summary-selection-link">&larr; Selection</a>
</div>
