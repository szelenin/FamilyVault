<script lang="ts">
  let { data } = $props();
  let projects = $state(data.projects);
  let archived = $state<{id: string, title: string} | null>(null);
  let undoTimer: ReturnType<typeof setTimeout> | null = null;

  async function archiveProject(id: string, e: Event) {
    e.preventDefault();
    e.stopPropagation();
    const project = projects.find(p => p.id === id);
    if (!project) return;

    // Remove from list visually
    projects = projects.filter(p => p.id !== id);
    archived = { id, title: project.title };

    // Auto-confirm after 5 seconds
    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(async () => {
      await fetch(`/api/project/${id}/archive`, { method: "POST" });
      archived = null;
    }, 5000);
  }

  function undoArchive() {
    if (!archived) return;
    if (undoTimer) clearTimeout(undoTimer);
    // Re-add to list
    const project = data.projects.find(p => p.id === archived!.id);
    if (project) projects = [...projects, project].sort((a, b) => b.id.localeCompare(a.id));
    archived = null;
  }
</script>

<h1 class="text-2xl font-bold mb-6">Projects</h1>

{#if projects.length === 0 && !archived}
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

<!-- Undo toast -->
{#if archived}
  <div class="fixed bottom-6 left-4 right-4 bg-gray-800 rounded-lg p-4 flex items-center gap-3 shadow-xl border border-gray-700 z-50">
    <span class="flex-1 text-sm">Archived "{archived.title}"</span>
    <button onclick={undoArchive}
            class="px-4 py-1.5 bg-blue-600 rounded-lg text-sm font-medium hover:bg-blue-500 transition">
      Undo
    </button>
  </div>
{/if}
