import { getAssetThumbnail } from '$lib/immich';

export async function GET({ params, url }) {
  const size = url.searchParams.get('size') === 'preview' ? 'preview' : 'thumbnail';
  const resp = await getAssetThumbnail(params.assetId, size);
  const buffer = await resp.arrayBuffer();
  return new Response(buffer, {
    headers: {
      'Content-Type': resp.headers.get('Content-Type') || 'image/jpeg',
      'Cache-Control': 'public, max-age=86400'
    }
  });
}
