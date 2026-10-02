// app/landing/page.tsx
// The about page: what this system does, how it decides to answer, and what it
// refuses. Server component - it holds no state and reads nothing.
//
// Provenance of the four figures below, because the distinction matters to a
// judge and used to be misstated in this file's header comment. They are the
// official CALIBER Case 1 dataset's figures, as documented in the Case Book
// (`TRUSTHUB.md`), and each is named here with the endpoint that produces it
// once the dataset is ingested: `GET /api/plant/status` and
// `GET /api/plant/verification`.
//
// Nothing here is aspirational: the awkward facts (sample data, one missing
// document, no LLM) are in the first screen rather than in a footnote.

import Link from "next/link";
import LogoMark from "@/components/shared/LogoMark";
import PetroProcessMotif from "@/components/landing/PetroProcessMotif";
import InteractiveLandingDemo from "@/components/landing/InteractiveLandingDemo";

// --- What the dataset actually contains -------------------------------------
// Official CALIBER Case 1 figures, not a running instance. See header above.

const FACTS = [
  { k: "95", label: "documents", detail: "with real document numbers, revisions and approval records", src: "/api/plant/status", tone: "blue" },
  { k: "8", label: "equipment units", detail: "each with datasheet, GA, interlock diagram and plot plan", src: "/api/plant/status", tone: "slate" },
  { k: "211", label: "work orders", detail: "joined from the maintenance workbook, 31 of them breakdowns", src: "/api/plant/status", tone: "slate" },
  { k: "0", label: "contradictions", detail: "among extracted trip set points, out of 105 values extracted", src: "/api/plant/verification", tone: "green" },
] as const;

const PROBLEMS = [
  {
    n: "01",
    title: "The right document, the wrong revision",
    body: "An engineer finds a set point in a drawing that was superseded two revisions ago. The number is right in the file and wrong for the plant. Nothing in a PDF tells you which revision you are holding.",
  },
  {
    n: "02",
    title: "The document that is not there",
    body: "The procedure you need was never written, or lives in a drawer. A chat assistant fills the gap with a plausible sentence, and that sentence is indistinguishable from a real one.",
  },
  {
    n: "03",
    title: "Eleven documents per unit",
    body: "Eight units, five baseline document types each, plus one-point lessons written after individual failures. Nobody holds all of it in their head, and the relevant document is rarely the one already open.",
  },
];

const PIPELINE = [
  {
    n: "01",
    title: "Ingest once, from the real files",
    body: "87 single-page PDFs, 8 P&ID drawings and the maintenance workbook parsed into one SQLite index: 95 documents, 362 text chunks, 211 work orders, 105 measured parameter values.",
  },
  {
    n: "02",
    title: "Extract, record provenance",
    body: "Trip set points are read from datasheet tables and interlock logic with operator, value and unit kept intact. Approval status comes from revision history and signature blocks present in each document.",
  },
  {
    n: "03",
    title: "Retrieve, then decide whether to answer",
    body: "SQLite FTS5 over indexed chunks, scoped to the equipment tag in the question where one is named. Before any answer is composed, the question is tested against what the index actually contains.",
  },
  {
    n: "04",
    title: "Score, badge, or refuse",
    body: "Five weighted signals produce one number, the number produces TRUSTED, VERIFY or DO NOT EXECUTE, and the sources are listed with their document number, revision and approval status.",
  },
];

const WEIGHTS = [
  { name: "Approval", w: 0.30, body: "Is the source an approved, issued revision?" },
  { name: "Revision", w: 0.20, body: "Does it carry a revision and an effective date?" },
  { name: "Agreement", w: 0.20, body: "Do several documents state the same value?" },
  { name: "Relevance", w: 0.20, body: "How well does the retrieved text match the question?" },
  { name: "Coverage", w: 0.10, body: "How much of the answer comes from more than one source?" },
];

