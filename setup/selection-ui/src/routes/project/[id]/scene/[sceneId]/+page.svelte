<script lang="ts">
  let { data } = $props();
  let items = $state(data.scene.items);
  let saving = $state(false);
  let detailItem = $state<any>(null);
  let detailIndex = $state(-1);

  const selectedCount = $derived(items.filter(i => i.selected).length);

  async function toggleItem(assetId: string, e: Event) {
    e.stopPropagation();
    const item = items.find(i => i.asset_id === assetId);
    if (item) item.selected = !item.selected;
    await saveSelection();
  }

  function openDetail(index: number) {
    detailItem = items[index];
    detailIndex = index;
  }

  function closeDetail() {
    detailItem = null;
    detailIndex = -1;
  }

  function prevDetail() {
    if (detailIndex > 0) {
      detailIndex--;
      detailItem = items[detailIndex];
    }
  }

  function nextDetail() {
    if (detailIndex < items.length - 1) {
      detailIndex++;
      detailItem = items[detailIndex];
    }
  }

  async function toggleDetailSelection() {
    if (!detailItem) return;
    detailItem.selected = !detailItem.selected;
    await saveSelection();
  }

  async function selectAll() { items.forEach(i => i.selected = true); await saveSelection(); }
  async function deselectAll() { items.forEach(i => i.selected = false); await saveSelection(); }
  async function photosOnly() { items.forEach(i => i.selected = i.type === "IMAGE"); await saveSelection(); }
  async function videosOnly() { items.forEach(i => i.selected = i.type === "VIDEO"); await saveSelection(); }

  async function saveSelection() {
    saving = true;
    const deselected = items.filter(i => !i.selected).map(i => i.asset_id);
    const resp = await fetch(`/api/project/${data.projectId}`);
    const project = await resp.json();
    const otherDeselected = (project.deselected_ids || [])
      .filter((id: string) => !data.scene.items.some((i: any) => i.asset_id === id));
    await fetch(`/api/project/${data.projectId}/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deselected_ids: [...otherDeselected, ...deselected] })
    });
    saving = false;
  }

  async function toggleFavorite(assetId: string, e: Event) {
    e.stopPropagation();
    const item = items.find(i => i.asset_id === assetId);
    if (!item) return;
    item.favorite = !item.favorite;
    await fetch(`/api/favorite/${assetId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isFavorite: item.favorite })
    });
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!detailItem) return;
    if (e.key === "Escape") closeDetail();
    if (e.key === "ArrowLeft") prevDetail();
    if (e.key === "ArrowRight") nextDetail();
    if (e.key === " ") { e.preventDefault(); toggleDetailSelection(); }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="mb-4">
  <a href="/project/{data.projectId}" class="text-blue-400 text-sm">&larr; Scenes</a>
  <h1 class="text-lg font-bold mt-1">{data.scene.label || "Scene"}</h1>
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
  {#each items as item, i}
    <div class="relative aspect-square cursor-pointer group"
         onclick={() => openDetail(i)}>
      <img src="/api/thumbnail/{item.asset_id}"
           alt="" class="w-full h-full object-cover rounded
                        {item.selected ?  : opacity-30}"
           loading="lazy" />

      <!-- Selection checkbox -->
      <button class="absolute top-1 left-1 w-7 h-7 rounded-full border-2 flex items-center justify-center
                  {item.selected ? bg-blue-500 border-blue-500 : border-white/50 bg-black/50}"
              onclick={(e) => toggleItem(item.asset_id, e)}>
        {#if item.selected}<span class="text-xs font-bold">✓</span>{/if}
      </button>

      <!-- Video indicator -->
      {#if item.type === "VIDEO"}
        <div class="absolute bottom-1 right-1 bg-black/70 px-1.5 py-0.5 rounded text-xs flex items-center gap-1">
          <span>▶</span>
          {#if item.duration}<span>{item.duration}</span>{/if}
        </div>
      {/if}

      <!-- Favorite heart -->
      {#if item.favorite}
        <button class="absolute top-1 right-1 text-red-500 text-lg"
                onclick={(e) => toggleFavorite(item.asset_id, e)}>♥</button>
      {/if}
    </div>
  {/each}
</div>

<!-- Full-screen detail view -->
{#if detailItem}
  <div class="fixed inset-0 bg-black z-50 flex flex-col" onclick={closeDetail}>
    <!-- Top bar -->
    <div class="flex items-center justify-between p-4 bg-black/80" onclick={(e) => e.stopPropagation()}>
      <button onclick={closeDetail} class="text-white text-lg">✕</button>
      <span class="text-sm text-gray-400">{detailIndex + 1} / {items.length}</span>
      <button onclick={toggleDetailSelection}
              class="px-3 py-1 rounded-full text-sm font-medium
                     {detailItem.selected ? bg-blue-500 : bg-gray-700}">
        {detailItem.selected ? "Selected ✓" : "Deselected"}
      </button>
    </div>

    <!-- Photo -->
    <div class="flex-1 flex items-center justify-center overflow-hidden"
         onclick={(e) => e.stopPropagation()}>
      <img src="/api/thumbnail/{detailItem.asset_id}?size=preview"
           alt="" class="max-w-full max-h-full object-contain" />
    </div>

    <!-- Navigation -->
    <div class="flex justify-between p-4 bg-black/80" onclick={(e) => e.stopPropagation()}>
      <button onclick={prevDetail}
              class="px-6 py-2 bg-gray-800 rounded-lg {detailIndex === 0 ? opacity-30 : }"
              disabled={detailIndex === 0}>
        ← Prev
      </button>
      <button onclick={(e) => { e.stopPropagation(); toggleFavorite(detailItem.asset_id, e); }}
              class="px-4 py-2 text-2xl">
        {detailItem.favorite ? "♥" : "♡"}
      </button>
      <button onclick={nextDetail}
              class="px-6 py-2 bg-gray-800 rounded-lg {detailIndex === items.length - 1 ? opacity-30 : }"
              disabled={detailIndex === items.length - 1}>
        Next →
      </button>
    </div>
  </div>
{/if}
