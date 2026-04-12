<script>
  import '../app.css';
  let { children } = $props();
</script>

<div class="min-h-screen bg-gray-950 text-white">
  <header class="bg-gray-900 p-4 flex items-center gap-3 sticky top-0 z-50">
    <a href="/" class="text-xl font-bold">Story Engine</a>
  </header>
  <main class="p-4">
    {@render children()}
  </main>
</div>
