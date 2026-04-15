import { loadProject, getSceneNotes } from "$lib/project";
import { error } from "@sveltejs/kit";

export function load({ params }) {
  try {
    const project = loadProject(params.id);
    const deselectedIds = new Set(project.deselected_ids || []);
    const notes = (project as any).scene_notes || {};
    const sceneOrder = (project as any).scene_order || null;
    const videoTrims = (project as any).video_trims || {};
    
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
      const orderMap = new Map<string, number>(sceneOrder.map((id: string, i: number) => [id, i]));
      scenes.sort((a: any, b: any) => {
        const aOrder = orderMap.get(a.id) ?? 999;
        const bOrder = orderMap.get(b.id) ?? 999;
        return aOrder - bOrder;
      });
    }

    const totalSelected = scenes.reduce((s: number, sc: any) => s + sc.selectedCount, 0);
    const totalPhotos = scenes.reduce((s: number, sc: any) => s + sc.photoCount, 0);
    const totalVideos = scenes.reduce((s: number, sc: any) => s + sc.videoCount, 0);
    // Account for trimmed videos: use actual trim duration instead of default 8s
    const allSelectedIds = new Set<string>(scenes.flatMap((sc: any) => sc.selectedIds));
    const trimmedEntries = Object.entries(videoTrims).filter(([id]) => allSelectedIds.has(id));
    const trimmedVideoDuration = trimmedEntries.reduce((sum, [, trim]: [string, any]) => sum + (trim.end - trim.start), 0);
    const trimmedVideoCount = trimmedEntries.length;
    const untrimmedVideoCount = Math.max(0, totalVideos - trimmedVideoCount);
    // photos × 4s + untrimmed videos × 8s + trimmed video durations − crossfade overlaps (0.5s per transition)
    const crossfades = Math.max(0, totalSelected - 1) * 0.5;
    const estimatedDuration = Math.round(totalPhotos * 4 + untrimmedVideoCount * 8 + trimmedVideoDuration - crossfades);

    return {
      projectId: params.id,
      projectTitle: project.title,
      scenes,
      totalSelected,
      estimatedDuration,
      videoTrims,
    };
  } catch {
    throw error(404, "Project not found");
  }
}
