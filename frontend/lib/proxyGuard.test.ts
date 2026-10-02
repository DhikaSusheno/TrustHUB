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
  BACKEND_ROUTE_ALLOWLIST,
  SAFE_FETCH_SITES,
  crossSiteDenial,
  missingTokenDenial,
  parseAllowedOrigins,
  routeDenial,
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
  assert.match(
    src,
    /routeDenial/,
    "proxy yang menyuntik token wajib punya allowlist endpoint",
  );
});

// ---------------------------------------------------------------- allowlist

test("seluruh endpoint yang dipanggil frontend lolos allowlist", () => {
  // Path dan method diambil dari pemakaian nyata di lib/plantApi.ts,
  // lib/platformSettings.ts, dan hooks/useBackendStatus.ts. Kalau salah satu
  // hilang di sini, halamannya rusak saat runtime, bukan saat review.
  const used: Array<[string[], string]> = [
    [["health"], "GET"],
    [["settings"], "GET"],
    [["settings"], "POST"],
    [["settings", "reset"], "POST"],
    [["browse"], "GET"],
    [["api", "targets", "browse"], "GET"],
    [["api", "plant", "status"], "GET"],
    [["api", "plant", "dataset"], "GET"],
    [["api", "plant", "reindex"], "POST"],
    [["api", "plant", "equipment"], "GET"],
    [["api", "plant", "equipment", "ZSO-001"], "GET"],
    [["api", "plant", "equipment", "ZSO-001", "documents"], "GET"],
    [["api", "plant", "equipment", "ZSO-001", "work-orders"], "GET"],
    [["api", "plant", "equipment", "ZSO-001", "failure-memory"], "GET"],
    [["api", "plant", "documents"], "GET"],
    [["api", "plant", "documents", "doc-001"], "GET"],
    [["api", "plant", "work-orders"], "GET"],
    [["api", "plant", "failure-memory"], "GET"],
    [["api", "plant", "graph"], "GET"],
    [["api", "plant", "verification"], "GET"],
    [["api", "plant", "evaluation"], "GET"],
    [["api", "plant", "conflicts"], "GET"],
    [["api", "plant", "trust", "weights"], "GET"],
    [["api", "plant", "audit"], "GET"],
    [["api", "plant", "search"], "GET"],
    [["api", "plant", "ask"], "POST"],
  ];

  const blocked: string[] = [];
  for (const [segments, method] of used) {
    const denied = routeDenial(segments, method);
    if (denied) blocked.push(`${method} /${segments.join("/")} -> ${denied.error}`);
  }
  assert.deepEqual(blocked, [], `dipakai frontend tapi diblokir: ${blocked.join("; ")}`);
});

test("path traversal ditolak 400, termasuk lewat nama berformat basis", () => {
  for (const segments of [
    [".."],
    ["api", "plant", ".."],
    ["api", "plant", "status", ".."],
    ["."],
    ["api", "plant", "equipment", "..", "documents"],
  ]) {
    const denied = routeDenial(segments, "GET");
    assert.ok(denied, `${segments.join("/")} harus ditolak`);
    assert.equal(denied.status, 400);
  }
});

test("encodeURIComponent tidak menutup traversal, jadi guard harus menutupnya", () => {
  // Titik yang membuat test ini ada: encode("../x") menghasilkan "..%2Fx",
  // yang terlihat aman, padahal check dilakukan pada segmen sebelum di-decode
  // ulang. Kalau suatu saat urutan encode-dan-cek ditukar, test ini gagal
  // lebih dulu daripada di produksi.
  assert.equal(encodeURIComponent(".."), "..");
  assert.ok(routeDenial(["..", "x"], "GET"));
});

test("segmen kosong dan pemisah path ditolak", () => {
  for (const segments of [["api", "", "plant"], ["api/plant"], ["api\\plant"], ["a/b"]]) {
    const denied = routeDenial(segments, "GET");
    assert.ok(denied, `${JSON.stringify(segments)} harus ditolak`);
    assert.equal(denied.status, 400);
  }
});

