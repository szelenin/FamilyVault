import { json } from '@sveltejs/kit';
import { saveDeselectedIds } from '$lib/project';

export async function POST({ params, request }) {
  const { deselected_ids } = await request.json();
  saveDeselectedIds(params.id, deselected_ids);
  return json({ ok: true });
}
