"use client";

// components/LLMProviderManager.tsx
// Panel pengelolaan provider LLM: tambah provider, atur daftar model per
// provider, tandai default, hapus.
//
// Yang membuat panel ini berguna: daftar model bukan field teks sekali tulis.
// Satu provider bisa punya puluhan model (mis. Ollama lokal), dan user butuh
// menambah atau menghapus per model tanpa mengedit JSON.
//
// API key tidak pernah dibaca balik dari server. Backend menyimpannya terenkripsi
// (llm_providers.api_key) dan tidak pernah mengirimkannya di response, jadi
// field di form selalu kosong saat edit - kosong berarti "biarkan yang lama".

import { useEffect, useMemo, useState } from "react";
import { useLLMProviders } from "@/hooks/useLLMProviders";
import {
  PROVIDER_BASE_URLS,
  PROVIDER_TYPE_LABELS,
  PROVIDER_TYPES,
  addModel,
  discoverModels,
  hasDefaultBaseUrl,
  isDeletable,
  mergeDiscovered,
  modelSuggestions,
  normalizeProviderType,
  reconcileDefault,
  removeModel,
  validateDraft,
  ApiError,
  type LLMProvider,
  type ProviderDraft,
  type ProviderType,
} from "@/lib/llmProviders";

const inputCls =
  "bg-slate-800 border border-slate-700/60 rounded-lg px-2.5 py-1 text-xs text-slate-200 outline-none placeholder-slate-600 focus:border-blue-500/60";
const btnPrimary =
  "rounded-lg bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed";
const btnGhost =
  "rounded-lg border border-slate-700/60 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800/60 disabled:opacity-40 disabled:cursor-not-allowed";

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-[10px] uppercase tracking-wide text-slate-500">{children}</span>;
}

function Notice({ kind, text }: { kind: "ok" | "err"; text: string }) {
  const cls =
    kind === "ok"
      ? "border-emerald-500/30 bg-emerald-900/20 text-emerald-300"
      : "border-red-500/30 bg-red-900/20 text-red-400";
  return <p className={`rounded-lg border px-3 py-2 text-xs ${cls}`}>{text}</p>;
}

// --- editor daftar model ----------------------------------------------------

