<script lang="ts">
  let { data } = $props();
  let scenes = $state(data.scenes);
  let excludedToast = $state<{id: string, label: string} | null>(null);
  let undoTimer: ReturnType<typeof setTimeout> | null = null;
  let showExcluded = $state(false);

  const activeScenes = $derived(scenes.filter(s => !s.excluded));
  const excludedScenes = $derived(scenes.filter(s => s.excluded));
  const totalSelected = $derived(activeScenes.reduce((s, sc) => s + sc.selectedCount, 0));
  const totalItems = $derived(activeScenes.reduce((s, sc) => s + sc.totalCount, 0));

  function excludeScene(sceneId: string, e: Event) {
    e.preventDefault();
    e.stopPropagation();
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;

    scene.excluded = true;
    scenes = [...scenes]; // trigger reactivity
    excludedToast = { id: sceneId, label: scene.label || "Scene" };

    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(async () => {
      // Persist: add all scene assets to deselected_ids
      await persistExclusion(sceneId);
      excludedToast = null;
    }, 5000);
  }

  function undoExclude() {
    if (!excludedToast) return;
    if (undoTimer) clearTimeout(undoTimer);
    const scene = scenes.find(s => s.id === excludedToast!.id);
    if (scene) scene.excluded = false;
    scenes = [...scenes]; // trigger reactivity
    excludedToast = null;
  }

  async function restoreScene(sceneId: string) {
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    scene.excluded = false;
    scenes = [...scenes]; // trigger reactivity
    // Remove scene assets from deselected_ids
    await persistRestore(sceneId);
  }

  async function persistExclusion(sceneId: string) {
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    const resp = await fetch(`/api/project/${data.project.id}`);
    const project = await resp.json();
    const current = new Set(project.deselected_ids || []);
    for (const id of scene.assetIds) current.add(id);
    await fetch(`/api/project/${data.project.id}/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deselected_ids: [...current] })
    });
  }

  async function persistRestore(sceneId: string) {
    const scene = scenes.find(s => s.id === sceneId);
    if (!scene) return;
    const resp = await fetch(`/api/project/${data.project.id}`);
    const project = await resp.json();
    const sceneAssetSet = new Set(scene.assetIds);
    const remaining = (project.deselected_ids || []).filter((id: string) => !sceneAssetSet.has(id));
    await fetch(`/api/project/${data.project.id}/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deselected_ids: remaining })
    });
    scene.selectedCount = scene.totalCount;
  }
</script>

<div class="mb-4">
  <a href="/" class="text-blue-400 text-sm">&larr; Projects</a>
  <h1 class="text-xl font-bold mt-1">{data.project.title}</h1>
  <p class="text-sm text-gray-400">{totalSelected}/{totalItems} selected · {activeScenes.length} scenes</p>
</div>

<div class="space-y-3">
  {#each activeScenes as scene (scene.id)}
    <div class="flex items-center gap-3 bg-gray-900 rounded-lg overflow-hidden">
      <a href="/project/{data.project.id}/scene/{scene.id}" class="flex items-center gap-3 p-3 flex-1 min-w-0">
        {#if scene.assetIds[0]}
          <img src="/api/thumbnail/{scene.assetIds[0]}"
               alt="" class="w-20 h-20 object-cover rounded shrink-0" loading="lazy" />
        {/if}
        <div class="flex-1 min-w-0">
          <div class="font-medium truncate">{scene.label || scene.id}</div>
          <div class="text-xs text-gray-400">
            {scene.time_range[0]?.slice(0,16).replace("T"," ")} ·
            {scene.cities?.join(", ") || ""}
          </div>
          <div class="text-xs text-gray-500">
            {scene.photo_count} photos, {scene.video_count} videos
          </div>
        </div>
        <div class="text-right shrink-0">
          <div class="text-sm font-mono" class:text-green-400={scene.selectedCount === scene.totalCount} class:text-yellow-400={scene.selectedCount !== scene.totalCount}>
            {scene.selectedCount}/{scene.totalCount}
          </div>
        </div>
      </a>
      <button onclick={(e) => excludeScene(scene.id, e)} data-testid="exclude-scene"
              class="p-3 text-gray-500 hover:text-red-400 transition shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 8v13H3V8"/>
          <path d="M1 3h22v5H1z"/>
          <path d="M10 12h4"/>
        </svg>
      </button>
    </div>
  {/each}
</div>

<!-- Excluded scenes link -->
{#if excludedScenes.length > 0 && !excludedToast}
  <div class="mt-6">
    <button onclick={() => showExcluded = !showExcluded}
            class="text-sm text-gray-400 hover:text-gray-200 transition">
      {showExcluded ? "Hide" : "Show"} {excludedScenes.length} excluded scene{excludedScenes.length > 1 ? "s" : ""}
    </button>

    {#if showExcluded}
      <div class="mt-3 space-y-2">
        {#each excludedScenes as scene (scene.id)}
          <div class="flex items-center gap-3 bg-gray-900/50 rounded-lg p-3 opacity-60">
            <div class="flex-1 min-w-0">
              <div class="text-sm truncate">{scene.label || scene.id}</div>
              <div class="text-xs text-gray-500">{scene.totalCount} items</div>
            </div>
            <button onclick={() => restoreScene(scene.id)}
                    class="px-3 py-1 bg-blue-600 rounded text-xs font-medium hover:bg-blue-500 transition">
              Restore
            </button>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<!-- Undo toast -->
{#if excludedToast}
  <div class="fixed bottom-6 left-4 right-4 bg-gray-800 rounded-lg p-4 flex items-center gap-3 shadow-xl border border-gray-700 z-50">
    <span class="flex-1 text-sm">Excluded "{excludedToast.label}"</span>
    <button onclick={undoExclude}
            class="px-4 py-1.5 bg-blue-600 rounded-lg text-sm font-medium hover:bg-blue-500 transition">
      Undo
    </button>
  </div>
{/if}
