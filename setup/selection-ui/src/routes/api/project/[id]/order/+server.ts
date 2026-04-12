import { json } from "@sveltejs/kit";
import { saveSceneOrder } from "$lib/project";

export async function POST({ params, request }) {
  const { order } = await request.json();
  saveSceneOrder(params.id, order);
  return json({ ok: true });
}
