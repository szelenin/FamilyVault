import fs from 'fs';

const IMMICH_URL = process.env.IMMICH_URL || 'http://localhost:2283';
const API_KEY_FILE = process.env.IMMICH_API_KEY_FILE || '/Volumes/HomeRAID/immich/api-key.txt';

let _apiKey: string | null = null;

function getApiKey(): string {
  if (!_apiKey) {
    _apiKey = fs.readFileSync(API_KEY_FILE, 'utf-8').trim();
  }
  return _apiKey;
}

function headers(): Record<string, string> {
  return { 'x-api-key': getApiKey(), 'Accept': 'application/json' };
}

export async function getAssetThumbnail(assetId: string, size: 'thumbnail' | 'preview' = 'thumbnail'): Promise<Response> {
  const resp = await fetch(`${IMMICH_URL}/api/assets/${assetId}/thumbnail?size=${size}`, { headers: headers() });
  return resp;
}

export async function getAssetDetail(assetId: string): Promise<any> {
  const resp = await fetch(`${IMMICH_URL}/api/assets/${assetId}`, { headers: headers() });
  return resp.json();
}

export async function toggleFavorite(assetId: string, isFavorite: boolean): Promise<void> {
  await fetch(`${IMMICH_URL}/api/assets/${assetId}`, {
    method: 'PUT',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ isFavorite })
  });
}

export { IMMICH_URL };
