import fs from "fs";

const IMMICH_URL = process.env.IMMICH_URL || "http://localhost:2283";
const API_KEY_FILE = process.env.IMMICH_API_KEY_FILE || "/Volumes/HomeRAID/immich/api-key.txt";

let _apiKey: string | null = null;
function getApiKey(): string {
  if (!_apiKey) _apiKey = fs.readFileSync(API_KEY_FILE, "utf-8").trim();
  return _apiKey;
}

export async function GET({ params, request }) {
  const range = request.headers.get("Range");
  
  const headers: Record<string, string> = { "x-api-key": getApiKey() };
  if (range) headers["Range"] = range;
  
  const resp = await fetch(`${IMMICH_URL}/api/assets/${params.assetId}/original`, { headers });
  
  const responseHeaders: Record<string, string> = {
    "Content-Type": resp.headers.get("Content-Type") || "video/mp4",
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=86400",
  };
  
  const contentLength = resp.headers.get("Content-Length");
  if (contentLength) responseHeaders["Content-Length"] = contentLength;
  
  const contentRange = resp.headers.get("Content-Range");
  if (contentRange) responseHeaders["Content-Range"] = contentRange;
  
  return new Response(resp.body, {
    status: resp.status,
    headers: responseHeaders,
  });
}
