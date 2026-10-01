// app/backend/[...path]/route.ts
// Proxy server-side ke backend FastAPI.
//
// BUG-11: backend mewajibkan token API di setiap route, sementara halaman
// browser tidak boleh menyimpan token itu di bundle. Route handler ini
// meneruskan request ke backend sambil menyuntikkan header token dari
// environment server, sehingga token tidak pernah sampai ke browser.
//
// Karena lewat server yang sama, request juga menjadi same-origin sehingga
// CORS tidak relevan untuk jalur ini.
//
// #63: menyuntikkan token tanpa syarat itu mengubah proxy ini menjadi
// "pintu masuk gratis" ke API terproteksi. Siapa pun yang bisa menjangkau
// port Next.js bisa memanggil /backend/* dengan kredensial server, termasuk
//_graph/export, /api/github/*, dan /api/llm/providers* yang menyimpan
// token pihak ketiga dalam BODY respons.
//
// Yang diperbaiki di sini:
//   1. Request cross-site dari browser ditolak lewat Sec-Fetch-Site. Tanpa
//      ini, halaman web mana pun bisa membuat browser korban menjalankan
//      POST ke /backend/* (CORS hanya memblokir pembacaan respons, bukan
//      eksekusinya - jadi ini tetap CSRF yang nyata).
//   2. Header Authorization milik klien TIDAK diteruskan, supaya pemanggil
//      tidak bisa menyamarkan diri sebagai backend.
//   3. Kalau TRUSTHUB_API_TOKEN kosong, proxy menolak dengan 503 alih-alih
//      meneruskan request tanpa token.
//   4. Tiap segmen path di-encode, supaya ".." atau "/" yang tersembunyi
//      tidak bisa mengubah tujuan request di backend.
//
// CATATAN AKHIR: ini menutup vektor browser. Klien non-browser (curl, skrip
// lokal, proses lain di jaringan) yang bisa menjangkau port ini tetap bisa
// memakai proxy, karena token diinjeksi server. Itu sifat intrinsik proxy
// penyuntik-token dan tidak bisa diperbaiki di file ini. Mitigasinya di
// level deploy:ikat Next.js ke localhost, atau set
// TRUSTHUB_PROXY_ALLOWED_ORIGINS untuk daftar origin yang memang diizinkan.

import { NextRequest } from "next/server";
import {
  crossSiteDenial,
  missingTokenDenial,
  parseAllowedOrigins,
} from "@/lib/proxyGuard";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const TOKEN = process.env.TRUSTHUB_API_TOKEN ?? "";

// Opsional. Kalau diisi (dipisah koma), Origin/STOLEN wajib salah satu dari
// daftar ini. Kalau kosong, tidak ada pembatasan Origin - andalkan
// Sec-Fetch-Site saja.
const ALLOWED_ORIGINS = parseAllowedOrigins(
  process.env.TRUSTHUB_PROXY_ALLOWED_ORIGINS
);

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "host",
  "origin",
  "referer",
  "cookie",
  "content-length",
]);

// Header milik klien yang TIDAK boleh diteruskan ke backend. Authorization
// ditolak eksplisit: kalau diteruskan, backend menerima dua header token
// dengan nilai berbeda dan hasilnya bergantung pada urutan penulisan.
const CLIENT_HEADERS_DENIED = new Set(["authorization", "x-trusthub-token"]);

