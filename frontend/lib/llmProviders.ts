// lib/llmProviders.ts
// Client typed untuk registry LLM provider (backend/main.py, tag "LLM").
//
// Token API tidak pernah ada di browser: route handler app/backend/[...path]
// menyuntikkan TRUSTHUB_API_TOKEN dari sisi server, jadi setiap fetch di sini
// cukup same-origin tanpa header auth apa pun. Jangan tambahin
// localStorage token atau X-TrustHub-Token di file ini - lib/backendUrl.test.ts
// dan-review sekalian kontrak itu.

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "/backend";

// Tipe yang dikenali TrustHub. BUKAN daftar tertutup: backend menerima tipe
// apa pun (lihat normalize_provider_type di main.py), jadi "groq",
// "lmstudio", "vllm", atau "internal-proxy" semuanya sah. Daftar ini hanya
// untuk (a) memberi base_url default di backend dan (b) mengisi dropdown.
//
// Konsekuensi: form harus bisa menerima teks bebas, bukan cuma <select>.
export const KNOWN_PROVIDER_TYPES = [
  "openai",
  "anthropic",
  "ibm",
  "nvidia",
  "deepseek",
  "ollama",
  "google",
  "groq",
  "mistral",
  "xai",
  "openrouter",
  "lmstudio",
  "openai-compatible",
] as const;

/** Nama tipe provider. Bebas, bukan salah satu dari KNOWN_PROVIDER_TYPES. */
export type ProviderType = string;

// Alias lama. Dipakai LLMProviderManager untuk iterasi dropdown; nama baru
// lebih jujur karena daftar ini tidak lagi lengkap.
export const PROVIDER_TYPES = KNOWN_PROVIDER_TYPES;

// Backend menolak DELETE untuk type di bawah dengan 403 (delete_llm_provider,
// "Cannot delete built-in provider"). UI harus menonaktifkan tombol hapus
// berdasarkan daftar yang sama supaya user tidak menunggu error yang sudah
// bisa diprediksi di client. Tipe custom SELALU boleh dihapus.
export const UNDELETABLE_TYPES: ReadonlySet<string> = new Set<string>([
  "openai",
  "anthropic",
  "ibm",
  "nvidia",
  "deepseek",
  "ollama",
  "google",
  "groq",
  "mistral",
  "xai",
  "openrouter",
  "lmstudio",
]);

export function isDeletable(type: ProviderType): boolean {
  return !UNDELETABLE_TYPES.has(type);
}

// Base URL default per tipe yang dikenali. Harus sama dengan
// PROVIDER_BASE_URLS di backend/main.py. Tipe di luar daftar TIDAK punya
// default: backend akan menolak dengan 400 kalau base_url kosong, karena
// menebak URL OpenAI akan mengirim isi repo ke akun yang tidak diminta.
export const PROVIDER_BASE_URLS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com/v1",
  nvidia: "https://integrate.api.nvidia.com/v1",
  deepseek: "https://api.deepseek.com/v1",
  ollama: "http://localhost:11434/v1",
  ibm: "https://us-south.ml.cloud.ibm.com/ml/v1",
  // Semua di bawah punya endpoint OpenAI-compatible, jadi form tidak perlu
  // menebak-nebak path. Kalau suatu vendor berubah jadi API-nya sendiri,
  // hapus dari sini dan pakai tipe custom yang mewajibkan base_url.
  google: "https://generativelanguage.googleapis.com/v1beta/openai",
  groq: "https://api.groq.com/openai/v1",
  mistral: "https://api.mistral.ai/v1",
  xai: "https://api.x.ai/v1",
  openrouter: "https://openrouter.ai/api/v1",
  // Lokal. Port default LM Studio; base_url tetap bisa diedit kalau jalan di
  // port lain. Tipe custom (vllm, llama.cpp) tidak ada di sini karena portnya
  // tidak bisa ditebak - tipe seperti itu mewajibkan base_url diisi manual.
  lmstudio: "http://localhost:1234/v1",
};

/** True kalau tipe punya base_url default, jadi field boleh dikosongkan. */
export function hasDefaultBaseUrl(type: ProviderType): boolean {
  return Object.prototype.hasOwnProperty.call(PROVIDER_BASE_URLS, type);
}

