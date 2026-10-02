// components/shared/LanguageSwitcher.tsx
// Interface language control.
//
// A native <select> rather than a custom menu or a row of buttons. Two reasons:
// it is keyboard and screen-reader operable with no extra code (Tab, arrows,
// Enter all work because the browser owns it), and it is the only form that
// survives a third and fourth locale without a redesign. globals.css already
// sets `color-scheme: dark`, which is what keeps the native popup from
// flashing white against this palette.
//
// The globe is drawn inline to the nav's icon spec: 24x24, currentColor,
// strokeWidth 1.7, no emoji, no icon library.

"use client";

import { useId } from "react";
import { useI18n } from "@/lib/i18n/LocaleProvider";
import { LOCALES, LOCALE_NAME, type Locale } from "@/lib/i18n/dictionary";

export default function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
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
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3a15 15 0 010 18a15 15 0 010-18z" />
      </svg>

      <label htmlFor={labelId} className="sr-only">
        {t("lang.switch_to")}
      </label>

      <select
        id={labelId}
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="min-w-0 flex-1 bg-transparent text-xs text-slate-400 hover:text-slate-200 focus-visible:text-slate-200 transition-colors cursor-pointer"
      >
        {LOCALES.map((code) => (
          <option key={code} value={code} className="bg-panel text-slate-200">
            {LOCALE_NAME[code]}
          </option>
        ))}
      </select>
    </div>
  );
}