import { json } from '@sveltejs/kit';
import { loadProject } from '$lib/project';

export async function GET({ params }) {
  try {
    const project = loadProject(params.id);
    return json(project);
  } catch {
    return json({ error: 'Project not found' }, { status: 404 });
  }
}
