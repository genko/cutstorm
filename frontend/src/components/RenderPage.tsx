import { useEffect, useRef, useState } from "react";
import { SubtitleOverlay } from "./SubtitleOverlay";
import { Watermark } from "./Watermark";
import { useStore } from "../store";

/**
 * Standalone page used by the backend renderer (Playwright) to capture
 * subtitle overlay frames at exact target-canvas resolution. Not for users.
 *
 * State (segments, style, position, size, canvas) is set via
 * `window.__setRenderState(json)` before each export run. Per-frame time is
 * driven via `window.__setFrameTime(seconds)`. Backend waits for
 * `window.__renderReady === true` (set on each re-render completion) before
 * screenshotting.
 */
export function RenderPage() {
  const [frameTime, setFrameTime] = useState(0);
  const [, setTick] = useState(0);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const [watermark, setWatermark] = useState(false);
  const fakeRef = useRef<HTMLMediaElement>(null);
  const setSegments = useStore.setState;

  // Transparent canvas so Playwright screenshots with alpha. Otherwise the dark
  // app-body background bleeds through, and ffmpeg composits overlay onto black
  // instead of our chromakey / source video.
  useEffect(() => {
    const body = document.body;
    const html = document.documentElement;
    const prevBody = body.style.cssText;
    const prevHtml = html.style.cssText;
    body.style.background = "transparent";
    body.style.backgroundImage = "none";
    html.style.background = "transparent";
    return () => {
      body.style.cssText = prevBody;
      html.style.cssText = prevHtml;
    };
  }, []);

  useEffect(() => {
    // Bridge: backend calls these via page.evaluate()
    (window as any).__setFrameTime = (t: number) => {
      (window as any).__renderReady = false;
      setFrameTime(t);
      // Force re-render even if `t` equals current state (first call t=0 on
      // initial state=0 would otherwise be a no-op and ready flag would never flip).
      setTick((n) => n + 1);
    };
    (window as any).__setRenderState = (payload: any) => {
      const s = payload || {};
      if (s.dims) setDims({ w: s.dims.w, h: s.dims.h });
      setWatermark(!!s.watermark);
      useStore.setState({
        segments: s.segments ?? [],
        style: s.style,
        position: s.position,
        size: s.size,
        canvas: s.canvas,
        videoW: s.videoW ?? 0,
        videoH: s.videoH ?? 0,
        duration: s.duration ?? 0,
        isAudioOnly: !!s.isAudioOnly,
      });
    };

    // Signal ready after render settles (microtask + frame).
    return () => {
      delete (window as any).__setFrameTime;
      delete (window as any).__setRenderState;
    };
  }, [setSegments]);

  // After each render, flag ready on next animation frame.
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      (window as any).__renderReady = true;
    });
    return () => cancelAnimationFrame(id);
  });

  if (!dims) {
    return <div data-testid="render-waiting" style={{ color: "#888" }}>awaiting state</div>;
  }

  return (
    <div
      data-testid="render-canvas"
      style={{
        position: "relative",
        width: dims.w + "px",
        height: dims.h + "px",
        overflow: "hidden",
        background: "transparent",
      }}
    >
      <SubtitleOverlay videoRef={fakeRef} renderMode currentTimeOverride={frameTime} />
      {watermark && <Watermark />}
    </div>
  );
}
