// lib/proxyGuard.ts
// Guard bersama untuk SEMUA route proxy di frontend.
//
// Repo ini punya DUA proxy yang menyuntikkan TRUSTHUB_API_TOKEN dari sisi
// server:
//   - app/backend/[...path]/route.ts  (proxy utama, kebanyakan endpoint)
//   - app/api/graph/route.ts          (proxy kedua, ke /graph/nodes + /graph/edges)
//
// Guard-nya dulu hanya ada di proxy utama (isu #63) dan proxy /api/graph
// jalan tanpa satupun: tanpa cek Sec-Fetch-Site, dan tanpa penolakan kalau
// token belum disetel sehingga request tetap diteruskan lalu gagal 401
// membingungkan di ujung. Dua file yang sama-sama menyuntik token tidak
// boleh memakai dua tingkat keamanan berbeda — karena itu logikanya dipindah
// ke sini supaya keduanya memakai SATU implementasi dan testnya juga cuma
// satu.

/** Nilai Sec-Fetch-Site yang menandakan request datang dari aplikasi ini sendiri. */
export const SAFE_FETCH_SITES: ReadonlySet<string> = new Set([
  "same-origin",
  "same-site",
  "none",
]);

export type ProxyDenial = {
  status: number;
  error: string;
  hint?: string;
};

/**
 * Tolak request yang jelas berasal dari origin lain atau dari browser
 * foreign. Mengembalikan objek penolakan, atau `null` kalau diperbolehkan.
 *
 * CORS hanya memblokir PEMBACAAN respons, bukan eksekusinya — jadi tanpa
 * guard ini halaman mana pun bisa membuat browser korban memicu POST ke
 * proxy (CSRF nyata, karena proxy-lah yang menyuntikkan kredensial server).
 *
 * @param fetchSite nilai header `sec-fetch-site` (null kalau tidak dikirim)
 * @param origin    nilai header `origin` (null kalau tidak dikirim)
 * @param allowedOrigins daftar origin yang diizinkan; kosong = tidak ada
 *        pembatasan origin selain Sec-Fetch-Site
 */
export function crossSiteDenial(
  fetchSite: string | null,
  origin: string | null,
  allowedOrigins: ReadonlySet<string> = new Set<string>()
): ProxyDenial | null {
  if (fetchSite && !SAFE_FETCH_SITES.has(fetchSite.toLowerCase())) {
    return {
      status: 403,
      error: "Cross-site request ditolak",
      hint: "Proxy hanya melayani request dari aplikasi TrustHub itu sendiri",
    };
  }

  if (allowedOrigins.size > 0) {
    // Origin hanya dikirim browser pada request non-GET. Untuk GET, andalkan
    // Sec-Fetch-Site yang sudah dicek di atas.
    if (origin && !allowedOrigins.has(origin)) {
      return { status: 403, error: "Origin tidak diizinkan", hint: `Origin: ${origin}` };
    }
  }

  return null;
}

/**
 * Tolak kalau server tidak punya token sama sekali.
 *
 * Tanpa guard ini proxy meneruskan request apa adanya ke backend tanpa
 * kredensial: yang terjadi hanya 401 membingungkan di ujung, atau — lebih
 * buruk — kalau kebijakan auth backend berubah, endpoint jadi terbuka.
 * Proxy yang menyuntik token harus gagal-cepat sebelum menyentuh jaringan.
 */
export function missingTokenDenial(token: string): ProxyDenial | null {
  if (token) return null;
  return {
    status: 503,
    error: "TRUSTHUB_API_TOKEN belum di-set di server",
    hint: "Proxy tidak akan meneruskan request tanpa kredensial",
  };
}

/**
 * Parsing daftar origin dari env (comma-separated) jadi Set.
 * Nilai kosong menghasilkan Set kosong, yang berarti "tanpa pembatasan
 * origin" — perilaku ini disengaja dan sama dengan versi lama.
 */