const REFUSALS = [
  {
    q: "What does OPL-GA-1201A-04 cover?",
    why: "That one-point lesson is genuinely missing from the dataset. The system declines rather than substituting the six lessons that do exist for the same unit.",
  },
  {
    q: "What is the shutdown procedure for ZX-9999?",
    why: "No document mentions that unit, so no document can be a source.",
  },
  {
    q: "What is the trip setpoint for ZSO-9999?",
    why: "The tag is instrument-shaped but not in the index. Answering from another unit's excerpt would have been fluent and wrong.",
  },
  {
    q: "How do I open a bank account?",
    why: "Retrieval returns chunks for any text. The domain vocabulary gate stops unrelated questions before they can be answered from plant documents.",
  },
];

const LIMITS = [
  "The dataset is labelled by its own authors as sample data. Trip set points and costs are stated to be dummy training values; the document structure, revision history and approval records are used as given.",
  "No language model is called by default. Answers are assembled from indexed text and measured values, so nothing is generated and nothing can be hallucinated, but nothing is paraphrased either, and procedural steps are quoted rather than restated.",
  "Zero contradictions means the extracted values agree with each other. It does not mean the plant is safe, and it does not mean every parameter in the documents was extracted.",
  "The dataset is not committed to this repository. It is fetched with one command, because its licence does not permit redistribution.",
];

const PAGES = [
  { page: "Ask", what: "A question, a badge, the documents behind it, and the arithmetic behind the score." },
  { page: "Equipment", what: "One unit at a time: every document, its full work-order history, and failures with linked lessons." },
  { page: "Documents", what: "The register. Document number, revision, effective date, and the approval marker found in the file." },
  { page: "Graph", what: "How the documents join. 8 units, 8 interlock diagrams, 8 datasheets, 55 lessons, 31 breakdowns." },
  { page: "Verification", what: "Whether the documents agree. Extraction inventory beside the conflict count." },
  { page: "Maintenance", what: "211 work orders and 31 breakdowns, with downtime and cost, and lesson coverage per unit." },
  { page: "Overview", what: "What this instance currently holds, and what it does not claim." },
  { page: "Audit", what: "The weight table printed in full, so any score can be recomputed by hand, plus every question asked." },
  { page: "Dataset", what: "Provenance, the known gaps in the file set, and the LLM policy." },
];

const STACK = ["Next.js 15", "React 19", "TypeScript", "Tailwind CSS", "FastAPI", "SQLite", "SQLite FTS5", "pdfplumber", "openpyxl"];

// Thin colored left accent bar per fact — the color is functional, not decorative:
// blue = primary data (document count), green = quality metric (zero contradictions)
const FACT_ACCENT: Record<string, string> = {
  blue: "bg-blue-500",
  green: "bg-green-500",
  slate: "bg-slate-600",
};