function ModelEditor({
  provider,
  onSave,
  disabled,
}: {
  provider: LLMProvider;
  onSave: (models: string[], defaultModel: string) => Promise<void>;
  disabled: boolean;
}) {
  // Default disimpan lokal supaya reconciliation tidak menyentuh apa pun
  // sebelum user menekan Simpan.
  const [models, setModels] = useState<string[]>(provider.models);
  const [defaultModel, setDefaultModel] = useState(provider.default_model);
  const [draft, setDraft] = useState("");
  const [discovering, setDiscovering] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  useEffect(() => {
    setModels(provider.models);
    setDefaultModel(provider.default_model);
  }, [provider.id, provider.models, provider.default_model]);

  const suggestions = modelSuggestions(provider.type);
  const missing = useMemo(
    () => suggestions.filter((s) => !models.includes(s)),
    [suggestions, models],
  );
  const dirty =
    JSON.stringify(models) !== JSON.stringify(provider.models) ||
    defaultModel !== provider.default_model;

  const commit = async () => {
    const next = addModel(models, draft);
    setModels(next);
    setDraft("");
    // Kalau draft ini jadi model pertama, default harus ikut ke sana,
    // kalau tidak default_model menunjuk model yang tidak ada.
    const nextDefault = reconcileDefault(next, defaultModel);
    setDefaultModel(nextDefault);
    await onSave(next, nextDefault);
  };

  const discover = async () => {
    setDiscovering(true);
    setNotice(null);
    setDiscoverError(null);
    try {
      const found = await discoverModels({ providerId: provider.id });
      const { models: next, added } = mergeDiscovered(models, found);
      if (added.length === 0) {
        setNotice(
          found.length === 0
            ? "Server tidak melaporkan model apa pun. Kalau ini salah, cek base_url - beberapa endpoint butuh path /v1 di akhirnya."
            : `Semua ${found.length} model di server sudah terdaftar.`,
        );
        return;
      }
      setModels(next);
      // Default tidak boleh dilompatin ke model baru: kalau default lama
      // masih ada di daftar (merge tidak menghapus), biarkan saja.
      const nextDefault = reconcileDefault(next, defaultModel);
      setDefaultModel(nextDefault);
      await onSave(next, nextDefault);
      setNotice(`${added.length} model baru ditambahkan dari server.`);
    } catch (err) {
      setDiscoverError(
        err instanceof ApiError
          ? err.message
          : "Gagal menghubungi endpoint provider.",
      );
    } finally {
      setDiscovering(false);
    }
  };

  return (
    <div className="mt-3 space-y-2 border-t border-slate-800/60 pt-3">
      <div className="flex items-center justify-between gap-2">
        <Label>Model ({models.length})</Label>
        <div className="flex items-center gap-2">
          {dirty && (
            <span className="text-[10px] text-amber-400">belum disimpan</span>
          )}
          <button
            type="button"
            className={btnGhost}
            disabled={disabled || discovering}
            title="Tanya /models ke endpoint provider ini dan tambahkan yang belum terdaftar"
            onClick={() => void discover()}
          >
            {discovering ? "Mengecek..." : "Ambil dari server"}
          </button>
        </div>
      </div>

      {notice && (
        <p className="rounded border border-emerald-500/30 bg-emerald-900/15 px-2 py-1 text-[10px] text-emerald-300">
          {notice}
        </p>
      )}
      {discoverError && (
        <p className="rounded border border-red-500/30 bg-red-900/15 px-2 py-1 text-[10px] text-red-400">
          {discoverError}
        </p>
      )}

      {models.length === 0 ? (
        <p className="text-[11px] text-slate-500">
          Belum ada model. Chat tidak akan jalan sampai minimal satu model didaftarkan.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {models.map((model) => {
            const isDefault = model === defaultModel;
            return (
              <span
                key={model}
                className={`group inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[10px] ${
                  isDefault
                    ? "border-blue-500/50 bg-blue-500/10 text-blue-200"
                    : "border-slate-700/60 bg-slate-800/60 text-slate-300"
                }`}
              >
                {isDefault && <span className="text-blue-400">*</span>}
                {model}
                <button
                  type="button"
                  title={isDefault ? "Model default" : "Jadikan default"}
                  disabled={disabled}
                  onClick={() => {
                    setDefaultModel(model);
                    void onSave(models, model);
                  }}
                  className="text-slate-500 hover:text-blue-300 disabled:opacity-40"
                >
                  {isDefault ? "●" : "○"}
                </button>
                <button
                  type="button"
                  title="Hapus model"
                  disabled={disabled}
                  onClick={() => {
                    const next = removeModel(models, model);
                    setModels(next);
                    const nextDefault = reconcileDefault(next, defaultModel);
                    setDefaultModel(nextDefault);
                    void onSave(next, nextDefault);
                  }}
                  className="text-slate-500 hover:text-red-400 disabled:opacity-40"
                >
                  x
                </button>
              </span>
            );
          })}
        </div>
      )}

      {missing.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-slate-600">Saran:</span>
          {missing.slice(0, 5).map((s) => {
            const next = addModel(models, s);
            const nextDefault = reconcileDefault(next, defaultModel);
            return (
              <button
                key={s}
                type="button"
                disabled={disabled}
                onClick={() => {
                  setModels(next);
                  setDefaultModel(nextDefault);
                  void onSave(next, nextDefault);
                }}
                className="rounded border border-slate-700/60 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 hover:border-slate-500 hover:text-slate-200 disabled:opacity-40"
              >
                + {s}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex gap-1.5">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void commit();
            }
          }}
          placeholder="Nama model, mis. gpt-4o-mini atau llama3.1:8b"
          className={`${inputCls} flex-1 font-mono`}
        />
        <button type="button" className={btnGhost} disabled={disabled || !draft.trim()} onClick={() => void commit()}>
          Tambah
        </button>
      </div>
    </div>
  );
}

// --- form tambah provider ---------------------------------------------------

function emptyDraft() {
  return {
    name: "",
    type: "openai" as ProviderType,
    base_url: "",
    api_key: "",
    models: [] as string[],
    default_model: "",
    max_tokens: 4096,
    supports_tools: true,
    supports_vision: false,
    enabled: true,
  };
}

function AddProviderForm({
  onSubmit,
  busy,
}: {
  onSubmit: (draft: ProviderDraft) => Promise<void>;
  busy: boolean;
}) {
  const [draft, setDraft] = useState(emptyDraft);
  const [open, setOpen] = useState(false);
  // Hasil /models untuk draft yang SEDANG diketik. Dipisah dari draft.models
  // supaya "ditemukan di server" tidak sama dengan "sudah terdaftar" - user
  // yang memutuskan mana yang mau dipakai.
  const [discovered, setDiscovered] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  const suggestions = modelSuggestions(draft.type);
  const discoveredCount = discovered.length;
  const set = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  // Endpoint, provider type, atau api_key berubah = hasil discovery lama
  // sudah tidak berlaku. Kalau tidak dibuang, user melihat chip model dari
  // server A lalu menyimpan ke server B dan chat gagal dengan model yang
  // tidak ada - persis kesalahan yang tombol ini untuk dihindari.
  const endpointKey = `${draft.type}|${draft.base_url.trim()}|${draft.api_key.trim()}`;
  const [lastEndpointKey, setLastEndpointKey] = useState(endpointKey);
  if (lastEndpointKey !== endpointKey) {
    setLastEndpointKey(endpointKey);
    setDiscovered([]);
    setDiscoverError(null);
  }

  const discover = async () => {
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const found = await discoverModels({
        type: normalizeProviderType(draft.type),
        baseUrl: draft.base_url.trim() || null,
        apiKey: draft.api_key.trim() || null,
      });
      setDiscovered(found);
      if (found.length === 0) {
        setDiscoverError(
          "Server tidak melaporkan model apa pun. Kalau ini tidak sesuai, cek base_url dan api_key.",
        );
      }
    } catch (err) {
      setDiscovered([]);
      setDiscoverError(
        err instanceof ApiError
          ? err.message
          : "Gagal menghubungi endpoint provider.",
      );
    } finally {
      setDiscovering(false);
    }
  };

  // Normalisasi saat submit, bukan saat mengetik: user harus boleh menulis
  // "Open AI" dan melihatnya apa adanya sampai menekan tombol.
  const normalizedType = normalizeProviderType(draft.type);
  const problems = validateDraft({
    ...draft,
    type: normalizedType,
    base_url: draft.base_url.trim() || null,
  });

  const submit = async () => {
    if (problems.length) return;
    await onSubmit({
      ...draft,
      type: normalizedType,
      base_url: draft.base_url.trim() || null,
      api_key: draft.api_key.trim() || null,
      default_model: reconcileDefault(draft.models, draft.default_model),
    });
    setDraft(emptyDraft());
    setOpen(false);
  };

  if (!open) {
    return (
      <button type="button" className={btnPrimary} onClick={() => setOpen(true)}>
        + Tambah Provider
      </button>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-slate-700/60 bg-slate-900/40 p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1">
          <Label>Nama</Label>
          <input
            value={draft.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="mis. openai atau lokal"
            className={`${inputCls} w-full`}
          />
        </label>
        <label className="space-y-1">
          <Label>Tipe</Label>
          {/* Input teks + datalist, bukan <select>. Backend menerima tipe apa
              pun (normalize_provider_type), jadi "groq", "lmstudio", atau
              "vllm" harus bisa diketik - <select> hanya bisa menampilkan
              daftar yang sudah hardcode, dan user yang provider-nya tidak
              ada di daftar itu tidak punya jalan lain. */}
          <input
            list="trusthub-provider-types"
            value={draft.type}
            onChange={(e) => set("type", e.target.value)}
            placeholder="openai-compatible"
            className={`${inputCls} w-full font-mono`}
          />
          <datalist id="trusthub-provider-types">
            {PROVIDER_TYPES.map((t) => (
              <option key={t} value={t} label={PROVIDER_TYPE_LABELS[t]} />
            ))}
            {/* "custom" sengaja jadi entri tersendiri, bukan hanyaketik-bebas.
                Provider milik sendiri (router lokal, proxy internal, vLLM di
                port ganjil) tidak mungkin ada di daftar kami, tapi user
                tidak akan menyimpulkan itu kalau dropdown-nya diam-diam
                hanya berisi vendor. Label-nya menyebutkan base_url wajib
                supaya tidak ada kejutan saat simpan ditolak. */}
            <option
              value="custom"
              label="Custom / server sendiri - base_url wajib diisi manual"
            />
          </datalist>
        </label>
      </div>

      <label className="block space-y-1">
        <Label>
          Base URL{" "}
          {hasDefaultBaseUrl(normalizeProviderType(draft.type)) ? "(opsional)" : "(wajib)"}
        </Label>
        <input
          value={draft.base_url}
          onChange={(e) => set("base_url", e.target.value)}
          placeholder={
            hasDefaultBaseUrl(normalizeProviderType(draft.type))
              ? PROVIDER_BASE_URLS[normalizeProviderType(draft.type)] ?? "https://api.example.com/v1"
              : "https://api.example.com/v1"
          }
          className={`${inputCls} w-full font-mono`}
        />
        {!hasDefaultBaseUrl(normalizeProviderType(draft.type)) && (
          <p className="text-[10px] text-amber-400">
            Tipe <span className="font-mono">{draft.type || "?"}</span> bukan provider bawaan,
            jadi TrustHub tidak menebak endpoint-nya. Tanpa base_url, request akan ditolak.
          </p>
        )}
      </label>

      <label className="block space-y-1">
        <Label>API Key (opsional untuk server lokal)</Label>
        <input
          type="password"
          value={draft.api_key}
          onChange={(e) => set("api_key", e.target.value)}
          placeholder="disimpan terenkripsi di backend, tidak pernah dikembalikan"
          className={`${inputCls} w-full font-mono`}
        />
      </label>

      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <Label>Model</Label>
          <button
            type="button"
            className={btnGhost}
            disabled={discovering}
            title="Tanya /models ke endpoint yang diisi di atas, pakai api_key yang diketik"
            onClick={() => void discover()}
          >
            {discovering ? "Mengecek..." : "Ambil dari server"}
          </button>
        </div>

        {discoverError && (
          <p className="rounded border border-red-500/30 bg-red-900/15 px-2 py-1 text-[10px] text-red-400">
            {discoverError}
          </p>
        )}
        {discoveredCount > 0 && (
          <p className="text-[10px] text-slate-500">
            {discoveredCount} model ditemukan di server. Yang diklik ikut
            terdaftar; sisanya bisa diketik manual di bawah.
          </p>
        )}

        <div className="flex flex-wrap gap-1.5">
          {/* Kalau server sudah dijawab, daftar model asli lebih berguna
              daripada tebakan MODEL_SUGGESTIONS: nama lokal ("qwen2.5-coder:7b")
              tidak akan pernah ada di tebakan, dan model lama yang dihapus
              vendor masih nempel di sana. */}
          {(discovered.length > 0 ? discovered : suggestions).map((s) => {
            const on = draft.models.includes(s);
            return (
              <button
                key={s}
                type="button"
                onClick={() =>
                  set(
                    "models",
                    on ? removeModel(draft.models, s) : addModel(draft.models, s),
                  )
                }
                className={`rounded border px-2 py-0.5 font-mono text-[10px] ${
                  on
                    ? "border-blue-500/50 bg-blue-500/10 text-blue-200"
                    : "border-slate-700/60 bg-slate-800/60 text-slate-400 hover:text-slate-200"
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1">
          <Label>Max tokens</Label>
          <input
            type="number"
            min={1}
            value={draft.max_tokens}
            onChange={(e) => set("max_tokens", Number(e.target.value) || 1)}
            className={`${inputCls} w-full`}
          />
        </label>
        <div className="flex items-end gap-3 text-[11px] text-slate-400">
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={draft.supports_tools}
              onChange={(e) => set("supports_tools", e.target.checked)}
            />
            tools
          </label>
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={draft.supports_vision}
              onChange={(e) => set("supports_vision", e.target.checked)}
            />
            vision
          </label>
        </div>
      </div>

      {problems.length > 0 && (
        <ul className="rounded-lg border border-amber-500/30 bg-amber-900/15 px-3 py-2 text-[10px] text-amber-300 space-y-0.5">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          className={btnPrimary}
          disabled={busy || problems.length > 0}
          onClick={() => void submit()}
        >
          {busy ? "Menyimpan..." : "Simpan Provider"}
        </button>
        <button type="button" className={btnGhost} onClick={() => setOpen(false)}>
          Batal
        </button>
      </div>
      <p className="text-[10px] text-slate-600">
        ID dibuat dari <span className="font-mono">tipe:nama</span>, jadi nama yang sama
        dengan tipe berbeda boleh - nama yang sama dengan tipe sama akan 409.
      </p>
    </div>
  );
}

// --- panel utama ------------------------------------------------------------

export default function LLMProviderManager() {
  const { providers, loading, busy, error, create, update, remove } = useLLMProviders();
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading) {
    return <p className="text-xs text-slate-500 animate-pulse">Memuat registry provider...</p>;
  }

  const enabled = providers.filter((p) => p.enabled);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-400">
          {providers.length === 0
            ? "Belum ada provider."
            : `${providers.length} provider, ${enabled.length} aktif.`}
        </p>
        <AddProviderForm
          busy={busy}
          onSubmit={async (draft) => {
            try {
              await create({
                name: draft.name.trim(),
                type: draft.type,
                base_url: draft.base_url,
                api_key: draft.api_key,
                models: draft.models,
                default_model: draft.default_model,
                max_tokens: draft.max_tokens,
                supports_tools: draft.supports_tools,
                supports_vision: draft.supports_vision,
                enabled: draft.enabled,
              });
              setNotice(`Provider "${draft.name.trim()}" disimpan.`);
            } catch {
              // Pesan sudah ditulis hook ke `error`; biarkan form tetap
              // terbuka supaya isinya tidak hilang.
            }
          }}
        />
      </div>

      {notice && <Notice kind="ok" text={notice} />}
      {error && <Notice kind="err" text={error} />}

      {providers.length === 0 && (
        <p className="rounded-lg border border-slate-800/60 bg-slate-900/30 p-4 text-xs text-slate-500">
          Panel chat di Cortex memakai provider di sini. Tanpa provider aktif, chat akan
          gagal dengan <span className="font-mono">Provider not found or disabled</span>.
        </p>
      )}

      {providers.map((provider) => {
        const open = expanded === provider.id;
        const deletable = isDeletable(provider.type);
        return (
          <div
            key={provider.id}
            className={`rounded-lg border bg-[#0d1117] ${
              provider.enabled ? "border-slate-700/60" : "border-slate-800/60 opacity-70"
            }`}
          >
            <div className="flex items-center gap-2 p-3">
              <button
                type="button"
                onClick={() => setExpanded(open ? null : provider.id)}
                className="min-w-0 flex-1 text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="truncate text-xs font-medium text-white">{provider.name}</span>
                  <span className="rounded border border-slate-700/60 px-1 py-0.5 font-mono text-[9px] text-slate-400">
                    {provider.type}
                  </span>
                  {!provider.enabled && (
                    <span className="rounded border border-slate-700/60 px-1 py-0.5 text-[9px] text-slate-500">
                      nonaktif
                    </span>
                  )}
                </div>
                <p className="mt-0.5 truncate font-mono text-[10px] text-slate-500">
                  {provider.base_url ?? "(base url bawaan)"} - default:{" "}
                  {provider.default_model || "(belum ada)"}
                </p>
              </button>

              <button
                type="button"
                className={btnGhost}
                disabled={busy}
                onClick={() =>
                  void update(provider.id, { enabled: !provider.enabled }).then(() =>
                    setNotice(`${provider.name} ${provider.enabled ? "dinonaktifkan" : "diaktifkan"}.`),
                  )
                }
              >
                {provider.enabled ? "Nonaktif" : "Aktif"}
              </button>

              <button
                type="button"
                className={btnGhost}
                disabled={busy || !deletable}
                title={
                  deletable
                    ? "Hapus provider"
                    : "Tipe bawaan tidak bisa dihapus (backend menolak dengan 403)"
                }
                onClick={() => {
                  if (!window.confirm(`Hapus provider "${provider.name}"?`)) return;
                  void remove(provider.id)
                    .then(() => setNotice(`Provider "${provider.name}" dihapus.`))
                    .catch(() => undefined);
                }}
              >
                Hapus
              </button>
            </div>

            {open && (
              <div className="px-3 pb-3">
                <ModelEditor
                  provider={provider}
                  disabled={busy}
                  onSave={async (models, defaultModel) => {
                    try {
                      await update(provider.id, { models, default_model: defaultModel });
                    } catch {
                      // Pesan sudah ada di `error`.
                    }
                  }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
