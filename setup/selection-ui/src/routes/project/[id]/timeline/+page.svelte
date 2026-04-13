<script lang="ts">
  let { data } = $props();
  let scenes = $state(data.scenes);
  let removedToast = $state<{id: string, label: string} | null>(null);
  let undoTimer: ReturnType<typeof setTimeout> | null = null;
  let expandedScene = $state<string | null>(null);
  let editingNote = $state<string | null>(null);
  let noteText = $state("");
  let saving = $state(false);

  function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
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
    expandedScene = expandedScene === sceneId ? null : sceneId;
  }

  async function removeScene(sceneId: string) {
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    
    const removedScene = { ...scene };
    scenes = scenes.filter(s => s.id !== sceneId);
    removedToast = { id: sceneId, label: scene.label || scene.id };

    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(async () => {
      // Persist: add scene assets to deselected_ids
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

  const totalSelected = $derived(scenes.reduce((s, sc) => s + sc.selectedCount, 0));
  const totalPhotos = $derived(scenes.reduce((s, sc) => s + sc.photoCount, 0));
  const totalVideos = $derived(scenes.reduce((s, sc) => s + sc.videoCount, 0));
  const estimatedSec = $derived(Math.round(totalPhotos * 4 + totalVideos * 8 - Math.max(0, totalSelected - 1) * 0.5));
</script>

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

      <!-- Thumbnail strip -->
      <button class="px-3 pb-2 cursor-pointer w-full text-left" data-testid="thumbnail-strip" onclick={() => toggleExpand(scene.id)}>
        <div class="flex gap-1 overflow-hidden" class:flex-wrap={expandedScene === scene.id}>
          {#each expandedScene === scene.id ? scene.selectedIds : scene.selectedIds.slice(0, 5) as assetId}
            <img src="/api/thumbnail/{assetId}"
                 alt="" class="w-14 h-14 object-cover rounded shrink-0" loading="lazy" />
          {/each}
          {#if expandedScene !== scene.id && scene.selectedIds.length > 5}
            <div class="w-14 h-14 bg-gray-800 rounded flex items-center justify-center text-xs text-gray-400 shrink-0">
              +{scene.selectedIds.length - 5}
            </div>
          {/if}
        </div>
        {#if expandedScene !== scene.id && scene.selectedIds.length > 5}
          <div class="text-xs text-gray-500 mt-1">Tap to see all {scene.selectedIds.length} items</div>
        {/if}
      </button>

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

<!-- Undo toast -->
{#if removedToast}
  <div class="fixed bottom-16 left-4 right-4 bg-gray-800 rounded-lg p-4 flex items-center gap-3 shadow-xl border border-gray-700 z-50">
    <span class="flex-1 text-sm">Removed "{removedToast.label}"</span>
    <button onclick={undoRemove}
            class="px-4 py-1.5 bg-blue-600 rounded-lg text-sm font-medium">Undo</button>
  </div>
{/if}

<!-- Summary bar -->
<div class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 p-3 flex items-center justify-between z-40" data-testid="summary-bar">
  <div class="text-sm text-gray-400" data-testid="summary-stats">{totalSelected} items · ~{formatDuration(estimatedSec)}</div>
  <a href="/project/{data.projectId}" class="text-sm text-blue-400" data-testid="summary-selection-link">&larr; Selection</a>
</div>