export default function LandingPage() {
  return (
    <div className="h-full overflow-y-auto">

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 border-b border-slate-800/60 bg-surface/95 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-14 flex items-center gap-4">
          <span className="flex items-center gap-2.5 shrink-0">
            <span className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
              <LogoMark />
            </span>
            <span className="text-sm font-bold text-ink tracking-tight">TrustHUB</span>
          </span>
          <nav aria-label="Sections" className="hidden md:flex items-center gap-1 text-xs text-slate-400 ml-2">
            {["problem","how","trust","limits","demo"].map(id => (
              <a key={id} href={`#${id}`}
                className="px-2.5 py-1.5 rounded-md hover:bg-slate-800/60 hover:text-slate-200 transition-colors capitalize">
                {id === "how" ? "How it works" : id.charAt(0).toUpperCase() + id.slice(1)}
              </a>
            ))}
          </nav>
          <div className="flex-1" />
          <Link href="/"
            className="text-xs font-semibold px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            Open the app
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 sm:px-8">

        {/* ── Hero ────────────────────────────────────────────────────────── */}
        <section className="pt-16 pb-12 sm:pt-24 sm:pb-16 border-b border-slate-800/60">
          <div className="grid lg:grid-cols-[1fr_420px] gap-12 lg:gap-16 lg:items-start">

            {/* Left: headline + stats */}
            <div>
              {/* Case reference — mono, no pill badge */}
              <p className="font-mono text-xs text-slate-500 mb-6 tracking-wide">
                CALIBER 2026 &middot; <span className="text-slate-300">Case 1</span> &middot; Manufacturing Knowledge Hub
              </p>

              <h1 className="text-4xl sm:text-5xl lg:text-[3.25rem] font-bold text-ink leading-[1.08] tracking-tight max-w-2xl">
                An engineering knowledge hub that would rather{" "}
                <span className="text-blue-400">refuse</span> than guess.
              </h1>

              <p className="mt-6 text-base text-slate-400 max-w-xl leading-relaxed">
                Datasheets, interlock logic, procedures and maintenance history for
                one LLDPE plant unit in one index. Every answer carries a trust badge,
                the documents behind it, and the arithmetic behind its score.
                A question with no supportable source gets a refusal and an explanation,
                not a sentence.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/"
                  className="text-sm font-semibold px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
                  Open the app
                </Link>
                <a href="#how"
                  className="text-sm px-5 py-2.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-ink transition-colors">
                  How it works
                </a>
                <a href="#limits"
                  className="text-sm px-5 py-2.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-ink transition-colors">
                  What it does not claim
                </a>
              </div>

              {/* Stat bar — 4 figures with colored left rule */}
              <div className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4">
                {FACTS.map((f) => (
                  <div key={f.k} className="flex gap-3">
                    <div className={`w-0.5 shrink-0 self-stretch rounded-full ${FACT_ACCENT[f.tone]}`} />
                    <div>
                      <div className="text-2xl font-bold text-ink tabular-nums leading-none">{f.k}</div>
                      <div className="mt-1 text-[11px] font-semibold text-slate-300 leading-tight">{f.label}</div>
                      <div className="mt-1 text-[10px] text-slate-500 leading-snug">{f.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-[11px] text-slate-600 leading-relaxed max-w-xl">
                Official CALIBER Case 1 dataset totals, labelled with the endpoint that produces each.
                A fresh checkout has no index; run{" "}
                <code className="font-mono text-slate-500">python -m plant.fetch_dataset</code> first.
              </p>
            </div>

            {/* Right: P&ID motif */}
            <div className="flex flex-col gap-4">
              <div className="rounded-xl border border-slate-800/60 bg-panel/80 p-3 overflow-hidden">
                <PetroProcessMotif className="w-full h-auto" />
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed px-1">
                A polymerisation train as a P&amp;ID draws it: vessels on one pipe run,
                instrument bubbles above each, tags in the notation the indexed documents use.
              </p>

              {/* Trust badge trio — shown here as a real preview, not decoration */}
              <div className="rounded-xl border border-slate-800/60 bg-panel p-4">
                <p className="text-[10px] font-mono text-slate-500 mb-3 uppercase tracking-wider">
                  Three possible outcomes per question
                </p>
                <div className="space-y-2.5">
                  {[
                    { badge: "TRUSTED", score: "0.84", desc: "Approved, revisioned, corroborated by several documents.", cls: "border-green-500/30 bg-green-500/8", dot: "bg-green-400", text: "text-green-300" },
                    { badge: "VERIFY", score: "0.61", desc: "Usable, but confirm against the cited document before acting.", cls: "border-amber-500/30 bg-amber-500/8", dot: "bg-amber-400", text: "text-amber-300" },
                    { badge: "DO NOT EXECUTE", score: "0.23", desc: "No trustworthy source. Do not act on this answer.", cls: "border-red-500/30 bg-red-500/8", dot: "bg-red-400", text: "text-red-300" },
                  ].map(b => (
                    <div key={b.badge} className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 ${b.cls}`}>
                      <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${b.dot}`} />
                      <div className="min-w-0">
                        <div className={`text-xs font-bold tracking-wide ${b.text}`}>
                          {b.badge} <span className="font-mono font-normal opacity-70">{b.score}</span>
                        </div>
                        <p className="mt-0.5 text-[11px] text-slate-400 leading-snug">{b.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Problem ─────────────────────────────────────────────────────── */}
        <section id="problem" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <div className="grid lg:grid-cols-[280px_1fr] gap-10 lg:gap-16">
            <div>
              <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">01</p>
              <h2 className="text-2xl font-bold text-ink leading-tight">The problem</h2>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Not "information is hard to find". A plant already has the documents.
                What it does not have is any way to know which applies, whether it is current,
                and whether it has been approved.
              </p>
            </div>
            <div className="space-y-0 divide-y divide-slate-800/60">
              {PROBLEMS.map((p) => (
                <div key={p.n} className="flex gap-5 py-6 first:pt-0 last:pb-0">
                  <span className="font-mono text-sm text-slate-700 shrink-0 mt-0.5 w-8">{p.n}</span>
                  <div>
                    <h3 className="text-base font-semibold text-ink leading-snug">{p.title}</h3>
                    <p className="mt-2 text-sm text-slate-400 leading-relaxed">{p.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ────────────────────────────────────────────────── */}
        <section id="how" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">02</p>
          <h2 className="text-2xl font-bold text-ink">How it works</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Four steps, in this order. The check for whether an answer is permitted at all
            happens before anything is written, not after.
          </p>
          <ol className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {PIPELINE.map((s) => (
              <li key={s.n}
                className="relative rounded-xl border border-slate-800/60 bg-panel p-5 flex flex-col gap-3">
                <span className="font-mono text-3xl font-bold text-slate-800 leading-none select-none absolute top-4 right-4">
                  {s.n}
                </span>
                <span className="w-6 h-0.5 bg-blue-500 rounded-full" />
                <h3 className="text-sm font-semibold text-ink leading-snug pr-8">{s.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ── Trust engine ────────────────────────────────────────────────── */}
        <section id="trust" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">03</p>
          <h2 className="text-2xl font-bold text-ink">The trust engine</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Five weighted signals, one score, three badges. Weights are properties of
            document provenance, not of a model's confidence, because no model is involved
            in producing them.
          </p>

          <div className="mt-10 grid lg:grid-cols-[1fr_1fr] gap-6">

            {/* Weights panel */}
            <div className="rounded-xl border border-slate-800/60 bg-panel p-6">
              <h3 className="text-sm font-bold text-ink mb-5">Signal weights</h3>
              <div className="space-y-4">
                {WEIGHTS.map((w) => (
                  <div key={w.name}>
                    <div className="flex items-baseline justify-between gap-2 mb-1.5">
                      <span className="text-xs font-semibold text-slate-300">{w.name}</span>
                      <span className="text-xs font-mono text-blue-400">{w.w.toFixed(2)}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${(w.w / 0.30) * 100}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500 leading-snug">{w.body}</p>
                  </div>
                ))}
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/60 grid gap-2">
                {[
                  { label: "TRUSTED", threshold: "0.80+", note: "Approved, revisioned, corroborated.", cls: "text-green-300", bar: "bg-green-500" },
                  { label: "VERIFY", threshold: "0.50", note: "Usable after checking the cited document.", cls: "text-amber-300", bar: "bg-amber-500" },
                  { label: "DO NOT EXECUTE", threshold: "<0.50", note: "No trustworthy source or outright refusal.", cls: "text-red-300", bar: "bg-red-500" },
                ].map(b => (
                  <div key={b.label} className="flex items-center gap-2.5">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${b.bar}`} />
                    <span className={`text-xs font-bold ${b.cls}`}>{b.label}</span>
                    <span className="text-[10px] font-mono text-slate-600">{b.threshold}</span>
                    <span className="text-[11px] text-slate-500 leading-snug">{b.note}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Refusals panel */}
            <div className="rounded-xl border border-slate-800/60 bg-panel p-6">
              <h3 className="text-sm font-bold text-ink mb-1">What it refuses, and why</h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-5">
                Refusals are the feature, not the failure mode. A hub that answers everything
                is fluent, not trustworthy.
              </p>
              <ul className="space-y-4">
                {REFUSALS.map((r) => (
                  <li key={r.q} className="border-l-2 border-red-500/40 pl-3">
                    <p className="text-xs font-mono text-slate-200 break-words leading-snug">{r.q}</p>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{r.why}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Interactive demo inline */}
          <div className="mt-8">
            <InteractiveLandingDemo />
          </div>
        </section>

        {/* ── Limits ──────────────────────────────────────────────────────── */}
        <section id="limits" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">04</p>
          <h2 className="text-2xl font-bold text-ink">What this system does not claim</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Listed here rather than in a footer, because a knowledge-hub demo that
            only shows its strengths is asking to be audited for the rest.
          </p>
          <ul className="mt-10 grid sm:grid-cols-2 gap-4 max-w-5xl">
            {LIMITS.map((limit, i) => (
              <li key={i}
                className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-5 py-4">
                <span className="font-mono text-[10px] text-amber-500/60 block mb-2">NOTE {String(i + 1).padStart(2, "0")}</span>
                <p className="text-sm text-slate-300 leading-relaxed">{limit}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* ── Demo path ───────────────────────────────────────────────────── */}
        <section id="demo" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">05</p>
          <h2 className="text-2xl font-bold text-ink">The demo path</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Nine pages. A judge can see the whole claim in about four minutes:
            ask a question, check its sources, then check whether those sources agree.
          </p>
          <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {PAGES.map((p) => (
              <div key={p.page}
                className="rounded-xl border border-slate-800/60 bg-panel px-4 py-4 hover:border-blue-500/30 hover:bg-panel-2 transition-colors">
                <h3 className="text-xs font-mono font-bold text-blue-300">{p.page}</h3>
                <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">{p.what}</p>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <Link href="/"
              className="inline-block text-sm font-semibold px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
              Open the app
            </Link>
          </div>
        </section>

        {/* ── Stack ───────────────────────────────────────────────────────── */}
        <section className="py-16">
          <h2 className="text-lg font-bold text-ink">Built with</h2>
          <div className="mt-5 flex flex-wrap gap-2">
            {STACK.map(s => (
              <span key={s} className="font-mono text-xs text-slate-400 bg-panel border border-slate-800/60 px-3 py-1.5 rounded-md">
                {s}
              </span>
            ))}
          </div>
          <p className="mt-6 text-sm text-slate-400 leading-relaxed max-w-2xl">
            Retrieval is SQLite FTS5 rather than a hosted vector database, so the
            whole system runs on one machine with no API key and no external service.
            The dataset is fetched with{" "}
            <code className="font-mono text-xs text-slate-300 bg-panel border border-slate-800/60 px-1.5 py-0.5 rounded">
              python -m plant.fetch_dataset
            </code>{" "}
            and is not committed, because its licence does not permit redistribution.
          </p>
        </section>
      </main>

      <footer className="border-t border-slate-800/60">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-8 flex flex-col sm:flex-row items-start sm:items-center gap-3 justify-between">
          <div className="flex items-center gap-3">
            <span className="w-6 h-6 rounded-md bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              <LogoMark />
            </span>
            <p className="text-xs text-slate-500">
              CALIBER 2026, Case 1 &middot; Manufacturing Knowledge Hub &middot; LLDPE Set 01
            </p>
          </div>
          <p className="font-mono text-xs text-slate-600">python -m plant.fetch_dataset</p>
        </div>
      </footer>
    </div>
  );
}