// Header yang DITOLAK oleh fetch() (undici) sehingga meneruskannya membuat
// fetch melempar exception, bukan sekadar header yang diabaikan. Efeknya
// request apa pun yang punya salah satu header ini jadi 503 "Backend tidak
// dapat dijangkau" - pesan yang sama persis dengan backend mati, padahal
// backend-nya sehat.
//
// Yang paling sering kena di dunia nyata: `expect: 100-continue`, dikirim
// curl dan beberapa pustaka HTTP untuk body besar. Browser tidak pernah
// mengirimnya, jadi bug ini tidak terlihat dari UI dan baru muncul lewat
// CLI atau integrasi server-ke-server.
//
// Daftar ini mengikuti forbidden header names di spesifikasi fetch.
const FETCH_FORBIDDEN = new Set([
  "accept-charset",
  "accept-encoding",
  "access-control-request-headers",
  "access-control-request-method",
  "connection",
  "content-length",
  "cookie",
  "cookie2",
  "date",
  "dnt",
  "expect",
  "host",
  "keep-alive",
  "origin",
  "referer",
  "set-cookie",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "via",
]);

type RouteContext = { params: Promise<{ path?: string[] }> };

function jsonError(status: number, error: string, hint?: string): Response {
  return new Response(JSON.stringify({ error, ...(hint ? { hint } : {}) }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  // #63: gagal-cepat kalau server tidak punya token. Tanpa guard ini proxy
  // meneruskan request apa adanya ke backend dan hopeful tidak di-401.
  const tokenDenied = missingTokenDenial(TOKEN);
  if (tokenDenied) {
    return jsonError(tokenDenied.status, tokenDenied.error, tokenDenied.hint);
  }

  // Guard CSRF/gagal-alih-alih di lib/proxyGuard.ts — dipakai bersama oleh
  // proxy ini dan app/api/graph/route.ts.
  const denied = crossSiteDenial(
    request.headers.get("sec-fetch-site"),
    request.headers.get("origin"),
    ALLOWED_ORIGINS
  );
  if (denied) {
    return jsonError(denied.status, denied.error, denied.hint);
  }

  // Next 15 membuat params berupa Promise. Menunggu di sini wajib; kalau
  // diakses sinkron, segments selalu kosong dan semua request jatuh ke root.
  const rawSegments = (await context.params)?.path ?? [];
  // Encode tiap segmen: Next.js sudah men-decode-nya, jadi encode ulang
  // mencegah segmen berisi ".." atau "/" menembus sebagai struktur path.
  const segments = rawSegments.map((s) => encodeURIComponent(s));
  const target = `${BACKEND}/${segments.join("/")}${request.nextUrl.search}`;

  const headers: Record<string, string> = {
    "X-TrustHub-Token": TOKEN,
  };

  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower) || CLIENT_HEADERS_DENIED.has(lower)) return;
    if (FETCH_FORBIDDEN.has(lower)) return;
    headers[key] = value;
  });
  // Token ditulis ulang SETELAH loop di bawah, supaya selalu menang atas
  // header klien apa pun yang lolos filter. (Versi lama menyuntik token di
  // dua titik, dan urutan penulisan tidak dijamin.)
  headers["X-TrustHub-Token"] = TOKEN;

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (err) {
    // Log di server, JANGAN di respons. Respons 503 sengaja tidak
    // menyebut BACKEND_URL (L5 FIX: host/port internal tidak perlu bocor),
    // tapi tanpa log ini satu-satunya jejak penyebabnya hilang - catch yang
    // kosong membuat "fetch gagal" jadi tak bisa dibedakan dari "backend
    // mati" hanya dari sisi server.
    const reason = err instanceof Error ? err.message : String(err);
    const cause = err instanceof Error && err.cause ? String(err.cause) : "";
    console.error(
      `[proxy] ${method} ${segments.join("/")} gagal: ${reason}` +
        `${cause ? ` (cause: ${cause})` : ""}`
    );
    return jsonError(
      503,
      "Backend tidak dapat dijangkau",
      "Pastikan proses uvicorn berjalan dan variabel BACKEND_URL di server benar"
    );
  }

  if (upstream.status === 401) {
    return jsonError(
      502,
      "Token API backend ditolak",
      "Cocokkan TRUSTHUB_API_TOKEN di .env.local dengan TRUSTHUB_API_TOKEN milik backend"
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) responseHeaders.set(key, value);
  });
  responseHeaders.set("Cache-Control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
