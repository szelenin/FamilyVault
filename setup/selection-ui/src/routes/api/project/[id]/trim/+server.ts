import { json } from "@sveltejs/kit";
import { saveVideoTrim } from "$lib/project";

export async function POST({ params, request }) {
  const { asset_id, start, end } = await request.json();
  saveVideoTrim(params.id, asset_id, start, end);
  return json({ ok: true });
}
