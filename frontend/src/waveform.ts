/**
 * Compute a downsampled peak array for an audio/video file URL.
 *
 * Fetches the asset, decodes its audio track via WebAudio, and reduces it to
 * `bins` peak samples in [0, 1]. Used to draw the waveform strip under the
 * preview. If the browser can't decode the track (unsupported format, huge
 * file, CORS), returns `null` — caller should show a placeholder bar.
 */
export async function computePeaks(
  url: string,
  bins: number = 240,
): Promise<Float32Array | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const buf = await res.arrayBuffer();
    // Safari still uses webkitAudioContext.
    const Ctor: typeof AudioContext =
      (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!Ctor) return null;
    const ctx = new Ctor();
    let decoded: AudioBuffer;
    try {
      decoded = await ctx.decodeAudioData(buf.slice(0));
    } catch {
      ctx.close?.();
      return null;
    }
    // Collapse channels, take max absolute amplitude per bin.
    const ch = decoded.numberOfChannels;
    const len = decoded.length;
    const samplesPerBin = Math.max(1, Math.floor(len / bins));
    const peaks = new Float32Array(bins);
    const channelData: Float32Array[] = [];
    for (let c = 0; c < ch; c++) channelData.push(decoded.getChannelData(c));
    for (let i = 0; i < bins; i++) {
      const start = i * samplesPerBin;
      const end = Math.min(len, start + samplesPerBin);
      let peak = 0;
      for (let c = 0; c < ch; c++) {
        const data = channelData[c];
        for (let j = start; j < end; j++) {
          const v = Math.abs(data[j]);
          if (v > peak) peak = v;
        }
      }
      peaks[i] = peak;
    }
    ctx.close?.();
    // Normalize so visual doesn't look dead on quiet sources.
    let max = 0;
    for (let i = 0; i < peaks.length; i++) if (peaks[i] > max) max = peaks[i];
    if (max > 0) {
      for (let i = 0; i < peaks.length; i++) peaks[i] = Math.min(1, peaks[i] / max);
    }
    return peaks;
  } catch {
    return null;
  }
}