test("endpoint yang menyimpan kredensial pihak ketiga tidak terjangkau", () => {
  // Ini reason allowlist-nya ada. Kalau salah satu lolos, proxy menjadi cara
  // mengambil token GitHub dan API key provider LLM milik operator.
  const forbidden: Array<[string[], string]> = [
    [["api", "github", "auth", "url"], "GET"],
    [["api", "github", "repos"], "GET"],
    [["api", "github", "repos", "owner", "repo", "contents"], "GET"],
    [["api", "github", "auth", "pat"], "POST"],
    [["api", "github", "connection"], "DELETE"],
    [["api", "llm", "providers"], "GET"],
    [["api", "llm", "providers"], "POST"],
    [["api", "llm", "chat"], "POST"],
    [["api", "targets"], "POST"],
    [["api", "targets", "1"], "DELETE"],
    [["operations"], "GET"],
    [["execute_operation"], "POST"],
    [["approve_operation"], "POST"],
    [["ingest_repository"], "POST"],
  ];

  for (const [segments, method] of forbidden) {
    const denied = routeDenial(segments, method);
    assert.ok(
      denied,
      `${method} /${segments.join("/")} TIDAK BOLEH terjangkau lewat proxy`,
    );
    assert.equal(denied.status, 404);
  }
});

test("method yang salah ditolak 405, bukan diteruskan", () => {
  // GET /settings membaca, POST /settings menulis konfigurasi. Mengizinkan
  // keduanya di semua rule mengembalikan kemampuan tulis ke route baca.
  assert.equal(routeDenial(["api", "plant", "status"], "POST")?.status, 405);
  assert.equal(routeDenial(["api", "plant", "status"], "DELETE")?.status, 405);
  assert.equal(routeDenial(["health"], "POST")?.status, 405);
  assert.equal(routeDenial(["api", "plant", "ask"], "GET")?.status, 405);
  assert.equal(routeDenial(["api", "plant", "reindex"], "GET")?.status, 405);
  assert.equal(routeDenial(["browse"], "POST")?.status, 405);
});

test("HEAD diperlakukan sama dengan GET", () => {
  assert.equal(routeDenial(["api", "plant", "status"], "HEAD"), null);
  assert.equal(routeDenial(["health"], "head"), null);
});

test("pengecekan method case-insensitive", () => {
  assert.equal(routeDenial(["api", "plant", "status"], "get"), null);
  assert.equal(routeDenial(["api", "plant", "ask"], "post"), null);
});

test("resource dengan karakter tak lazim tetap boleh sebagai segmen", () => {
  // Nama dokumen dan equipment tag boleh memuat spasi, "+", "#", dan titik.
  // Guard menolak pemisah path dan navigasi direktori, bukan karakter sah.
  for (const tag of ["ZSO-001", "OPL-GA-1201A-04", "doc v2 final", "a+b", "file#3", "v1.2.3"]) {
    assert.equal(
      routeDenial(["api", "plant", "equipment", tag], "GET"),
      null,
      `${tag} harus boleh`,
    );
  }
});

test("prefix yang benar tapi tidak ada yang bocor ke luar allowlist", () => {
  // /api/plant/equipment/{tag}/documents adalah allowlist; menambahkan segmen
  // lain di belakangnya harus jatuh ke 404, bukan "/prefix ada → lolos".
  assert.equal(routeDenial(["api", "plant", "equipment", "T1", "documents", "extra"], "GET")?.status, 404);
  assert.equal(routeDenial(["api", "plant", "trust"], "GET")?.status, 404);
  assert.equal(routeDenial(["api", "plant"], "GET")?.status, 404);
  assert.equal(routeDenial(["api", "plant", "verification", "extra"], "GET")?.status, 404);
});

test("path root kosong ditolak", () => {
  const denied = routeDenial([], "GET");
  assert.ok(denied);
  assert.equal(denied.status, 404);
});

test("allowlist tidak memuat regex tanpa anchor", () => {
  // Regex tanpa ^ dan $ bisa cocok di tengah string, sehingga
  // "/api/github/x/../api/plant/status" lolos sebagai plant endpoint padahal
  // request aslinya menuju GitHub. Anchor itu yang membuatnya aman.
  for (const rule of BACKEND_ROUTE_ALLOWLIST) {
    assert.ok(rule.path.source.startsWith("^"), `tanpa anchor: ${rule.path.source}`);
    assert.ok(rule.path.source.endsWith("$"), `tanpa anchor: ${rule.path.source}`);
  }
});