// Label yang tampil di datalist dropdown. Murni kosmetik - tidak ikut
// kontrak dengan backend, jadi boleh berbeda. Tujuannya satu: user tahu
// sebelum memilih apakah tipe ini perlu API key, jalan lokal, atau
// mewajibkan base_url manual.
export const PROVIDER_TYPE_LABELS: Record<string, string> = {
  openai: "OpenAI - butuh API key",
  anthropic: "Anthropic Claude - butuh API key",
  google: "Google Gemini - butuh API key",
  groq: "Groq - butuh API key, gratis limited",
  mistral: "Mistral - butuh API key",
  xai: "xAI Grok - butuh API key",
  openrouter: "OpenRouter - butuh API key, banyak model",
  deepseek: "DeepSeek - butuh API key",
  nvidia: "NVIDIA NIM - butuh API key",
  ibm: "IBM watsonx - butuh API key",
  ollama: "Ollama - lokal, tanpa API key",
  lmstudio: "LM Studio - lokal, tanpa API key",
  "openai-compatible": "OpenAI-compatible - server sendiri, base_url wajib",
};

// Saran model per tipe. Backend tidak menolak nama model di luar daftar ini -
// namespaced model lokal (mis. "llama3.1:8b", "qwen2.5-coder:14b") sah untuk
// Ollama, dan vendor baru sering punya nama sendiri. Daftar ini hanya untuk
// autocomplete, jadi input tetap harus bisa menerima teks bebas.
export const MODEL_SUGGESTIONS: Record<string, readonly string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"],
  anthropic: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-latest"],
  ibm: ["ibm/granite-3-8b-instruct", "meta-llama/llama-3-3-70b-instruct"],
  nvidia: ["meta/llama-3.3-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  ollama: ["llama3.1", "qwen2.5-coder", "deepseek-r1", "gemma3"],
  google: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
  groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"],
  mistral: ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
  xai: ["grok-4", "grok-3", "grok-3-mini"],
  openrouter: ["google/gemini-2.5-flash", "anthropic/claude-sonnet-4", "openai/gpt-4o-mini"],
  lmstudio: ["qwen2.5-coder-7b-instruct", "llama-3.2-3b-instruct"],
  "openai-compatible": ["gpt-4o-mini", "llama3.1", "qwen2.5-coder"],
};

/** Saran model untuk satu tipe. Selalu array, walau tipenya tidak dikenal. */
export function modelSuggestions(type: ProviderType): readonly string[] {
  return MODEL_SUGGESTIONS[type] ?? [];
}

