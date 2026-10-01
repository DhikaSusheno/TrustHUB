// lib/proxyGuard.test.ts
// node --test "lib/*.test.ts"
//
// Unit tests for the shared guard used by the token-injecting proxy at
// app/backend/[...path]/route.ts, plus a scan that demands every proxy route in
// the tree uses it.
//
// The scan is the important part. This guard exists because two proxies in this
// repo had two different security levels, and the weaker one was reachable. The
// unit tests below would still pass if someone added a third proxy that skipped
// the guard entirely, so the last test scans for exactly that.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

import {
  SAFE_FETCH_SITES,
  crossSiteDenial,
  missingTokenDenial,
  parseAllowedOrigins,
} from "./proxyGuard.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const rel = (f: string) => relative(ROOT, f).split(/[\\/]/).join("/");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (["node_modules", ".next", ".git", "dist"].includes(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.name === "route.ts" || entry.name === "route.tsx") out.push(full);
  }
  return out;
}

// ---------------------------------------------------------------- Sec-Fetch

test("Sec-Fetch-Site cross-site ditolak 403", () => {
  const denied = crossSiteDenial("cross-site", "http://evil.example");
  assert.ok(denied, "cross-site harus ditolak");
  assert.equal(denied.status, 403);
});

test("pengecekan Sec-Fetch-Site tidak case-sensitive", () => {
  assert.ok(crossSiteDenial("Cross-Site", null));
  assert.ok(crossSiteDenial("CROSS-SITE", null));
});

test("same-origin, same-site, dan none diperbolehkan", () => {
  for (const site of ["same-origin", "same-site", "none"]) {
    assert.equal(crossSiteDenial(site, null), null, `${site} harus lolos`);
  }
});

test("tanpa header Sec-Fetch-Site diperbolehkan (klien non-browser)", () => {
  // With no header there is no evidence the request came from a foreign browser,
  // and blocking that would break curl and server-side clients.
  assert.equal(crossSiteDenial(null, null), null);
});

test("SAFE_FETCH_SITES tidak memuat nilai berbahaya", () => {
  assert.ok(!SAFE_FETCH_SITES.has("cross-site"));
  assert.ok(!SAFE_FETCH_SITES.has("cross-origin"));
  assert.equal(SAFE_FETCH_SITES.size, 3);
});

// ---------------------------------------------------------------- origin

test("origin di luar allowlist ditolak hanya kalau allowlist terisi", () => {
  const allowed = new Set(["http://localhost:3000"]);
  const denied = crossSiteDenial(null, "http://evil.example", allowed);
  assert.ok(denied);
  assert.equal(denied.status, 403);
  assert.match(denied.hint ?? "", /evil\.example/);
});

test("origin di dalam allowlist diperbolehkan", () => {
  const allowed = new Set(["http://localhost:3000"]);
  assert.equal(crossSiteDenial(null, "http://localhost:3000", allowed), null);
});

test("allowlist kosong berarti tanpa pembatasan origin", () => {
  assert.equal(crossSiteDenial(null, "http://evil.example", new Set()), null);
});

test("tanpa header Origin tidak ditolak (GET tidak mengirim Origin)", () => {
  const allowed = new Set(["http://localhost:3000"]);
  assert.equal(crossSiteDenial(null, null, allowed), null);
});

// ---------------------------------------------------------------- token

test("token kosong ditolak 503 sebelum request diteruskan", () => {
  const denied = missingTokenDenial("");
  assert.ok(denied);
  assert.equal(denied.status, 503);
  assert.match(denied.error, /TRUSTHUB_API_TOKEN/);
});

test("token ada berarti lolos", () => {
  assert.equal(missingTokenDenial("token-yang-valid-panjang"), null);
});

// ---------------------------------------------------------------- parsing

test("parseAllowedOrigins membuang spasi dan entri kosong", () => {
  const parsed = parseAllowedOrigins(
    " http://localhost:3000 , http://localhost:3001 ,, "
  );
  // Array.from/Set spread is deliberately unused: tsconfig targets es5, so
  // iterating a Set needs downlevelIteration.
  assert.equal(parsed.size, 2, `dapat ${parsed.size} entri`);
  assert.ok(parsed.has("http://localhost:3000"));
  assert.ok(parsed.has("http://localhost:3001"));
});

test("parseAllowedOrigins(undefined) menghasilkan set kosong", () => {
  assert.equal(parseAllowedOrigins(undefined).size, 0);
  assert.equal(parseAllowedOrigins("").size, 0);
});

// --------------------------------------------- every proxy route must be guarded

test("setiap route handler proxy memakai proxyGuard", () => {
  const routes = walk(join(ROOT, "app"));
  assert.ok(routes.length >= 1, `minimal satu route, dapat ${routes.length}`);

  const offenders: string[] = [];
  for (const file of routes) {
    const src = readFileSync(file, "utf8");
    const mentionsBackend = /BACKEND_URL|TRUSTHUB_API_TOKEN/.test(src);
    if (!mentionsBackend) continue; // an ordinary route, not a proxy
    const guarded =
      src.includes("@/lib/proxyGuard") ||
      (src.includes("crossSiteDenial") && src.includes("missingTokenDenial"));
    if (!guarded) offenders.push(rel(file));
  }

  assert.deepEqual(
    offenders,
    [],
    `route berikut menyuntik token tanpa guard: ${offenders.join(", ")}`,
  );
});

test("proxy utama menyuntik token dan memakai guard", () => {
  const file = join(ROOT, "app", "backend", "[...path]", "route.ts");
  const src = readFileSync(file, "utf8");
  assert.match(src, /proxyGuard/, "guard harus diimpor");
  assert.match(
    src,
    /X-TrustHub-Token/,
    "route ini memang menyuntik token - karena itu guard wajib",
  );
});