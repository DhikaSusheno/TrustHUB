// lib/backendUrl.test.ts
// node --test "lib/*.test.ts"
//
// Regression guard for the proxy-token contract (BUG-11). The backend requires
// an API token on every non-public path, and a browser bundle must never hold
// that token. So every browser call has to go through the Next route handler at
// app/backend/[...path]/route.ts, which injects TRUSTHUB_API_TOKEN from the
// server environment.
//
// The failure this prevents is the expensive kind. A module that falls back to
// an absolute backend URL bypasses the proxy, gets a 401, and shows an empty
// page - while /health stays public, so the status banner still reads green and
// the viewer concludes the data is empty rather than unauthorised.
//
// The scan covers whole directories rather than a hard-coded file list. A list
// misses files added later by anyone else working in the tree, which is exactly
// how the original bug got reintroduced.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCAN_DIRS = ["app", "components", "hooks", "lib"];
const SKIP = new Set(["node_modules", ".next", ".git", "dist"]);

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

// Paths always use "/" so assertions do not depend on the OS separator.
const rel = (f: string) => relative(ROOT, f).split(/[\\/]/).join("/");

const SOURCES = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d))).filter(
  // Do not scan this file: it contains the pattern as its own examples.
  (f) => rel(f) !== "lib/backendUrl.test.ts",
);

// The legitimate default: a relative path, so the request goes via the proxy.
const PUBLIC_DEFAULT = /process\.env\.NEXT_PUBLIC_BACKEND_URL\s*\?\?\s*"\/backend"/;
// An absolute host means the request hits the backend with no token header.
const ABSOLUTE_DEFAULT =
  /process\.env\.NEXT_PUBLIC_BACKEND_URL\s*\?\?\s*"(https?:\/\/[^"]+)"/;
// Only a VARIABLE read counts, not the string appearing in UI copy.
// BackendStatusBanner mentions NEXT_PUBLIC_BACKEND_URL in its error message and
// that is not a read of the environment.
const READS_ENV = /process\.env\.NEXT_PUBLIC_BACKEND_URL/;

// exec rather than matchAll: matchAll returns an iterator, which would need
// --downlevelIteration, and there is no reason to change the global tsconfig
// for one test.
function allMatches(src: string, re: RegExp): string[] {
  const out: string[] = [];
  const rx = new RegExp(re.source, re.flags.includes("g") ? re.flags : `${re.flags}g`);
  let m: RegExpExecArray | null;
  while ((m = rx.exec(src)) !== null) {
    out.push(m[1]);
    if (m.index === rx.lastIndex) rx.lastIndex++;
  }
  return out;
}

test("tree scan benar-benar menemukan file sumber", () => {
  assert.ok(
    SOURCES.length > 15,
    `hanya ${SOURCES.length} file ketemu - pola walk-nya salah`,
  );
  assert.ok(
    SOURCES.some((f) => rel(f) === "app/page.tsx"),
    "app/page.tsx tidak ikut ter-scan",
  );
  assert.ok(
    SOURCES.some((f) => rel(f) === "lib/plantApi.ts"),
    "client API plant tidak ikut ter-scan",
  );
  assert.ok(
    SOURCES.some((f) => rel(f) === "app/backend/[...path]/route.ts"),
    "proxy tidak ikut ter-scan",
  );
});

test("tidak ada modul browser yang fallback ke URL backend absolut", () => {
  const offenders: string[] = [];
  for (const file of SOURCES) {
    const src = readFileSync(file, "utf8");
    for (const host of allMatches(src, ABSOLUTE_DEFAULT)) {
      offenders.push(`${rel(file)} -> ${host}`);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `Modul ini fallback ke URL absolut, jadi melewati proxy dan akan 401:\n` +
      `${offenders.join("\n")}\n\nGanti dengan "/backend". ` +
      `Lihat frontend/.env.local.example.`,
  );
});

test("modul yang membaca env itu defaultnya ke proxy", () => {
  const bad: string[] = [];
  for (const file of SOURCES) {
    const src = readFileSync(file, "utf8");
    if (!READS_ENV.test(src)) continue;
    if (!PUBLIC_DEFAULT.test(src)) bad.push(rel(file));
  }
  assert.deepEqual(bad, [], `Default bukan "/backend":\n${bad.join("\n")}`);
});

test("proxy tidak boleh pakai NEXT_PUBLIC_, hanya server-side env", () => {
  const proxy = readFileSync(
    join(ROOT, "app/backend/[...path]/route.ts"),
    "utf8",
  );
  // NEXT_PUBLIC_ is inlined into the browser bundle, so the token or the
  // backend URL would ship to the client. The proxy reads server-side env only.
  assert.ok(
    !/NEXT_PUBLIC_/.test(proxy),
    "proxy memuat NEXT_PUBLIC_* - nilainya akan masuk bundle browser",
  );
  assert.match(
    proxy,
    /process\.env\.BACKEND_URL\s*\?\?\s*"https?:\/\//,
    "proxy harus default ke URL absolut server-side; hanya browser yang wajib /backend",
  );
});

/**
 * Strip comments, keeping string contents.
 *
 * Comments are stripped but not strings, because the distinction that matters
 * here is "does this code read the token" versus "does this file mention the
 * token in prose". Several modules name TRUSTHUB_API_TOKEN in a comment
 * explaining why they must NOT use it, and flagging those would push someone
 * towards deleting an accurate warning. Block comments are handled without a
 * full parser on purpose: a token literal inside one is not a code path.
 */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

// A read, as opposed to a mention. `process.env.X` and `process.env["X"]` are
// reads; the same word inside an error message or a comment is not. Matching
// the bare name would flag lib/proxyGuard.ts, which legitimately names the
// variable in the text of a 503 telling the operator to set it.
const READS_TOKEN = /process\.env(?:\.\s*|\[\s*['"])[^'"\]\n]*TRUSTHUB_API_TOKEN/;

test("token API tidak pernah dibaca di kode browser", () => {
  // The strongest form of the same guarantee: no file that ships to the browser
  // may READ the token, whatever the variable is called. A new module reading a
  // differently-named secret is caught here even though the regexes above would
  // not see it.
  const offenders: string[] = [];
  for (const file of SOURCES) {
    const relPath = rel(file);
    // The proxy is server-side by definition, and is where the token is read.
    if (relPath === "app/backend/[...path]/route.ts") continue;
    const code = stripComments(readFileSync(file, "utf8"));
    if (READS_TOKEN.test(code)) offenders.push(relPath);
  }
  assert.deepEqual(
    offenders,
    [],
    `Kode browser ini membaca TRUSTHUB_API_TOKEN:\n${offenders.join("\n")}\n` +
      `Panggil lewat BASE + path agar request melewati proxy.`,
  );
});