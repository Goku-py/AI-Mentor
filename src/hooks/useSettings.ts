import { useState, useEffect, useCallback } from "react";

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
    const saved = parseInt(localStorage.getItem("fontSize") || "15", 10);
    return isNaN(saved) ? 15 : saved;
  });
  const [darkMode, setDarkMode] = useState<boolean>(() => localStorage.getItem("darkMode") === "true");
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    localStorage.setItem("fontSize", String(fontSize));
  }, [fontSize]);

  useEffect(() => {
    document.documentElement.classList.toggle("light-mode", !darkMode);
    localStorage.setItem("darkMode", String(darkMode));
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
