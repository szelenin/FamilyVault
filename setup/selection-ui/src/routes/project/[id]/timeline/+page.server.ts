import { loadProject, getSceneNotes } from "$lib/project";
import { error } from "@sveltejs/kit";

export function load({ params }) {
  try {
    const project = loadProject(params.id);
    const deselectedIds = new Set(project.deselected_ids || []);
    const notes = (project as any).scene_notes || {};
    const sceneOrder = (project as any).scene_order || null;
    
    let scenes = (project.discovery?.scenes || [])
      .filter((scene: any) => {
        // Only show scenes with at least 1 selected item
        const selectedCount = (scene.asset_ids || []).filter((id: string) => !deselectedIds.has(id)).length;
        return selectedCount > 0;
      })
      .map((scene: any) => {
        const selectedIds = (scene.asset_ids || []).filter((id: string) => !deselectedIds.has(id));
        return {
          ...scene,
          selectedIds,
          selectedCount: selectedIds.length,
          totalCount: (scene.asset_ids || []).length,
          note: notes[scene.id] || "",
          photoCount: scene.photo_count || 0,
          videoCount: scene.video_count || 0,
        };
      });

    // Apply custom order if exists
    if (sceneOrder) {
      const orderMap = new Map(sceneOrder.map((id: string, i: number) => [id, i]));
      scenes.sort((a: any, b: any) => {
        const aOrder = orderMap.get(a.id) ?? 999;
        const bOrder = orderMap.get(b.id) ?? 999;
        return aOrder - bOrder;
      });
    }

    const totalSelected = scenes.reduce((s: number, sc: any) => s + sc.selectedCount, 0);
    const estimatedDuration = totalSelected * 4; // rough: 4s per item

    return {
      projectId: params.id,
      projectTitle: project.title,
      scenes,
      totalSelected,
      estimatedDuration,
    };
  } catch {
    throw error(404, "Project not found");
  }
}
