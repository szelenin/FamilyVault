import { listProjects, loadProject } from '$lib/project';

export function load() {
  const projectIds = listProjects();
  const projects = projectIds.slice(0, 20).map(id => {
    try {
      const p = loadProject(id);
      return { id, title: p.title, state: p.state, sceneCount: p.discovery?.scenes?.length || 0 };
    } catch { return { id, title: id, state: 'unknown', sceneCount: 0 }; }
  });
  return { projects };
}
