"use client";

import { useSyncExternalStore } from "react";

const THEME_KEY = "tee-time-theme";
const THEME_EVENT = "tee-time-theme-change";

function subscribe(onChange: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  function syncPreference() {
    let saved: string | null = null;
    try { saved = window.localStorage.getItem(THEME_KEY); } catch { /* Storage may be unavailable. */ }
    document.documentElement.dataset.theme = saved === "light" || saved === "dark"
      ? saved : media.matches ? "dark" : "light";
    onChange();
  }
  function storageChanged(event: StorageEvent) {
    if (event.key === THEME_KEY || event.key === null) syncPreference();
  }
  window.addEventListener(THEME_EVENT, onChange);
  window.addEventListener("storage", storageChanged);
  media.addEventListener("change", syncPreference);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener("storage", storageChanged);
    media.removeEventListener("change", syncPreference);
  };
}

export function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe,
    () => document.documentElement.dataset.theme === "dark", () => false);
  function toggle() {
    const theme = dark ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem(THEME_KEY, theme); } catch { /* Keep this tab usable without storage. */ }
    window.dispatchEvent(new Event(THEME_EVENT));
  }
  return <button type="button" className="theme-toggle" aria-label="Dark mode" aria-pressed={dark}
    title={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={toggle}>
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {dark ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5" /></>
        : <path d="M20.5 14.1A8.7 8.7 0 0 1 9.9 3.5a8.7 8.7 0 1 0 10.6 10.6Z" />}
    </svg>
  </button>;
}
