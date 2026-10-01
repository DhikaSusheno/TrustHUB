// app/landing/page.tsx
// The about page: what this system does, how it decides to answer, and what it
// refuses. Server component - it holds no state and reads nothing.
//
// Every number on this page is one the backend returns. Where a number is a
// measurement of the dataset rather than a property of the code, it says which
// endpoint produces it, so a reader can check it instead of taking it on trust.
// Nothing here is aspirational: the awkward facts (sample data, one missing
// document, no LLM) are in the first screen rather than in a footnote.

import Link from "next/link";

// --- What the dataset actually contains -------------------------------------
// From /api/plant/status and /api/plant/verification with the official
// CALIBER dataset ingested.

const FACTS = [
  { k: "95", v: "documents indexed, with real document numbers, revisions and approval records" },
  { k: "8", v: "equipment units, each with a datasheet, GA, interlock diagram and plot plan" },
  { k: "211", v: "work orders joined from the maintenance workbook, 31 of them breakdowns" },
  { k: "0", v: "contradictions among extracted trip set points, out of 105 values extracted" },
];

// --- The problem, stated as the plant actually experiences it ---------------

const PROBLEMS = [
  {
    title: "The right document, the wrong revision",
    body: "An engineer finds a set point in a drawing that was superseded two revisions ago. The number is right in the file and wrong for the plant. Nothing in a PDF tells you which revision you are holding.",
  },
  {
    title: "The document that is not there",
    body: "The procedure you need was never written, or lives in a drawer. A chat assistant fills the gap with a plausible sentence, and that sentence is indistinguishable from a real one.",
  },
  {
    title: "Eleven documents per unit",
    body: "Eight units, five baseline document types each, plus one-point lessons written after individual failures. Nobody holds all of it in their head, and the relevant document is rarely the one already open.",
  },
];

// --- The pipeline -----------------------------------------------------------

const PIPELINE = [
  {
    n: "01",
    title: "Ingest once, from the real files",
    body: "87 single-page PDFs, 8 P&ID drawings and the maintenance workbook are parsed into one SQLite index: 95 documents, 362 text chunks, 211 work orders, 105 measured parameter values.",
  },
  {
    n: "02",
    title: "Extract, and record where it came from",
    body: "Trip set points are read from datasheet tables and interlock logic with their operator, value and unit kept intact. Approval status comes from the revision history and signature blocks that are actually present in each document type.",
  },
  {
    n: "03",
    title: "Retrieve, then check whether to answer",
    body: "SQLite FTS5 over the indexed chunks, scoped to the equipment tag in the question where one is named. Before any answer is composed, the question is tested against what the index actually contains.",
  },
  {
    n: "04",
    title: "Score it, badge it, or refuse",
    body: "Five weighted signals produce one number, the number produces TRUSTED, VERIFY or DO NOT EXECUTE, and the sources behind the answer are listed with their document number, revision and approval status.",
  },
];

// --- The four baseline data types ------------------------------------------

const DATA_TYPES = [
  {
    name: "Equipment datasheets",
    detail: "Manufacturer data and physical parameters per unit.",
    note: "Read from PDF tables, not linear text. Reading these files in text order loses the pairing between a label and its value, which is the only thing that makes them usable.",
  },
  {
    name: "Cause & effect / interlock logic",
    detail: "Which condition trips which protective function.",
    note: "The trip set points live here. 31 interlock parameters are extracted as structured values with their operators, not as prose.",
  },
  {
    name: "Operating procedures (GA, OPL, plot plan)",
    detail: "How to do the work, and what was learned after it went wrong.",
    note: "55 one-point lessons carry real signature blocks - reviewed and approved by named people - so a procedure can be traced to the person accountable for it.",
  },
  {
    name: "Maintenance history",
    detail: "Work orders, breakdowns, downtime and cost from the workbook.",
    note: "19 of 31 breakdowns already have a one-point lesson attached to them. The other 12 are the gap, and the system reports them rather than hiding them.",
  },
];

