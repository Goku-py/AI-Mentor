import { useState, useEffect, useCallback } from "react";

// Safari private mode throws SecurityError on every localStorage access, and a
// throw during a useState initialiser escapes the ErrorBoundary (it is below
// it in the tree) — the page would just go blank. Every access is guarded.
function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable or full — settings just do not persist */
  }
}

export interface UseSettingsReturn {
  fontSize: number;
  darkMode: boolean;
  isFullscreen: boolean;
  increaseFont: () => void;
  decreaseFont: () => void;
  toggleDarkMode: () => void;
  toggleFullscreen: () => void;
}

export function useSettings(): UseSettingsReturn {
  const [fontSize, setFontSize] = useState<number>(() => {
    const saved = parseInt(readStorage("fontSize") || "15", 10);
    return isNaN(saved) ? 15 : saved;
  });
  // Defaults to dark because :root and <meta name="theme-color"> are dark;
  // defaulting to light flashed dark->light on every first visit.
  const [darkMode, setDarkMode] = useState<boolean>(() => readStorage("darkMode") !== "false");
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    writeStorage("fontSize", String(fontSize));
  }, [fontSize]);

  useEffect(() => {
    document.documentElement.classList.toggle("light-mode", !darkMode);
    writeStorage("darkMode", String(darkMode));
  }, [darkMode]);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const increaseFont = useCallback(() => setFontSize((f) => Math.min(f + 1, 36)), []);
  const decreaseFont = useCallback(() => setFontSize((f) => Math.max(f - 1, 8)), []);
  const toggleDarkMode = useCallback(() => setDarkMode((d) => !d), []);
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen()
        .then(() => setIsFullscreen(true))
        .catch(() => {});
    } else {
      document.exitFullscreen()
        .then(() => setIsFullscreen(false))
        .catch(() => {});
    }
  }, []);

  return { fontSize, darkMode, isFullscreen, increaseFont, decreaseFont, toggleDarkMode, toggleFullscreen };
}