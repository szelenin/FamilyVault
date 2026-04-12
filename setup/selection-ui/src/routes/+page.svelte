<script lang="ts">
  let { data } = $props();
  let projects = $state(data.projects);

  async function archiveProject(id: string, e: Event) {
    e.preventDefault();
    e.stopPropagation();
    await fetch(`/api/project/${id}/archive`, { method: "POST" });
    projects = projects.filter(p => p.id !== id);
  }
</script>

<h1 class="text-2xl font-bold mb-6">Projects</h1>

{#if projects.length === 0}
  <p class="text-gray-400">No projects found. Ask Claude to create one.</p>
{:else}
  <div class="space-y-3">
    {#each projects as project}
      <a href="/project/{project.id}"
         class="flex items-center gap-3 bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition">
        <div class="flex-1 min-w-0">
          <div class="font-semibold">{project.title}</div>
          <div class="text-sm text-gray-400">{project.sceneCount} scenes · {project.state}</div>
        </div>
        <button onclick={(e) => archiveProject(project.id, e)}
                class="p-2 text-gray-500 hover:text-red-400 transition shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 8v13H3V8"/>
            <path d="M1 3h22v5H1z"/>
            <path d="M10 12h4"/>
          </svg>
        </button>
      </a>
    {/each}
  </div>
{/if}
