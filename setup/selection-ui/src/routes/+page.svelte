<script lang="ts">
  let { data } = $props();
  let projects = $state(data.projects);
  let swiping = $state<string | null>(null);
  let swipeX = $state(0);

  async function archiveProject(id: string) {
    await fetch(`/api/project/${id}/archive`, { method: "POST" });
    projects = projects.filter(p => p.id !== id);
  }

  function handleTouchStart(e: TouchEvent, id: string) {
    swiping = id;
    swipeX = e.touches[0].clientX;
  }

  function handleTouchMove(e: TouchEvent, id: string) {
    if (swiping !== id) return;
    const diff = e.touches[0].clientX - swipeX;
    const el = e.currentTarget as HTMLElement;
    if (diff < 0) {
      el.style.transform = `translateX(${Math.max(diff, -120)}px)`;
    }
  }

  function handleTouchEnd(e: TouchEvent, id: string) {
    const el = e.currentTarget as HTMLElement;
    const diff = parseInt(el.style.transform.replace(/[^-\d]/g, "") || "0");
    if (diff < -80) {
      el.style.transform = "translateX(-120px)";
    } else {
      el.style.transform = "translateX(0)";
    }
    swiping = null;
  }
</script>

<h1 class="text-2xl font-bold mb-6">Projects</h1>

{#if projects.length === 0}
  <p class="text-gray-400">No projects found. Ask Claude to create one.</p>
{:else}
  <div class="space-y-3">
    {#each projects as project}
      <div class="relative overflow-hidden rounded-lg">
        <!-- Archive button behind -->
        <div class="absolute inset-y-0 right-0 w-28 bg-red-600 flex items-center justify-center">
          <button onclick={() => archiveProject(project.id)} class="text-white font-medium text-sm">
            Archive
          </button>
        </div>
        <!-- Project card -->
        <a href="/project/{project.id}"
           class="block bg-gray-900 p-4 relative transition-transform"
           ontouchstart={(e) => handleTouchStart(e, project.id)}
           ontouchmove={(e) => handleTouchMove(e, project.id)}
           ontouchend={(e) => handleTouchEnd(e, project.id)}>
          <div class="font-semibold">{project.title}</div>
          <div class="text-sm text-gray-400">{project.sceneCount} scenes · {project.state}</div>
        </a>
      </div>
    {/each}
  </div>
{/if}
