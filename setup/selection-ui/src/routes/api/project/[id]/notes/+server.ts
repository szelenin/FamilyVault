import { json } from "@sveltejs/kit";
import { getSceneNotes, saveSceneNote } from "$lib/project";

export async function GET({ params }) {
  return json(getSceneNotes(params.id));
}

export async function POST({ params, request }) {
  const { scene_id, note } = await request.json();
  saveSceneNote(params.id, scene_id, note);
  return json({ ok: true });
}
