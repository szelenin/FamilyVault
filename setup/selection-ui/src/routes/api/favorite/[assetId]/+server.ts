import { json } from '@sveltejs/kit';
import { toggleFavorite } from '$lib/immich';

export async function PUT({ params, request }) {
  const { isFavorite } = await request.json();
  await toggleFavorite(params.assetId, isFavorite);
  return json({ ok: true });
}
