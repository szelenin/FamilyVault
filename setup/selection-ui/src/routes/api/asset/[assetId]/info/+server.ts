import { json } from "@sveltejs/kit";
import { getAssetDetail } from "$lib/immich";

export async function GET({ params }) {
  const detail = await getAssetDetail(params.assetId);
  return json({
    type: detail.type || "IMAGE",
    duration: detail.duration || null,
  });
}
