import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { setupAutosave } from "./autosave";
import { loadFonts } from "./fonts";
import { useStore } from "./store";
import "./styles.css";

setupAutosave();

// Register the curated font bundle served by the backend. Runs in parallel
// with the first React render — fonts hot-swap into the UI as they arrive.
void loadFonts();

// Exposed for E2E tests (undo/hotkeys specs call useStore.temporal.getState()).
(window as unknown as { useStore: typeof useStore }).useStore = useStore;

const root = createRoot(document.getElementById("root")!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
