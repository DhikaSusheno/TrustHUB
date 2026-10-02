// components/shared/ThemeSwitcher.tsx
// Colour theme control.
//
// A native <select> for the same reasons as the language switcher above it: the
// browser owns the keyboard and screen-reader behaviour, so Tab, arrows and
// Enter work without extra code. It also keeps the footer reading as one small
// settings block instead of mixing a two-state toggle button with a dropdown.
//
// The glyph is a crescent drawn inline to the nav's icon spec: 24x24,
// currentColor, strokeWidth 1.7, no emoji, no icon library.
//
// It carries no colours of its own. Everything it paints comes from the theme
// variables, so it needs no dark: variants and cannot drift out of sync with the
// palette.

"use client";

import { useId } from "react";
import { useI18n } from "@/lib/i18n/LocaleProvider";
import { useTheme, THEMES } from "@/lib/theme/ThemeProvider";
import type { Theme } from "@/lib/theme/ThemeProvider";

export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  const labelId = useId();

  return (
    <div className="flex items-center gap-1.5">
      <svg
        aria-hidden="true"
        className="w-3.5 h-3.5 shrink-0 text-slate-500"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.7}
        strokeLinecap="round"
        strokeLinejoin="round"
        viewBox="0 0 24 24"
      >
        <path d="M20.5 14.3A8.5 8.5 0 019.7 3.5a8.5 8.5 0 1010.8 10.8z" />
      </svg>

      <label htmlFor={labelId} className="sr-only">
        {t("theme.label")}
      </label>

      <select
        id={labelId}
        value={theme}
        onChange={(e) => setTheme(e.target.value as Theme)}
        className="min-w-0 flex-1 bg-transparent text-xs text-slate-400 hover:text-slate-200 focus-visible:text-slate-200 transition-colors cursor-pointer"
      >
        {THEMES.map((code) => (
          <option key={code} value={code} className="bg-panel text-ink-2">
            {t(code === "dark" ? "theme.dark" : "theme.light")}
          </option>
        ))}
      </select>
    </div>
  );
}