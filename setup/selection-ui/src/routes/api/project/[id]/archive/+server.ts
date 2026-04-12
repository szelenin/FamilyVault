import { json } from "@sveltejs/kit";
import { archiveProject } from "$lib/project";

export async function POST({ params }) {
  try {
    archiveProject(params.id);
    return json({ ok: true });
  } catch (e: any) {
    return json({ error: e.message }, { status: 500 });
  }
}
