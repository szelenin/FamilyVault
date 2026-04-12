import { loadProject } from '$lib/project';
import { getAssetDetail } from '$lib/immich';
import { error } from '@sveltejs/kit';

export async function load({ params }) {
  try {
    const project = loadProject(params.id);
    const scene = project.discovery?.scenes?.find((s: any) => s.id === params.sceneId);
    if (!scene) throw error(404, 'Scene not found');

    const deselectedIds = new Set(project.deselected_ids || []);

    // Get basic info for each asset (type, favorite status)
    const items = await Promise.all(
      scene.asset_ids.map(async (assetId: string) => {
        try {
          const detail = await getAssetDetail(assetId);
          return {
            asset_id: assetId,
            type: detail.type || 'IMAGE',
            selected: !deselectedIds.has(assetId),
            favorite: detail.isFavorite || false,
            duration: detail.duration || null,
            filename: detail.originalFileName || '',
          };
        } catch {
          return {
            asset_id: assetId,
            type: 'IMAGE',
            selected: !deselectedIds.has(assetId),
            favorite: false,
            duration: null,
            filename: '',
          };
        }
      })
    );

    return {
      projectId: params.id,
      scene: { ...scene, items },
    };
  } catch (e: any) {
    if (e.status) throw e;
    throw error(404, 'Not found');
  }
}
