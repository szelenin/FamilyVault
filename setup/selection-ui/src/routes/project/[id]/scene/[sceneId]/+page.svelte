<script lang="ts">
  let { data } = $props();
  let items = $state(data.scene.items);
  let saving = $state(false);

  const selectedCount = $derived(items.filter(i => i.selected).length);

  async function toggleItem(assetId: string) {
    const item = items.find(i => i.asset_id === assetId);
    if (item) item.selected = !item.selected;
    await saveSelection();
  }

  async function selectAll() {
    items.forEach(i => i.selected = true);
    await saveSelection();
  }

  async function deselectAll() {
    items.forEach(i => i.selected = false);
    await saveSelection();
  }

  async function photosOnly() {
    items.forEach(i => i.selected = i.type === 'IMAGE');
    await saveSelection();
  }

  async function videosOnly() {
    items.forEach(i => i.selected = i.type === 'VIDEO');
    await saveSelection();
  }

  async function saveSelection() {
    saving = true;
    const deselected = items.filter(i => !i.selected).map(i => i.asset_id);
    // Merge with other scenes' deselections
    const resp = await fetch(`/api/project/${data.projectId}`);
    const project = await resp.json();
    const otherDeselected = (project.deselected_ids || [])
      .filter((id: string) => !data.scene.items.some((i: any) => i.asset_id === id));
    await fetch(`/api/project/${data.projectId}/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deselected_ids: [...otherDeselected, ...deselected] })
    });
    saving = false;
  }

  async function toggleFavorite(assetId: string) {
    const item = items.find(i => i.asset_id === assetId);
    if (!item) return;
    item.favorite = !item.favorite;
    await fetch(`/api/favorite/${assetId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ isFavorite: item.favorite })
    });
  }
</script>

<div class="mb-4">
  <a href="/project/{data.projectId}" class="text-blue-400 text-sm">← Scenes</a>
  <h1 class="text-lg font-bold mt-1">{data.scene.label || 'Scene'}</h1>
  <p class="text-sm text-gray-400">
    {selectedCount}/{items.length} selected
    {#if saving}<span class="text-yellow-400 ml-2">saving...</span>{/if}
  </p>
</div>

<!-- Batch actions -->
<div class="flex gap-2 mb-4 overflow-x-auto pb-2">
  <button onclick={selectAll} class="px-3 py-1.5 bg-gray-800 rounded-full text-xs whitespace-nowrap hover:bg-gray-700">Select All</button>
  <button onclick={deselectAll} class="px-3 py-1.5 bg-gray-800 rounded-full text-xs whitespace-nowrap hover:bg-gray-700">Deselect All</button>
  <button onclick={photosOnly} class="px-3 py-1.5 bg-gray-800 rounded-full text-xs whitespace-nowrap hover:bg-gray-700">Photos Only</button>
  <button onclick={videosOnly} class="px-3 py-1.5 bg-gray-800 rounded-full text-xs whitespace-nowrap hover:bg-gray-700">Videos Only</button>
</div>

<!-- Thumbnail grid -->
<div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1">
  {#each items as item}
    <div class="relative aspect-square cursor-pointer group"
         onclick={() => toggleItem(item.asset_id)}>
      <img src="/api/thumbnail/{item.asset_id}"
           alt="" class="w-full h-full object-cover rounded
                        {item.selected ? '' : 'opacity-30'}"
           loading="lazy" />
      
      <!-- Selection checkbox -->
      <div class="absolute top-1 left-1 w-6 h-6 rounded-full border-2 flex items-center justify-center
                  {item.selected ? 'bg-blue-500 border-blue-500' : 'border-white/50 bg-black/30'}">
        {#if item.selected}
          <span class="text-xs">✓</span>
        {/if}
      </div>

      <!-- Video indicator -->
      {#if item.type === 'VIDEO'}
        <div class="absolute bottom-1 right-1 bg-black/70 px-1.5 py-0.5 rounded text-xs flex items-center gap-1">
          <span>▶</span>
          {#if item.duration}
            <span>{item.duration}</span>
          {/if}
        </div>
      {/if}

      <!-- Favorite heart -->
      <button class="absolute top-1 right-1 text-lg"
              onclick={() => toggleFavorite(item.asset_id)}>
        {item.favorite ? '❤️' : ''}
      </button>
    </div>
  {/each}
</div>