// --- Trust model -----------------------------------------------------------

const WEIGHTS = [
  { name: "Approval", w: "0.30", body: "Is the source an approved, issued revision?" },
  { name: "Revision", w: "0.20", body: "Does it carry a revision and an effective date?" },
  { name: "Agreement", w: "0.20", body: "Do several documents state the same value?" },
  { name: "Relevance", w: "0.20", body: "How well does the retrieved text match the question?" },
  { name: "Coverage", w: "0.10", body: "How much of the answer comes from more than one source?" },
];

// --- Refusals. The part that matters. -------------------------------------

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

// --- Limits, stated on the first screen ------------------------------------

const LIMITS = [
  "The dataset is labelled by its own authors as sample data. Trip set points and costs are stated to be dummy training values; the document structure, revision history and approval records are used as given.",
  "No language model is called by default. Answers are assembled from indexed text and measured values, so nothing is generated and nothing can be hallucinated - but nothing is paraphrased either, and procedural steps are quoted rather than restated.",
  "Zero contradictions means the extracted values agree with each other. It does not mean the plant is safe, and it does not mean every parameter in the documents was extracted.",
  "The dataset is not committed to this repository. It is fetched with one command, because its licence does not permit redistribution.",
];

// --- The nine pages --------------------------------------------------------

const PAGES = [
  { page: "Ask", what: "The product. A question, a badge, the documents behind it, and the arithmetic behind the score." },
  { page: "Equipment", what: "One unit at a time: every document, its full work-order history in date order, and the failures with a linked lesson." },
  { page: "Documents", what: "The register. Document number, revision, effective date, and the approval marker found in the file." },
  { page: "Graph", what: "How the documents join. 8 units, 8 interlock diagrams, 8 datasheets, 8 plot plans, 55 lessons, 31 breakdowns." },
  { page: "Verification", what: "Whether the documents agree. Extraction inventory beside the conflict count, because zero conflicts alone means nothing." },
  { page: "Maintenance", what: "211 work orders and 31 breakdowns, with downtime and cost, and lesson coverage per unit." },
  { page: "Overview", what: "What this instance currently holds, and what it does not claim." },
  { page: "Audit", what: "The weight table printed in full, so any score can be recomputed by hand, plus every question asked." },
  { page: "Dataset", what: "Provenance, the known gaps in the file set, and the LLM policy." },
];

const STACK = [
  "Next.js 15",
  "React 19",
  "TypeScript",
  "Tailwind CSS",
  "FastAPI",
  "SQLite",
  "SQLite FTS5",
  "pdfplumber",
  "openpyxl",
];

function LogoMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="w-full h-full" fill="none" stroke="#3b82f6" strokeWidth={1.6} strokeLinecap="round">
      <path d="M12 12L6 6.5M12 12l6-5.5M12 12l-5.5 6M12 12l5.5 6" opacity={0.55} />
      <circle cx="12" cy="12" r="3.1" fill="#3b82f6" stroke="none" />
      <circle cx="6" cy="6.5" r="1.9" />
      <circle cx="18" cy="6.5" r="1.9" />
      <circle cx="6.5" cy="18" r="1.9" />
      <circle cx="17.5" cy="18" r="1.9" />
    </svg>
  );
}

