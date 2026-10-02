// components/pages/AskPage.tsx
// The grounded question page. This is the page the whole product is judged on,
// because it is the only place where a number reaches an engineer.
//
// Design rule: the answer is never shown without the evidence that produced it.
// Refusal is a deliberate safety feature, not an error state.

"use client";

import { useState } from "react";
import { plantApi, type PlantAnswer, type AnswerSource, PlantApiError } from "@/lib/plantApi";
import TrustBadge, { SignalRow } from "@/components/shared/TrustBadge";
import { PageShell, Panel, Tag } from "@/components/shared/PageShell";

/** Questions that each demonstrate a different guardrail, not a random list. */
const EXAMPLES: { category: string; label: string; question: string; why: string; tone: "blue" | "green" | "amber" | "slate" }[] = [
  {
    category: "Verified Setpoint",
    label: "Measured setpoint",
    question: "What is the trip setpoint for VSHH-1201?",
    why: "Read from verified datasheet tables with full citation provenance",
    tone: "green",
  },
  {
    category: "Safety Guardrail",
    label: "Missing document",
    question: "What does OPL-GA-1201A-04 cover?",
    why: "That one-point lesson is not in the dataset. System refuses rather than guessing.",
    tone: "amber",
  },
  {
    category: "Tag Validation",
    label: "Unknown equipment",
    question: "What is the shutdown procedure for ZX-9999?",
    why: "No document mentions unit ZX-9999. Strict tag checking blocks hallucination.",
    tone: "slate",
  },
  {
    category: "Scope Gate",
    label: "Out of domain",
    question: "How do I open a bank account?",
    why: "Domain vocabulary gate stops non-plant questions before document retrieval.",
    tone: "slate",
  },
  {
    category: "Workbook Analytics",
    label: "Maintenance history",
    question: "Which equipment has the most breakdowns?",
    why: "Aggregated live from the maintenance workbook, not from narrative text.",
    tone: "blue",
  },
  {
    category: "Interlock Logic",
    label: "Safety-critical bypass",
    question: "Can I bypass the PSLL-1201 trip to keep the feed running?",
    why: "Safety procedures without explicit authorization yield DO NOT EXECUTE.",
    tone: "amber",
  },
];

