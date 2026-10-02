// lib/i18n/LocaleProvider.tsx
// Holds the interface language and hands out translated chrome strings.
//
// The initial render is always English, on purpose. `localStorage` does not
// exist while a client component is being created on the server, so reading it
// in the useState initialiser would give the server English and the client
// Indonesian: a hydration mismatch. The stored locale is applied in an effect
// after mount, which is the same rule app/page.tsx follows for ?page=.

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
import {
  DEFAULT_LOCALE,
  LOCALE_TAG,
  STRINGS,
  isLocale,
  type Locale,
  type StringKey,
} from "./dictionary";

const STORAGE_KEY = "trusthub.locale";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  /** Translated chrome string. English is the frozen reference column. */
  t: (key: StringKey) => string;
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLocale(stored)) setLocaleState(stored);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // A blocked storage quota must not take the language switcher down with
      // it. The choice still applies for this session.
    }
  }, []);

  // Screen readers pick pronunciation rules from the document language, so
  // Indonesian read with English phonetics is mispronounced. Keep it honest.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key) => STRINGS[key][locale],
      // Indonesian groups thousands with a period, English with a comma, so
      // the formatter has to follow the locale or the same figure reads as two
      // different numbers to a reader.
      formatNumber: (n, options) =>
        new Intl.NumberFormat(LOCALE_TAG[locale], options).format(n),
    }),
    [locale, setLocale]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useI18n(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useI18n must be called inside <LocaleProvider>");
  return ctx;
}