export default function LandingPage() {
  return (
    <div className="h-full overflow-y-auto bg-[#080d14]">
      {/* ---------- Nav ---------- */}
      <header className="sticky top-0 z-10 border-b border-slate-800/60 bg-[#080d14]/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-4">
          <span className="flex items-center gap-2.5">
            <span className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
              <LogoMark />
            </span>
            <span className="text-sm font-bold text-white tracking-tight">TrustHUB</span>
          </span>
          <nav aria-label="Sections" className="hidden md:flex items-center gap-5 text-xs text-slate-400 ml-4">
            <a href="#problem" className="hover:text-slate-200 transition-colors">Problem</a>
            <a href="#how" className="hover:text-slate-200 transition-colors">How it works</a>
            <a href="#data" className="hover:text-slate-200 transition-colors">Data</a>
            <a href="#trust" className="hover:text-slate-200 transition-colors">Trust</a>
            <a href="#limits" className="hover:text-slate-200 transition-colors">Limits</a>
            <a href="#demo" className="hover:text-slate-200 transition-colors">Demo</a>
          </nav>
          <div className="flex-1" />
          <Link href="/" className="text-xs font-semibold px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            Open the app
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6">
        {/* ---------- Hero ---------- */}
        <section className="py-20 sm:py-28 border-b border-slate-800/60">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-5">
            CALIBER 2026 &middot; Case 1 &middot; Manufacturing Knowledge Hub
          </p>
          <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight leading-[1.1] max-w-3xl">
            An engineering knowledge hub that would rather refuse than guess.
          </h1>
          <p className="mt-6 text-base text-slate-400 max-w-2xl leading-relaxed">
            Datasheets, interlock logic, procedures and maintenance history for
            one unit of an LLDPE plant, in one index. Every answer carries a
            trust badge, the documents behind it, and the reason for its score.
            A question with no supportable source gets a refusal and an
            explanation, not a sentence.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link href="/" className="text-sm font-semibold px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
              Open the app
            </Link>
            <a href="#how" className="text-sm px-5 py-2.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white transition-colors">
              How it works
            </a>
            <a href="#limits" className="text-sm px-5 py-2.5 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white transition-colors">
              What it does not claim
            </a>
          </div>
          <dl className="mt-14 grid grid-cols-2 sm:grid-cols-4 gap-6">
            {FACTS.map((s) => (
              <div key={s.v} className="border-l border-slate-800 pl-4">
                <dt className="text-xl font-bold text-white">{s.k}</dt>
                <dd className="text-xs text-slate-500 mt-1 leading-snug">{s.v}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* ---------- Problem ---------- */}
        <section id="problem" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">The problem</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Not &ldquo;information is hard to find&rdquo;. A plant already has
            the documents. What it does not have is any way to know which of
            them applies, whether it is current, and whether it has been approved.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {PROBLEMS.map((p) => (
              <article key={p.title} className="rounded-xl border border-slate-800/60 bg-[#0d1117] p-5">
                <h3 className="text-sm font-semibold text-white">{p.title}</h3>
                <p className="mt-2 text-xs text-slate-400 leading-relaxed">{p.body}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- How it works ---------- */}
        <section id="how" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">How it works</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Four steps, in this order. The check for whether an answer is
            permitted at all happens before anything is written, not after.
          </p>
          <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map((s) => (
              <li key={s.n} className="rounded-xl border border-slate-800/60 bg-[#0d1117] p-5">
                <span className="text-xs font-mono text-blue-400">{s.n}</span>
                <h3 className="mt-2 text-sm font-semibold text-white">{s.title}</h3>
                <p className="mt-2 text-xs text-slate-400 leading-relaxed">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ---------- Data types ---------- */}
        <section id="data" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">The four baseline data types</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Joined by the key the dataset itself specifies &mdash; the
            equipment tag, which the dataset&rsquo;s own documentation calls the
            join key to all other documents.
          </p>
          <div className="mt-10 grid gap-4 lg:grid-cols-2">
            {DATA_TYPES.map((d) => (
              <article key={d.name} className="rounded-xl border border-slate-800/60 bg-[#0d1117] p-5">
                <h3 className="text-sm font-semibold text-white">{d.name}</h3>
                <p className="mt-1 text-xs text-blue-300">{d.detail}</p>
                <p className="mt-2 text-xs text-slate-500 leading-relaxed">{d.note}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- Trust ---------- */}
        <section id="trust" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">The trust engine</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Five weighted signals, one score, three badges. The weights are
            properties of document provenance, not of a model&rsquo;s confidence,
            because no model is involved in producing them.
          </p>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800/60 bg-[#0d1117] p-5">
              <h3 className="text-sm font-semibold text-white">Weights</h3>
              <div className="mt-4 space-y-2.5">
                {WEIGHTS.map((w) => (
                  <div key={w.name}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs text-slate-300">{w.name}</span>
                      <span className="text-xs font-mono text-slate-500">{w.w}</span>
                    </div>
                    <div className="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden">
                      <div className="h-full bg-blue-500" style={{ width: `${parseFloat(w.w) * 100 / 0.3}%` }} />
                    </div>
                    <p className="mt-1 text-[10px] text-slate-600">{w.body}</p>
                  </div>
                ))}
              </div>
              <div className="mt-5 pt-4 border-t border-slate-800/60 space-y-1.5 text-[11px]">
                <p><span className="text-green-300 font-semibold">TRUSTED</span> at 0.80 &mdash; approved, revisioned, corroborated.</p>
                <p><span className="text-amber-300 font-semibold">VERIFY</span> at 0.50 &mdash; usable after checking the cited document.</p>
                <p><span className="text-red-300 font-semibold">DO NOT EXECUTE</span> below 0.50, or refused outright when no source supports the question.</p>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-[#0d1117] p-5">
              <h3 className="text-sm font-semibold text-white">What it refuses, and why</h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Refusals are the feature, not the failure mode. A hub that
                answers everything is fluent, not trustworthy.
              </p>
              <ul className="mt-4 space-y-3">
                {REFUSALS.map((r) => (
                  <li key={r.q}>
                    <p className="text-xs font-mono text-slate-200 break-words">{r.q}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500 leading-relaxed">{r.why}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---------- Limits ---------- */}
        <section id="limits" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">What this system does not claim</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Listed here rather than in a footer, because a knowledge-hub demo that
            only shows its strengths is asking to be audited for the rest.
          </p>
          <ul className="mt-8 space-y-3 max-w-3xl">
            {LIMITS.map((limit) => (
              <li key={limit} className="flex gap-3 text-sm text-slate-400 leading-relaxed">
                <span className="text-amber-400 shrink-0">&mdash;</span>
                <span>{limit}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* ---------- Demo ---------- */}
        <section id="demo" className="scroll-mt-14 py-20 border-b border-slate-800/60">
          <h2 className="text-2xl font-bold text-white">The demo path</h2>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl">
            Nine pages. A judge can see the whole claim in about four minutes:
            ask a question, check its sources, then check whether those sources
            agree.
          </p>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {PAGES.map((p) => (
              <div key={p.page} className="rounded-xl border border-slate-800/60 p-4">
                <h3 className="text-sm font-semibold text-white font-mono">{p.page}</h3>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">{p.what}</p>
              </div>
            ))}
          </div>
          <div className="mt-10">
            <Link href="/" className="inline-block text-sm font-semibold px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
              Open the app
            </Link>
          </div>
        </section>

        {/* ---------- Stack ---------- */}
        <section className="py-20">
          <h2 className="text-2xl font-bold text-white">Built with</h2>
          <div className="mt-6 flex flex-wrap gap-2">
            {STACK.map((tech) => (
              <span key={tech} className="px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-400 font-mono">
                {tech}
              </span>
            ))}
          </div>
          <p className="mt-8 text-xs text-slate-600 leading-relaxed max-w-2xl">
            Retrieval is SQLite FTS5 rather than a hosted vector database, so the
            whole system runs on one machine with no API key and no external
            service. The dataset is fetched with{" "}
            <code className="font-mono text-slate-500">python -m plant.fetch_dataset</code>{" "}
            and is not committed, because its licence does not permit
            redistribution.
          </p>
        </section>
      </main>

      <footer className="border-t border-slate-800/60">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-start sm:items-center gap-3 justify-between">
          <p className="text-xs text-slate-600">
            CALIBER 2026 &middot; Case 1 &middot; Manufacturing Knowledge Hub &middot; LLDPE unit, Set 01
          </p>
          <Link href="/" className="text-xs font-semibold px-3.5 py-2 rounded-lg border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white transition-colors">
            Open the app
          </Link>
        </div>
      </footer>
    </div>
  );
}