export interface LLMProvider {
  id: string;
  name: string;
  type: ProviderType;
  base_url: string | null;
  models: string[];
  default_model: string;
  max_tokens: number;
  supports_tools: boolean;
  supports_vision: boolean;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProviderDraft {
  name: string;
  type: ProviderType;
  base_url?: string | null;
  api_key?: string | null;
  models: string[];
  default_model?: string;
  max_tokens?: number;
  supports_tools?: boolean;
  supports_vision?: boolean;
  enabled?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    // FastAPI balas {"detail": "..."} atau {"detail": [{loc, msg}]} untuk 422.
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        detail = `${body.detail[0].loc?.join(".") ?? "body"}: ${body.detail[0].msg}`;
      }
    } catch {
      // body bukan JSON, pakai status saja
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// owner dan repo tetap di-encode per-segmen: nama repo GitHub boleh berisi
// karakter yang harus di-escape, dan segment "/" akan memecah path.
const seg = (v: string) => encodeURIComponent(v);

export async function listProviders(): Promise<LLMProvider[]> {
  const data = await api<{ ok: boolean; providers: LLMProvider[] }>("/api/llm/providers");
  return data.providers ?? [];
}

export async function createProvider(draft: ProviderDraft): Promise<string> {
  const data = await api<{ ok: boolean; id: string }>("/api/llm/providers", {
    method: "POST",
    body: JSON.stringify(draft),
  });
  return data.id;
}

export async function updateProvider(
  id: string,
  patch: Partial<ProviderDraft>,
): Promise<void> {
  await api<{ ok: boolean }>(`/api/llm/providers/${seg(id)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteProvider(id: string): Promise<void> {
  await api<{ ok: boolean }>(`/api/llm/providers/${seg(id)}`, { method: "DELETE" });
}

export async function listModels(
  id: string,
): Promise<{ models: string[]; defaultModel: string }> {
  const data = await api<{ ok: boolean; models: string[]; default: string }>(
    `/api/llm/providers/${seg(id)}/models`,
  );
  return { models: data.models ?? [], defaultModel: data.default ?? "" };
}

// --- discovery model dari upstream -----------------------------------------

export interface DiscoverInput {
  /** Provider tersimpan. Kosong = provider belum ada, pakai draft saja. */
  providerId?: string | null;
  type?: string | null;
  baseUrl?: string | null;
  apiKey?: string | null;
}

/**
 * Tanya endpoint provider sendiri, bukan daftar hardcode.
 *
 * Model suggestion di file ini cepat basi: Ollama lokal tidak punya
 * "gpt-4o", OpenRouter punya ratusan model yang tidak akan pernah masuk
 * daftar, dan model yang dihapus vendor masih nempel di registry. Yang
 * benar adalah bertanya ke /models milik provider itu.
 */
export async function discoverModels(
  input: DiscoverInput,
): Promise<string[]> {
  const data = await api<{ ok: boolean; models: string[] }>(
    "/api/llm/discover-models",
    {
      method: "POST",
      body: JSON.stringify({
        provider_id: input.providerId ?? null,
        type: input.type || null,
        base_url: input.baseUrl || null,
        api_key: input.apiKey || null,
      }),
    },
  );
  return dedupe(data.models ?? []);
}

// --- helper model list, murni supaya bisa diuji tanpa network ---------------

/**
 * Tambah model ke daftar, buang duplikat dan entry kosong, dan jaga
 * default_model tetap menunjuk ke model yang benar-benar ada.
 *
 * Tanpa ini, menghapus model default lewat UI meninggalkan default_model
 * menggantung ke nama yang sudah dihapus, dan /api/llm/chat gagal dengan
 * "Provider not found or disabled"-looking error dari sisi provider.
 */
export function addModel(
  models: readonly string[],
  name: string,
): string[] {
  const trimmed = name.trim();
  if (!trimmed) return dedupe(models);
  return dedupe([...models, trimmed]);
}

export function removeModel(
  models: readonly string[],
  name: string,
): string[] {
  return dedupe(models.filter((m) => m !== name));
}

export function dedupe(models: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const m of models) {
    const trimmed = m.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}

/**
 * Bersihkan default_model terhadap daftar model terbaru.
 * Kalau default hilang, jatuh ke model pertama; kalau daftar kosong, kosong.
 */
export function reconcileDefault(
  models: readonly string[],
  currentDefault: string,
): string {
  const list = dedupe(models);
  if (!list.length) return "";
  return list.includes(currentDefault) ? currentDefault : list[0];
}

/**
 * Backend membuat id dari "{type}:{name}", jadi dua provider beda tipe tapi
 * nama sama tetap bentrok di kolom PRIMARY KEY dan jawab 409. Lebih baik
 * dicegat sebelum request.
 */
export function makeProviderId(type: ProviderType, name: string): string {
  return `${type}:${name.trim()}`;
}

/**
 * Gabungkan hasil discovery ke daftar model yang ada.
 *
 * BUKAN replace. Server yang membalas daftar kosong (atau hanya sebagian)
 * tidak boleh menghapus model yang sudah dikonfigurasi dan masih dipakai -
 * hilanginya model default karena satu request yang gagal balik adalah
 * gegabah, dan gejalanya ("Provider not found") tidak menyuruh user cek
 * koneksi sama sekali. Yang ditambahkan hanya yang benar-benar baru; model
 * lama yang tidak lagi ada di server sengaja dibiarkan supaya user yang
 * memutuskan, bukan TrustHub.
 */
export function mergeDiscovered(
  current: readonly string[],
  discovered: readonly string[],
): { models: string[]; added: string[] } {
  const models = dedupe(current);
  const known = new Set(models);
  const added: string[] = [];
  for (const m of dedupe(discovered)) {
    if (known.has(m)) continue;
    known.add(m);
    added.push(m);
    models.push(m);
  }
  return { models, added };
}

/**
 * Alias nama tipe -> tipe kanonik.
 *
 * Tanpa ini user mengetik "gemini", tidak ketemu di daftar, lalu berakhir
 * sebagai tipe custom: base_url wajib diisi manual padahal kami tahu
 * endpointnya, dan id-nya jadi "gemini:..." bukan "google:..." yang punya
 * default.
 *
 * WAJIB sama dengan PROVIDER_TYPE_ALIASES di backend/main.py, karena id
 * provider dihitung oleh kedua sisi sebelum request dikirim.
 */
export const PROVIDER_TYPE_ALIASES: Record<string, string> = {
  gemini: "google",
  "google-gemini": "google",
  googleai: "google",
  "google-ai": "google",
  claude: "anthropic",
  grok: "xai",
  "grok-2": "xai",
  "lm-studio": "lmstudio",
  lm_studio: "lmstudio",
  "lm-studio-local": "lmstudio",
  "googleai-studio": "google",
  "meta-llama": "openai-compatible",
  "openai-compat": "openai-compatible",
  openai_compatible: "openai-compatible",
  custom: "openai-compatible",
};

/** Tipe fallback kalau user mengosongkan field tipe. Satu-satunya tipe
 *  yang boleh tanpa base_url dan tanpa model bawaan, jadi form tetap bisa
 *  disimpan. */
const DEFAULT_PROVIDER_TYPE = "openai-compatible";

/**
 * Normalisasi tipe: lowercase, lalu coba beberapa bentuk sampai satu cocok
 * dengan daftar bawaan. WAJIB sama dengan normalize_provider_type() di
 * backend/main.py, karena makeProviderType di bawah menghitung id client-side
 * dan id itu harus sama persis dengan "{type}:{name}" yang dibuat server.
 *
 * Urutan kandidat penting. "Open AI" adalah cara orang mengetik nama itu
 * setiap hari, dan kalau spasinya diganti tanda hubung hasilnya "open-ai",
 * nama yang tidak ada di daftar bawaan. Akibatnya provider kehilangan
 * base_url default dan user dipaksa mengetik URL yang sebenarnya sudah kami
 * tahu benar, DAN id yang dibuat client beda dengan id dari server.
 *
 *     "  OpenAI "            -> "openai"           (cocok persis)
 *     "Open AI" / "open ai"  -> "openai"           (spasi dihapus, cocok)
 *     "open ai compatible"   -> "openai-compatible" (spasi -> dash)
 *     "gemini" / "Gemini"    -> "google"           (alias)
 *     "vllm"                 -> "vllm"             (tidak dikenal, dipakai apa adanya)
 */
export function normalizeProviderType(raw: string): string {
  const text = (raw ?? "").trim().toLowerCase();
  if (!text) return DEFAULT_PROVIDER_TYPE;
  const squashed = text.replace(/\s+/g, "");
  const dashed = text.split(/\s+/).join("-");
  for (const candidate of [text, squashed, dashed, dashed.replace(/-/g, "_")]) {
    // Alias dicek lebih dulu supaya "gemini" mendarat ke "google", bukan
    // jadi tipe custom yang base_url-nya wajib diisi manual.
    const canonical = PROVIDER_TYPE_ALIASES[candidate];
    if (canonical) return canonical;
    if (hasDefaultBaseUrl(candidate) || KNOWN_PROVIDER_TYPES.includes(candidate as never)) {
      return candidate;
    }
  }
  // Tipe custom: buang karakter yang akan merusak id dan base_url.
  const cleaned = dashed.replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return PROVIDER_TYPE_ALIASES[cleaned] || cleaned || DEFAULT_PROVIDER_TYPE;
}

/**
 * Validasi draft sebelum dikirim. Backend sudah menolak tipe tanpa base_url
 * dengan 422, tapi errornya berupa jargon Pydantic; di sini pesannya
 * langsung dan bisa ditindaklanjuti user.
 *
 * Mengembalikan string[] yang kosong kalau draftnya sah.
 */
export function validateDraft(draft: ProviderDraft): string[] {
  const problems: string[] = [];
  if (!draft.name.trim()) {
    problems.push("Nama provider wajib diisi.");
  }
  const type = normalizeProviderType(draft.type);
  if (!type) {
    problems.push("Tipe provider wajib diisi.");
  } else if (!hasDefaultBaseUrl(type) && !(draft.base_url ?? "").trim()) {
    problems.push(
      `Tipe "${type}" bukan provider bawaan, jadi base_url wajib diisi. ` +
        `TrustHub tidak menebak endpoint untuk tipe di luar daftar.`,
    );
  }
  if (draft.models.length === 0 && !(draft.default_model ?? "").trim()) {
    problems.push("Isi minimal satu model, atau set default model.");
  }
  return problems;
}
