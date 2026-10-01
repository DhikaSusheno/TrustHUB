"use client";

// hooks/useBackendStatus.ts
// One health poll for the whole app, shared by every subscriber.
//
// One poller, many subscribers. The banner and the sidebar used to poll
// /health separately and could display "Backend connected" and "OFFLINE" at the
// same time; now both read the same state from this module.
//
// What it probes, and why it changed:
//
//   It used to probe /health and gate on NEXT_PUBLIC_USE_LIVE_SSE, reporting
//   "demo data" whenever that variable was unset. That was correct for the old
//   app, whose data arrived over SSE. None of the Manufacturing Knowledge Hub
//   pages use SSE - every one of them reads the plant index over the
//   same-origin proxy - so a page showing real ingested documents and work
//   orders was labelled "DEMO DATA" because an unrelated env var was missing.
//
//   It now reads /api/plant/status, which is the endpoint that answers the
//   question the viewer actually has: is the backend up, and is the plant index
//   built. Those are different answers, so they are different modes.

import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "/backend";

/**
 * `live`     backend up, plant index built - the pages show real indexed data.
 * `empty`    backend up, plant index not built - pages will show the fetch
 *            command. Distinct from `offline`, because the backend working is
 *            good news and a visitor should not be told it is broken.
 * `checking` first probe in flight.
 * `offline`  backend unreachable.
 */
export type BackendMode = "live" | "empty" | "checking" | "offline";

export interface BackendStatus {
  mode: BackendMode;
  isLive: boolean;
  error?: string;
  /** Recovery command from the backend, present when mode is `empty`. */
  problem?: string;
}

const listeners = new Set<(s: BackendStatus) => void>();
let current: BackendStatus = { mode: "checking", isLive: false };
let poller: ReturnType<typeof setInterval> | null = null;

function emit() {
  // ponytail: forEach, not for..of - tsconfig targets below ES2015 and iterating
  // a Set needs downlevelIteration.
  listeners.forEach((l) => l(current));
}

async function checkBackend() {
  current = { ...current, mode: "checking" };
  emit();
  try {
    const res = await fetch(`${BACKEND_URL}/api/plant/status`, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      const body = (await res.json()) as { ready?: boolean; problem?: string | null };
      current = body.ready
        ? { mode: "live", isLive: true }
        : {
            mode: "empty",
            isLive: false,
            problem: body.problem ?? "The plant index has not been built yet.",
          };
    } else if (res.status === 503) {
      // The backend is running and telling us the index is missing. That is
      // `empty`, not `offline`, and the body carries the fix.
      let problem: string | undefined;
      try {
        const body = (await res.json()) as { detail?: string };
        problem = body.detail;
      } catch {
        // Non-JSON body. The mode alone is still useful.
      }
      current = { mode: "empty", isLive: false, problem };
    } else {
      current = {
        mode: "offline",
        isLive: false,
        error: `Backend responded ${res.status}`,
      };
    }
  } catch (e) {
    current = {
      mode: "offline",
      isLive: false,
      error: e instanceof Error ? e.message : "Unknown error",
    };
  }
  emit();
}

export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>(current);

  useEffect(() => {
    listeners.add(setStatus);
    setStatus(current);
    if (poller === null) {
      checkBackend();
      // 30s. The index cannot change without a rebuild, and the rebuild is
      // initiated from this UI, so a faster poll would only add load.
      poller = setInterval(checkBackend, 30_000);
    }
    return () => {
      listeners.delete(setStatus);
      // ponytail: one module timer for all consumers. When the last consumer
      // unmounts the timer stops; polling resumes on the next mount.
      if (listeners.size === 0 && poller !== null) {
        clearInterval(poller);
        poller = null;
      }
    };
  }, []);

  return status;
}