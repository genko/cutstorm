/**
 * In-memory cache of blob URLs per extra_audio_id — populated at upload
 * time in the Timeline component and read by the preview's audio mix.
 *
 * A blob URL lets WebAudio decode the extra track without re-fetching from
 * the server. After a page reload the blob is gone (in-memory only), so
 * `getExtraAudioPlaybackUrl` falls back to the server route
 * `/api/extra-audio/{id}` which streams the on-disk file. The blob path is
 * preferred when available (no network roundtrip).
 */
const cache = new Map<string, string>();

export function setExtraBlob(id: string, url: string): void {
  const existing = cache.get(id);
  if (existing && existing !== url) {
    URL.revokeObjectURL(existing);
  }
  cache.set(id, url);
}

/** Cached blob URL only (no server fallback). Use when you specifically
 * need a same-origin blob (e.g. client-side waveform decode). */
export function getExtraBlob(id: string | null): string | null {
  if (!id) return null;
  return cache.get(id) ?? null;
}

/** Playback URL for the preview's WebAudio graph: blob if we have it,
 * otherwise the server-served file. Returns null when there's no extra
 * track on the project. */
export function getExtraAudioPlaybackUrl(id: string | null): string | null {
  if (!id) return null;
  const blob = cache.get(id);
  if (blob) return blob;
  return `/api/extra-audio/${encodeURIComponent(id)}`;
}

export function clearExtraBlob(id: string): void {
  const url = cache.get(id);
  if (url) URL.revokeObjectURL(url);
  cache.delete(id);
}