function SourceCard({ source, index }: { source: AnswerSource; index: number }) {
  const approved = source.approval_status === "approved";
  return (
    <div className="rounded-xl border border-slate-800/80 bg-panel-2/70 p-4 transition-all hover:border-slate-700/80">
      <div className="flex items-start gap-3">
        <span className="shrink-0 w-6 h-6 rounded-md bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-mono font-bold flex items-center justify-center">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-slate-100 leading-snug break-words">
            {source.filename ?? source.title ?? source.doc_id}
          </div>
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {source.equipment_tag && <Tag tone="blue">{source.equipment_tag}</Tag>}
            {source.doc_no && <Tag>{source.doc_no}</Tag>}
            {source.doc_type && <Tag>{source.doc_type}</Tag>}
            {source.revision && <Tag>REV {source.revision}</Tag>}
            <Tag tone={approved ? "green" : "amber"}>
              {source.approval_status ?? "unknown"}
            </Tag>
            {typeof source.relevance === "number" && (
              <span className="text-[11px] font-mono text-slate-400 ml-1">
                rel {source.relevance.toFixed(2)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AnswerBody({ result }: { result: PlantAnswer }) {
  if (result.refused) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400 animate-pulse" />
          <span className="text-xs font-bold text-red-300 uppercase tracking-wider">
            Refused: No verified source found
          </span>
        </div>
        <p className="mt-3 text-base text-slate-100 leading-relaxed font-medium">
          {result.refusal_reason}
        </p>
        <div className="mt-4 pt-3 border-t border-red-500/20 text-xs text-slate-300 leading-relaxed">
          <strong>Deliberate Safety Refusal:</strong> TrustHUB chooses silence over speculation.
          No unverified or missing plant parameter will ever be hallucinated.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Primary Answer Box */}
      <div className="rounded-xl border border-slate-700/80 bg-panel-2/90 p-5 shadow-sm">
        <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
          Verified Plant Response
        </div>
        <div className="text-base text-slate-100 leading-relaxed whitespace-pre-line break-words font-medium">
          {result.answer}
        </div>
        {result.verbatim && (
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-xs text-amber-300/90 font-medium">
            <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
            <span>Verbatim quote directly from source documents. Do not alter or paraphrase operational steps.</span>
          </div>
        )}
      </div>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="space-y-2">
          {result.warnings.map((warning, i) => (
            <div
              key={i}
              className="text-xs text-amber-200/90 bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3 leading-relaxed font-medium flex items-start gap-2.5"
            >
              <span className="w-2 h-2 rounded-full bg-amber-400 mt-1 shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      {/* Sources Grid */}
      {result.sources.length > 0 && (
        <div className="mt-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Cited Engineering Documents
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              {result.sources.length} document{result.sources.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-1">
            {result.sources.map((source, index) => (
              <SourceCard key={`${source.doc_id ?? "src"}-${index}`} source={source} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<PlantAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(text?: string) {
    const q = (text ?? question).trim();
    if (q.length < 2) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await plantApi.ask(q));
      setQuestion(q);
    } catch (err) {
      setResult(null);
      setError(
        err instanceof PlantApiError ? err.detail : "Could not reach the backend",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell
      title="Ask TrustHUB"
      subtitle="Engineering Q&A grounded strictly in official LLDPE unit documents with verifiable trust scoring"
    >
      <div className="p-4 sm:p-8 max-w-5xl mx-auto space-y-6">

        {/* Search Input Box */}
        <div className="rounded-2xl border border-slate-700/80 bg-panel/90 p-4 sm:p-5 shadow-sm backdrop-blur-sm">
          <label htmlFor="ask-question" className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
            Ask any plant parameter, setpoint, or procedure
          </label>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
            className="flex flex-col sm:flex-row gap-2.5"
          >
            <div className="relative flex-1">
              <input
                id="ask-question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. What is the trip setpoint for VSHH-1201?"
                className="w-full px-4 py-3 rounded-xl bg-panel-2 border border-slate-700 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500/80 focus:ring-1 focus:ring-blue-500/50 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={busy || question.trim().length < 2}
              className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-sm font-semibold text-white transition-all shrink-0 flex items-center justify-center gap-2 shadow-sm"
            >
              {busy ? (
                <>
                  <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <span>Ask Question</span>
              )}
            </button>
          </form>

          {error && (
            <div className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Answer Display */}
        {result && (
          <div className="space-y-4">
            {/* Top metadata badge row */}
            <div className="flex items-center justify-between flex-wrap gap-3 bg-panel-2/60 border border-slate-800/80 rounded-xl p-3">
              <div className="flex items-center gap-2.5 flex-wrap">
                <TrustBadge badge={result.badge} score={result.trust_score} size="md" />
                {result.equipment_tag && <Tag tone="blue">{result.equipment_tag}</Tag>}
                {result.cross_unit && <Tag>Cross-Unit</Tag>}
              </div>
              <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
                <span>Kind: <strong className="text-slate-200">{result.kind}</strong></span>
                <span>Mode: <strong className="text-slate-200">{result.llm_mode}</strong></span>
                <button
                  onClick={() => {
                    setResult(null);
                    setQuestion("");
                  }}
                  className="px-2.5 py-1 rounded-md text-xs font-sans text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
              <div className="min-w-0">
                <AnswerBody result={result} />
              </div>

              {/* Trust Score Breakdown Panel */}
              {result.signals.length > 0 && (
                <Panel title="Trust Breakdown" className="h-fit">
                  <div className="space-y-3.5">
                    {result.signals.map((signal) => (
                      <SignalRow key={signal.name} {...signal} />
                    ))}
                  </div>
                  {result.reasons.length > 0 && (
                    <div className="mt-5 pt-4 border-t border-slate-800/80">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-2">
                        Evaluation Notes
                      </div>
                      <ul className="space-y-2">
                        {result.reasons.map((reason, i) => (
                          <li key={i} className="text-xs text-slate-300 leading-relaxed flex items-start gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                            <span>{reason}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Panel>
              )}
            </div>
          </div>
        )}

        {/* Preset Prompt Showcase Cards */}
        {!result && (
          <div className="space-y-3">
            <div>
              <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Preset Test Scenarios (Guardrail Validation)
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Click any scenario to see how TrustHUB retrieves or deliberately refuses unverified queries.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  onClick={() => void submit(example.question)}
                  disabled={busy}
                  className="group text-left rounded-xl border border-slate-800/80 bg-panel-2/80 p-4 hover:border-blue-500/50 hover:bg-panel-2 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Tag tone={example.tone}>{example.category}</Tag>
                    </div>
                    <div className="text-xs font-mono font-medium text-slate-200 group-hover:text-blue-300 transition-colors break-words">
                      {example.question}
                    </div>
                  </div>
                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 text-[11px] text-slate-400 leading-snug">
                    {example.why}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

      </div>
    </PageShell>
  );
}
