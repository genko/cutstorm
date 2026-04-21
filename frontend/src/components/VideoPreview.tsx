import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  attachAudioMix,
  resumeAudioContext,
  setExtraVolume,
  setSourceVolume,
  syncExtraToVideo,
} from "../audioMix";
import { resolveCanvas } from "../canvas";
import { getExtraBlob } from "../extraBlobs";
import { useStore } from "../store";
import { CropEditor } from "./CropEditor";
import { PreviewToolbar } from "./PreviewToolbar";
import { SubtitleOverlay } from "./SubtitleOverlay";
import { Watermark } from "./Watermark";
import { Timeline } from "./Timeline";

export function VideoPreview() {
  const videoUrl = useStore((s) => s.videoUrl);
  const setCurrentTime = useStore((s) => s.setCurrentTime);
  const setVideoEl = useStore((s) => s.setVideoEl);
  const canvas = useStore((s) => s.canvas);
  const videoW = useStore((s) => s.videoW);
  const videoH = useStore((s) => s.videoH);
  const useSubs = useStore((s) => s.useSubs);
  const watermark = useStore((s) => s.watermark);
  const trimRange = useStore((s) => s.trimRange);
  const sourceVolume = useStore((s) => s.audio.sourceVolume);
  const extraAudioId = useStore((s) => s.audio.extraAudioId);
  const extraVolume = useStore((s) => s.audio.extraVolume);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  const resolved = resolveCanvas(canvas, videoW, videoH, false);
  // In custom mode the preview-frame renders the FULL source (so the user can
  // drag/resize a crop rect over it). targetW/H reported by resolveCanvas in
  // custom mode is the crop dims — not what we want for the preview frame.
  const frameW = canvas.mode === "custom" ? (videoW || resolved.targetW) : resolved.targetW;
  const frameH = canvas.mode === "custom" ? (videoH || resolved.targetH) : resolved.targetH;

  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const s = Math.min(r.width / frameW, r.height / frameH);
      setScale(Math.max(0.01, s));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [frameW, frameH]);

  useEffect(() => {
    if (videoRef.current && videoUrl) {
      videoRef.current.load();
    }
    setVideoEl(videoRef.current);
    return () => setVideoEl(null);
  }, [videoUrl, setVideoEl]);

  // Build / rebuild the WebAudio mix graph when the <video> element or the
  // chosen extra audio track changes. The video's own `volume` property is
  // bypassed once WebAudio takes over the element (it routes through the
  // GainNode instead), so we set gains via setSourceVolume/setExtraVolume.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !videoUrl) return;
    const extraUrl = getExtraBlob(extraAudioId);
    const mix = attachAudioMix(v, extraUrl);
    mix.srcGain.gain.value = Math.max(0, Math.min(2, sourceVolume));
    mix.extraGain.gain.value = Math.max(0, Math.min(2, extraVolume));
  }, [videoUrl, extraAudioId]);

  useEffect(() => { setSourceVolume(sourceVolume); }, [sourceVolume]);
  useEffect(() => { setExtraVolume(extraVolume); }, [extraVolume]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onTime = () => {
      if (trimRange.in_sec > 0 && v.currentTime < trimRange.in_sec - 0.05) {
        v.currentTime = trimRange.in_sec;
      }
      if (trimRange.out_sec > 0 && v.currentTime > trimRange.out_sec) {
        v.pause();
        v.currentTime = trimRange.out_sec;
      }
      setCurrentTime(v.currentTime);
      syncExtraToVideo(v, trimRange.in_sec);
    };
    const onPlay = () => {
      if (trimRange.in_sec > 0 && v.currentTime < trimRange.in_sec) {
        v.currentTime = trimRange.in_sec;
      }
      resumeAudioContext();
      syncExtraToVideo(v, trimRange.in_sec);
    };
    const onPause = () => syncExtraToVideo(v, trimRange.in_sec);
    const onExtraReady = () => syncExtraToVideo(v, trimRange.in_sec);
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("seeked", onTime);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    window.addEventListener("cutstorm:extra-ready", onExtraReady);
    onTime();
    return () => {
      v.removeEventListener("timeupdate", onTime);
      v.removeEventListener("seeked", onTime);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      window.removeEventListener("cutstorm:extra-ready", onExtraReady);
    };
  }, [setCurrentTime, videoUrl, trimRange.in_sec, trimRange.out_sec]);

  if (!videoUrl) return null;

  return (
    <div className="pane preview-pane">
      <div className="preview-stage" ref={stageRef}>
        <div
          style={{
            width: frameW * scale + "px",
            height: frameH * scale + "px",
            position: "relative",
          }}
        >
          <div
            className="preview-frame"
            data-testid="preview-wrap"
            data-canvas-mode={canvas.mode}
            style={{
              width: frameW + "px",
              height: frameH + "px",
              maxWidth: "none",
              maxHeight: "none",
              transform: `scale(${scale})`,
              transformOrigin: "top left",
              position: "absolute",
              top: 0,
              left: 0,
            }}
          >
            <video
              ref={videoRef}
              src={videoUrl}
              preload="metadata"
              data-testid="preview-video"
              style={{
                width: "100%",
                height: "100%",
                objectFit: resolved.sourceFit,
                objectPosition: resolved.sourceObjectPosition,
                background: canvas.bg_color,
              }}
            />
            {canvas.mode === "custom" ? (
              <CropEditor videoRef={videoRef as React.RefObject<HTMLMediaElement>} />
            ) : (
              useSubs && <SubtitleOverlay videoRef={videoRef as React.RefObject<HTMLMediaElement>} />
            )}
            {canvas.mode !== "custom" && watermark && <Watermark />}
          </div>
        </div>
      </div>
      <PreviewToolbar />
      <Timeline />
    </div>
  );
}
