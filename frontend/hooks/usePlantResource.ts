// hooks/usePlantResource.ts
// One fetch hook for every data-backed page.
//
// Why a hook instead of `useEffect` in each page: eleven pages that each
// spell out loading, error, and cancellation will spell it out eleven
// different ways, and the differences will all be wrong somewhere. Two of
// them will forget to abort, so a slow request for GA-1201A lands after the
// user has clicked to FA-8901 and overwrites the newer answer.
//
// A React 19 caveat worth knowing before adding features here: `use` plus a
// cache is the intended shape for data that is read many times, and for data
// that is written we still want a manual effect to control refetching. This
// hook covers the second case; the shared status read on the overview and the
// nav footer is small enough not to need a cache layer.

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface Resource<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  /** Re-run the fetcher. Bumps a counter so the effect re-fires. */
  reload: () => void;
}

/**
 * Fetch on mount and whenever `deps` change.
 *
 * The fetcher is held in a ref so a caller can pass an inline arrow function
 * without re-triggering on every render. An aborted request is ignored rather
 * than surfaced, so navigating away mid-flight does not flash an error for a
 * page the user already left.
 */
export function usePlantResource<T>(fetcher: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  // Tracks the request that is still current. Anything that resolves after a
  // newer request started is stale and its result is dropped.
  const generation = useRef(0);

  useEffect(() => {
    const mine = ++generation.current;
    setLoading(true);
    setError(null);

    fetcherRef.current().then(
      (value) => {
        if (generation.current !== mine) return;
        setData(value);
        setLoading(false);
      },
      (err) => {
        if (generation.current !== mine) return;
        // An abort means the caller moved on, not that the request failed.
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err);
        setLoading(false);
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { data, error, loading, reload };
}

/** Debounce free variant of an input value, for search-as-you-type. */
export function useDebounced<T>(value: T, delay = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
