<script>
  let { data } = $props();
</script>

<h1 class="text-2xl font-bold mb-6">Projects</h1>

{#if data.projects.length === 0}
  <p class="text-gray-400">No projects found. Ask Claude to create one.</p>
{:else}
  <div class="space-y-3">
    {#each data.projects as project}
      <a href="/project/{project.id}" 
         class="block bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition">
        <div class="font-semibold">{project.title}</div>
        <div class="text-sm text-gray-400">{project.sceneCount} scenes · {project.state}</div>
      </a>
    {/each}
  </div>
{/if}
