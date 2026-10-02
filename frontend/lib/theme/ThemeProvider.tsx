// lib/theme/ThemeProvider.tsx
// Holds the colour theme and writes it onto <html> as data-theme.
//
// The theme is a CSS variable swap, not a class swap. Every colour in the app
// resolves through a variable declared in globals.css, so flipping one attribute
// on the root element restyles every component with no re-render and no class
// name changing. That is why no component needs to know which theme is active.
//
// The initial state is always the dark theme, which is what the server renders
// and what :root declares. A stored light theme is applied after mount for the
// same reason LocaleProvider applies a stored locale after mount: localStorage
// does not exist during server rendering, so reading it in the useState
// initialiser would hand the server one theme and the client another.
//
// The flash of the wrong theme is prevented separately, by the inline script in
// app/layout.tsx, which runs before first paint. This provider is not what stops
// the flash; by the time it mounts, the attribute is already correct.

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light";

export const THEMES: readonly Theme[] = ["dark", "light"];
export const DEFAULT_THEME: Theme = "dark";
export const THEME_STORAGE_KEY = "trusthub.theme";
export const THEME_ATTRIBUTE = "data-theme";

export function isTheme(value: unknown): value is Theme {
  return value === "dark" || value === "light";
}

interface ThemeContextValue {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    } catch {
      // Storage can be blocked outright, in which case the attribute the inline
      // script already set is the answer.
    }
    if (isTheme(stored)) {
      setThemeState(stored);
      return;
    }
    const fromDom = document.documentElement.getAttribute(THEME_ATTRIBUTE);
    if (isTheme(fromDom)) setThemeState(fromDom);
  }, []);

  const applyTheme = useCallback((next: Theme) => {
    setThemeState(next);
    document.documentElement.setAttribute(THEME_ATTRIBUTE, next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // A blocked quota must not take the switcher down. The theme still applies
      // for this session; it just will not be remembered.
    }
  }, []);

  const setTheme = useCallback(
    (next: Theme) => applyTheme(next),
    [applyTheme]
  );

  const toggleTheme = useCallback(
    () => applyTheme(theme === "dark" ? "light" : "dark"),
    [applyTheme, theme]
  );

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be called inside <ThemeProvider>");
  return ctx;
}