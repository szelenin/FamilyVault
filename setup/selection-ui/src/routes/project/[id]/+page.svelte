<script lang="ts">
  let { data } = $props();
  const totalSelected = data.scenes.reduce((s, sc) => s + sc.selectedCount, 0);
  const totalItems = data.scenes.reduce((s, sc) => s + sc.totalCount, 0);
  const activeScenes = data.scenes.filter(s => s.selectedCount > 0);
  const emptyScenes = data.scenes.filter(s => s.selectedCount === 0);
</script>

<div class="mb-4">
  <a href="/" class="text-blue-400 text-sm">&larr; Projects</a>
  <h1 class="text-xl font-bold mt-1">{data.project.title}</h1>
  <p class="text-sm text-gray-400">{totalSelected}/{totalItems} selected · {data.scenes.length} scenes</p>
</div>

<!-- Summary bar -->
<div class="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 p-3 flex items-center justify-between z-40">
  <div class="text-sm text-gray-400">{totalSelected}/{totalItems} selected</div>
  <a href="/project/{data.project.id}/timeline" class="text-sm text-blue-400 font-medium">Review Timeline &rarr;</a>
</div>

{#if emptyScenes.length > 0}
  <details class="mt-6">
    <summary class="text-sm text-gray-500 cursor-pointer">{emptyScenes.length} deselected scenes</summary>
    <div class="space-y-3 mt-3 opacity-50">
      {#each emptyScenes as scene (scene.id)}
        <a href="/project/{data.project.id}/scene/{scene.id}"
           class="flex items-center gap-3 bg-gray-900 rounded-lg p-3 hover:bg-gray-800 transition">
          {#if scene.assetIds[0]}
            <img src="/api/thumbnail/{scene.assetIds[0]}"
                 alt="" class="w-16 h-16 object-cover rounded shrink-0" loading="lazy" />
          {/if}
          <div class="flex-1 min-w-0">
            <div class="font-medium truncate text-sm">{scene.label || scene.id}</div>
            <div class="text-xs text-gray-500">{scene.totalCount} items</div>
          </div>
          <div class="text-sm font-mono text-gray-600">0/{scene.totalCount}</div>
        </a>
      {/each}
    </div>
  </details>
{/if}

<div class="space-y-3">
  {#each activeScenes as scene (scene.id)}
    <a href="/project/{data.project.id}/scene/{scene.id}"
       class="flex items-center gap-3 bg-gray-900 rounded-lg p-3 hover:bg-gray-800 transition">
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
  {/each}
</div>
