<script lang="ts">
  import { onMount } from 'svelte';

  let {
    videoSrc,
    duration,
    trimStart = $bindable(0),
    trimEnd = $bindable(0),
    videoEl = $bindable<HTMLVideoElement | null>(null),
    ondragend,
  }: {
    videoSrc: string;
    duration: number;
    trimStart: number;
    trimEnd: number;
    videoEl?: HTMLVideoElement | null;
    ondragend?: () => void;
  } = $props();

  const FRAME_COUNT = 10;
  const MIN_GAP = 0.5; // seconds
  const HANDLE_WIDTH = 20; // px

  let containerEl: HTMLDivElement | null = null;
  let hiddenVideoEl: HTMLVideoElement | null = null;
  let containerWidth = $state(0);
  let frames: string[] = $state([]);
  let extracting = $state(true);
  let dragHandle: 'start' | 'end' | null = null;
  let dragStartX = 0;
  let dragStartValue = 0;

  const startPct = $derived(duration > 0 ? (trimStart / duration) * 100 : 0);
  const endPct = $derived(duration > 0 ? (trimEnd / duration) * 100 : 100);
  const spanPct = $derived(endPct - startPct);

  function formatTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, '0')}`;
  }

  onMount(() => {
    extractFrames();
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  });

  async function extractFrames() {
    if (!hiddenVideoEl) return;
    extracting = true;
    frames = [];

    const video = hiddenVideoEl;
    video.src = videoSrc;
    video.muted = true;
    video.preload = 'auto';

    // Wait for metadata
    await new Promise<void>((resolve, reject) => {
      const onMeta = () => { video.removeEventListener('error', onErr); resolve(); };
      const onErr = () => { video.removeEventListener('loadedmetadata', onMeta); reject(); };
      video.addEventListener('loadedmetadata', onMeta, { once: true });
      video.addEventListener('error', onErr, { once: true });
      setTimeout(() => reject(new Error('timeout')), 10000);
    }).catch(() => { extracting = false; return; });

    if (!video.duration) { extracting = false; return; }

    const offscreen = document.createElement('canvas');
    offscreen.width = 120;
    offscreen.height = 68;
    const ctx = offscreen.getContext('2d');
    if (!ctx) { extracting = false; return; }

    const extracted: string[] = [];
    for (let i = 0; i < FRAME_COUNT; i++) {
      // Spread frames across duration; avoid last few ms to prevent EOF issues
      const t = i === 0 ? 0.01 : Math.min((i / (FRAME_COUNT - 1)) * duration, duration - 0.05);
      video.currentTime = t;
      await new Promise<void>(r => video.addEventListener('seeked', () => r(), { once: true }));
      ctx.drawImage(video, 0, 0, 120, 68);
      extracted.push(offscreen.toDataURL('image/jpeg', 0.6));
      // Yield to avoid blocking UI
      await new Promise<void>(r => setTimeout(r, 0));
    }

    frames = extracted;
    extracting = false;
    // Release video resource
    video.src = '';
  }

  function startDrag(e: PointerEvent, handle: 'start' | 'end') {
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragHandle = handle;
    dragStartX = e.clientX;
    dragStartValue = handle === 'start' ? trimStart : trimEnd;
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragHandle || !containerEl) return;
    const dx = e.clientX - dragStartX;
    const dt = (dx / containerEl.getBoundingClientRect().width) * duration;
    const newVal = dragStartValue + dt;

    if (dragHandle === 'start') {
      trimStart = Math.max(0, Math.min(newVal, trimEnd - MIN_GAP));
      if (videoEl) videoEl.currentTime = trimStart;
    } else {
      trimEnd = Math.min(duration, Math.max(newVal, trimStart + MIN_GAP));
      if (videoEl) videoEl.currentTime = trimEnd;
    }
  }

  function onPointerUp() {
    dragHandle = null;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    ondragend?.();
  }
</script>

<!-- Hidden video for frame extraction — must be in DOM for Safari seeked event -->
<video
  bind:this={hiddenVideoEl}
  playsinline
  muted
  style="position:absolute;width:0;height:0;visibility:hidden;pointer-events:none"
  aria-hidden="true"
></video>

<div class="select-none touch-none" bind:this={containerEl} bind:clientWidth={containerWidth}>
  <!-- Filmstrip -->
  <div class="relative h-16 rounded overflow-hidden flex bg-gray-800">
    <!-- Frames -->
    {#if frames.length > 0}
      {#each frames as frame}
        <img src={frame} class="flex-1 h-full object-cover" style="min-width:0" draggable="false" alt="" />
      {/each}
    {:else}
      <!-- Skeleton while extracting -->
      {#each { length: FRAME_COUNT } as _}
        <div class="flex-1 h-full bg-gray-700 border-r border-gray-900 animate-pulse"></div>
      {/each}
    {/if}

    <!-- Dark overlay: before trim start -->
    <div class="absolute inset-y-0 left-0 bg-black/65 pointer-events-none"
         style="width:{startPct}%"></div>

    <!-- Yellow border: selected region -->
    <div class="absolute inset-y-0 border-2 border-yellow-400 pointer-events-none"
         style="left:{startPct}%;width:{spanPct}%"></div>

    <!-- Dark overlay: after trim end -->
    <div class="absolute inset-y-0 right-0 bg-black/65 pointer-events-none"
         style="width:{100 - endPct}%"></div>

    <!-- Left handle -->
    <div class="absolute inset-y-0 bg-yellow-400 rounded-l z-20 flex items-center justify-center cursor-col-resize active:bg-yellow-300 touch-none"
         style="left:{startPct}%;width:{HANDLE_WIDTH}px;transform:translateX(-{HANDLE_WIDTH / 2}px)"
         onpointerdown={(e) => startDrag(e, 'start')}
         tabindex="0" role="slider" aria-label="Trim start" aria-valuenow={trimStart} aria-valuemin={0} aria-valuemax={trimEnd}>
      <span class="text-black font-bold leading-none" style="font-size:10px">◂</span>
    </div>

    <!-- Right handle -->
    <div class="absolute inset-y-0 bg-yellow-400 rounded-r z-20 flex items-center justify-center cursor-col-resize active:bg-yellow-300 touch-none"
         style="left:{endPct}%;width:{HANDLE_WIDTH}px;transform:translateX(-{HANDLE_WIDTH / 2}px)"
         onpointerdown={(e) => startDrag(e, 'end')}
         tabindex="0" role="slider" aria-label="Trim end" aria-valuenow={trimEnd} aria-valuemin={trimStart} aria-valuemax={duration}>
      <span class="text-black font-bold leading-none" style="font-size:10px">▸</span>
    </div>
  </div>

  <!-- Time labels -->
  <div class="flex justify-between text-xs mt-1.5 px-0.5">
    <span class="text-yellow-400">{formatTime(trimStart)}</span>
    <span class="text-gray-500">{formatTime(trimEnd - trimStart)} selected · {formatTime(duration)} total</span>
    <span class="text-yellow-400">{formatTime(trimEnd)}</span>
  </div>

  <!-- Hidden inputs for keyboard/test accessibility — also trigger autosave -->
  <input type="range" value={trimStart} min="0" max={duration} step="0.1"
         data-testid="trim-start" style="position:absolute;opacity:0;pointer-events:none;width:0" aria-hidden="true"
         oninput={(e) => { trimStart = Math.min(+e.currentTarget.value, trimEnd - MIN_GAP); ondragend?.(); }} />
  <input type="range" value={trimEnd} min="0" max={duration} step="0.1"
         data-testid="trim-end" style="position:absolute;opacity:0;pointer-events:none;width:0" aria-hidden="true"
         oninput={(e) => { trimEnd = Math.max(+e.currentTarget.value, trimStart + MIN_GAP); ondragend?.(); }} />
</div>
