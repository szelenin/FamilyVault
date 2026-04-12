import { getAssetThumbnail } from "$lib/immich";
import fs from "fs";

const IMMICH_URL = process.env.IMMICH_URL || "http://localhost:2283";
const API_KEY_FILE = process.env.IMMICH_API_KEY_FILE || "/Volumes/HomeRAID/immich/api-key.txt";

let _apiKey: string | null = null;
function getApiKey(): string {
  if (!_apiKey) _apiKey = fs.readFileSync(API_KEY_FILE, "utf-8").trim();
  return _apiKey;
}

export async function GET({ params, url }) {
  const size = url.searchParams.get("size") || "thumbnail";
  
  if (size === "original") {
    // Stream the original file (for video playback)
    const resp = await fetch(`${IMMICH_URL}/api/assets/${params.assetId}/original`, {
      headers: { "x-api-key": getApiKey() }
    });
    const buffer = await resp.arrayBuffer();
    return new Response(buffer, {
      headers: {
        "Content-Type": resp.headers.get("Content-Type") || "video/mp4",
        "Cache-Control": "public, max-age=86400",
        "Accept-Ranges": "bytes",
      }
    });
  }
  
  // Thumbnail or preview
  const resp = await getAssetThumbnail(params.assetId, size as "thumbnail" | "preview");
  const buffer = await resp.arrayBuffer();
  return new Response(buffer, {
    headers: {
      "Content-Type": resp.headers.get("Content-Type") || "image/jpeg",
      "Cache-Control": "public, max-age=86400"
    }
  });
}
