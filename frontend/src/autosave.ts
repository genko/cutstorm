import { saveProjectState, updateTranscript } from "./api";
import { useStore } from "./store";

/**
 * Debounced backend PUTs for both transcript edits (segments) and project
 * state (style / position / size / canvas / trim / audio / toggles). Runs
 * whenever the relevant slice of the store changes AND there's a videoId.
 */

let segTimer: ReturnType<typeof setTimeout> | null = null;
let projTimer: ReturnType<typeof setTimeout> | null = null;
let lastSegSerialized: string | null = null;
let lastProjSerialized: string | null = null;

function projectSnapshot(s: ReturnType<typeof useStore.getState>) {
  return {
    style: s.style,
    position: s.position,
    size: s.size,
    canvas: s.canvas,
    trim_range: s.trimRange,
    audio: {
      source_volume: s.audio.sourceVolume,
      extra_audio_id: s.audio.extraAudioId,
      extra_volume: s.audio.extraVolume,
    },
    use_subs: s.useSubs,
    display_mode: s.style.mode,
  };
}

export function setupAutosave() {
  useStore.subscribe((state, prev) => {
    const id = state.videoId;
    if (!id) return;

    // --- segments ---
    if (state.segments !== prev.segments) {
      const ser = JSON.stringify(state.segments);
      if (ser !== lastSegSerialized) {
        if (segTimer) clearTimeout(segTimer);
        segTimer = setTimeout(async () => {
          try {
            await updateTranscript(id, state.segments);
            lastSegSerialized = ser;
          } catch (err) {
            console.warn("autosave.segments failed:", err);
          }
        }, 1200);
      }
    }

    // --- project state ---
    const projectChanged =
      state.style !== prev.style ||
      state.position !== prev.position ||
      state.size !== prev.size ||
      state.canvas !== prev.canvas ||
      state.trimRange !== prev.trimRange ||
      state.audio !== prev.audio ||
      state.useSubs !== prev.useSubs ||
      state.videoId !== prev.videoId;
    if (!projectChanged) return;

    const snap = projectSnapshot(state);
    const ser = JSON.stringify(snap);
    if (ser === lastProjSerialized) return;

    if (projTimer) clearTimeout(projTimer);
    projTimer = setTimeout(async () => {
      try {
        await saveProjectState(id, { ...snap, updated_at: Date.now() / 1000 });
        lastProjSerialized = ser;
      } catch (err) {
        console.warn("autosave.project failed:", err);
      }
    }, 500);
  });
}
