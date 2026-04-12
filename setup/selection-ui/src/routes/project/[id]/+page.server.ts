import { loadProject } from '$lib/project';
import { error } from '@sveltejs/kit';

export function load({ params }) {
  try {
    const project = loadProject(params.id);
    const deselectedIds = new Set(project.deselected_ids || []);
    const scenes = (project.discovery?.scenes || []).map(scene => ({
      ...scene,
      selectedCount: scene.asset_ids.filter((id: string) => !deselectedIds.has(id)).length,
      totalCount: scene.asset_ids.length,
    }));
    return { project: { id: project.id, title: project.title, state: project.state }, scenes };
  } catch {
    throw error(404, 'Project not found');
  }
}