export function parseAllowedOrigins(raw: string | undefined): Set<string> {
  return new Set(
    (raw ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  );
}

// --------------------------------------------------------------- allowlist
//
// Yang diIzinkan lewat proxy adalah endpoint yang benar-benar dipanggil
// frontend. Semua route lain di backend/main.py TIDAK boleh terjangkau lewat
// proxy, karena proxy menyuntikkan TRUSTHUB_API_TOKEN milik server ke setiap
// request yang diteruskan.
//
// Tanpa allowlist, `/backend/*` jadi pintu masuk ke endpoint yang tidak pernah
// dimaksud untuk diekspos lewat web:
//
//   - /api/github/*      menyimpan token GitHub milik operator dan
//                        menampilkannya di BODY respons
//   - /api/llm/providers* menyimpan API key provider LLM di BODY respons
//                        (termasuk saat menambah provider)
//   - /api/targets (POST/PATCH/DELETE), /operations, /approve_operation,
//     /execute_operation, /propose_operation
//                        menulis ke disk dan menjalankan operasi atas nama
//                        server; tidak ada layar TrustHUB yang memanggilnya
//
// Alasan allowlist, bukan bloklist: bloklist harus memperbarui dirinya setiap
// kali route baru ditambahkan ke backend, dan route baru itu akan lolos sampai
// ada yang ingat. Allowlist gagal aman secara default.

type BackendRouteRule = {
  /** Regex terhadap path yang dimulai `/`, dianchor di kedua ujung. */
  path: RegExp;
  /** Method HTTP yang boleh. `HEAD` dianggap sama dengan `GET`. */
  methods: readonly string[];
};

/**
 * Bahasa Indonesia Path Param (plant/api.py) memakai nama variabel route
 * sebagai penanda posisi, jadi `trust/weights` adalah dua segmen. Pola di
 * bawah ditulis terhadap hasil DECODE dari Next.js, sebelum di-encode ulang.
 */
const PLANT_PARAM = "[^/]+";

export const BACKEND_ROUTE_ALLOWLIST: readonly BackendRouteRule[] = [
  // ---------------------------------------------------------------- sistem
  { path: /^\/health$/, methods: ["GET", "HEAD"] },
  { path: /^\/settings$/, methods: ["GET", "HEAD", "POST"] },
  { path: /^\/settings\/reset$/, methods: ["POST"] },
  { path: /^\/browse$/, methods: ["GET", "HEAD"] },
  { path: /^\/api\/targets\/browse$/, methods: ["GET", "HEAD"] },

  // ------------------------------------------- CALIBER plant router (read)
  {
    path: new RegExp(
      "^/api/plant/(status|dataset|equipment|documents|work-orders" +
        "|failure-memory|graph|verification|evaluation|conflicts|audit" +
        "|search|trust/weights)$"
    ),
    methods: ["GET", "HEAD"],
  },
  { path: new RegExp(`^/api/plant/equipment/${PLANT_PARAM}$`), methods: ["GET", "HEAD"] },
  {
    path: new RegExp(
      `^/api/plant/equipment/${PLANT_PARAM}/(documents|work-orders|failure-memory)$`
    ),
    methods: ["GET", "HEAD"],
  },
  { path: new RegExp(`^/api/plant/documents/${PLANT_PARAM}$`), methods: ["GET", "HEAD"] },

  // ------------------------------------------ CALIBER plant router (write)
  { path: /^\/api\/plant\/ask$/, methods: ["POST"] },
  { path: /^\/api\/plant\/reindex$/, methods: ["POST"] },
];

/**
 * Tolak request ke endpoint yang tidak ada di allowlist, atau ke endpoint yang
 * ada tapi dengan method yang salah.
 *
 * Method ikut diperiksa karena `GET /settings` dan `POST /settings` memang dua
 * operasi berbeda: yang pertama membaca, yang kedua menulis konfigurasi.
 * Mengizinkan keduanya untuk semua rule akan mengembalikan kemampuan tulis ke
 *-route baca lewat method lain.
 */
export function routeDenial(
  segments: readonly string[],
  method: string
): ProxyDenial | null {
  // Path traversal dicek pada segmen yang SUDAH di-decode oleh Next.js, bukan
  // sesudahnya. encodeURIComponent("..") tetap "..", jadi encode ulang tidak
  // mencegah "../" yang membuat path menunjuk endpoint lain dari yang
  // diallowlist. Menolak ".", "..", segmen kosong, dan segmen yang memuat
  // separator menutupnya di titik yang benar.
  for (const segment of segments) {
    if (segment === "" || segment === "." || segment === "..") {
      return {
        status: 400,
        error: "Path tidak valid",
        hint: "Segmen path harus nama resource, bukan navigasi direktori",
      };
    }
    if (segment.includes("/") || segment.includes("\\")) {
      return {
        status: 400,
        error: "Path tidak valid",
        hint: "Segmen path tidak boleh memuat pemisah path",
      };
    }
  }

  const path = `/${segments.join("/")}`;
  const allowedPath = BACKEND_ROUTE_ALLOWLIST.some((rule) => rule.path.test(path));
  if (!allowedPath) {
    return {
      status: 404,
      error: "Endpoint backend tidak tersedia lewat proxy",
      hint: "Proxy hanya melayani endpoint yang dipakai antarmuka TrustHUB",
    };
  }

  const normalizedMethod = method.toUpperCase();
  const rule = BACKEND_ROUTE_ALLOWLIST.find((entry) => entry.path.test(path));
  const allowedMethod =
    rule !== undefined &&
    rule.methods.some((entry) => entry.toUpperCase() === normalizedMethod);
  if (!allowedMethod) {
    return {
      status: 405,
      error: "Method tidak diizinkan untuk endpoint ini",
      hint: `${normalizedMethod} ${path}`,
    };
  }

  return null;
}
