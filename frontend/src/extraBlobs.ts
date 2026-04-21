/**
 * In-memory cache of blob URLs per extra_audio_id — populated at upload
 * time in the Timeline component and read by the preview's audio mix.
 *
 * A blob URL lets WebAudio decode the extra track without re-fetching from
 * the server. The server keeps the file on disk for export; we don't expose
 * a GET endpoint for extra audio (would duplicate plumbing), so the blob is
 * our only playback source in-browser.
 */
const cache = new Map<string, string>();

export function setExtraBlob(id: string, url: string): void {
  const existing = cache.get(id);
  if (existing && existing !== url) {
    URL.revokeObjectURL(existing);
  }
  cache.set(id, url);
}

export function getExtraBlob(id: string | null): string | null {
  if (!id) return null;
  return cache.get(id) ?? null;
}

export function clearExtraBlob(id: string): void {
  const url = cache.get(id);
  if (url) URL.revokeObjectURL(url);
  cache.delete(id);
}
