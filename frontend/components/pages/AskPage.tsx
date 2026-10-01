// components/pages/AskPage.tsx
// The grounded question page. This is the page the whole product is judged on,
// because it is the only place where a number reaches an engineer.
//
// Design rule, and the reason this page exists in this shape: the answer is
// never shown without the evidence that produced it. A refusal is not an error
// state, so it gets the same layout as an answer, a badge, and the reason. An
// engineer who gets a wrong setpoint does not lose the tool; they lose trust
// in it and never come back. An engineer who gets "I will not answer this,
// and here is exactly why" keeps using it.

"use client";

import { useState } from "react";
import { plantApi, type PlantAnswer, type AnswerSource, PlantApiError } from "@/lib/plantApi";
import TrustBadge, { SignalRow } from "@/components/shared/TrustBadge";
import { PageShell, Panel, Tag } from "@/components/shared/PageShell";

/** Questions that each demonstrate a different guardrail, not a random list. */
const EXAMPLES: { label: string; question: string; why: string }[] = [
  {
    label: "Measured setpoint",
    question: "What is the trip setpoint for VSHH-1201?",
    why: "Read from the documents, with the citing documents listed",
  },
  {
    label: "Missing document",
    question: "What does OPL-GA-1201A-04 cover?",
    why: "That one-point lesson is not in the dataset. It must refuse.",
  },
  {
    label: "Unknown equipment",
    question: "What is the shutdown procedure for ZX-9999?",
    why: "No document can be a source. It must refuse.",
  },
  {
    label: "Out of scope",
    question: "How do I open a bank account?",
    why: "Retrieval would return chunks anyway. It must refuse.",
  },
  {
    label: "Maintenance history",
    question: "Which equipment has the most breakdowns?",
    why: "Aggregated from the workbook, not from document text",
  },
  {
    label: "Safety-critical",
    question: "Can I bypass the PSLL-1201 trip to keep the feed running?",
    why: "Safety without a verifiable source is DO NOT EXECUTE",
  },
];

function SourceRow({ source, index }: { source: AnswerSource; index: number }) {
  const approved = source.approval_status === "approved";
  return (
    <li className="px-3 py-2.5 border-b border-slate-800/50 last:border-0">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0 w-5 h-5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono flex items-center justify-center">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-slate-200 leading-snug break-words">
            {source.filename ?? source.title ?? source.doc_id}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {source.equipment_tag && <Tag tone="blue">{source.equipment_tag}</Tag>}
            {source.doc_no && <Tag>{source.doc_no}</Tag>}
            {source.doc_type && <Tag>{source.doc_type}</Tag>}
            {source.revision && <Tag>REV {source.revision}</Tag>}
            <Tag tone={approved ? "green" : "amber"}>
              {source.approval_status ?? "unknown"}
            </Tag>
            {typeof source.relevance === "number" && (
              <span className="text-[10px] font-mono text-slate-600">
                rel {source.relevance.toFixed(2)}
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function AnswerBody({ result }: { result: PlantAnswer }) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-xs font-semibold text-red-300 uppercase tracking-wide">
            Refused &mdash; no source
          </span>
        </div>
        <p className="mt-2.5 text-sm text-slate-200 leading-relaxed">
          {result.refusal_reason}
        </p>
        <p className="mt-3 text-[11px] text-slate-500 leading-relaxed">
          This is a deliberate refusal, not a failure. The system would rather
          return nothing than return something no document supports.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-lg border border-slate-800/60 bg-[#0d1117] p-4">
        {/* The answer text is the only prose the system generates, and it is
            assembled from document text plus measured values, never invented. */}
        <div className="text-sm text-slate-100 leading-relaxed whitespace-pre-line break-words">
          {result.answer}
        </div>
        {result.verbatim && (
          <div className="mt-3 pt-3 border-t border-slate-800/60 text-[11px] text-amber-300/90">
            Quoted from the source documents. Do not paraphrase before working
            to these steps.
          </div>
        )}
      </div>

      {result.warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {result.warnings.map((warning, i) => (
            <div
              key={i}
              className="text-[11px] text-amber-200/90 bg-amber-500/5 border border-amber-500/20 rounded px-3 py-2"
            >
              {warning}
            </div>
          ))}
        </div>
      )}

      {result.sources.length > 0 && (
        <div className="mt-4 rounded-lg border border-slate-800/60 overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-800/60 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wide text-slate-500">
              Sources
            </span>
            <span className="text-[10px] text-slate-600 font-mono">
              {result.sources.length} document{result.sources.length === 1 ? "" : "s"}
            </span>
          </div>
          <ul>
            {result.sources.map((source, index) => (
              <SourceRow key={`${source.doc_id ?? "src"}-${index}`} source={source} index={index} />
            ))}
          </ul>
        </div>
      )}
    </>
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
      title="Ask the Knowledge Hub"
      subtitle="Every answer carries a trust badge, the documents behind it, and the reason for its score. Questions with no support are refused."
    >
      <div className="p-6 max-w-5xl">
        {/* Input */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="flex gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the trip setpoint for VSHH-1201?"
            aria-label="Question"
            className="flex-1 px-3.5 py-2.5 rounded-lg bg-[#0d1117] border border-slate-700 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/60 transition-colors"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 2}
            className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-sm font-medium text-white transition-colors shrink-0"
          >
            {busy ? "Asking" : "Ask"}
          </button>
        </form>

        {error && (
          <div className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">
            {error}
          </div>
        )}

        {/* Answer */}
        {result && (
          <div className="mt-5">
            <div className="flex items-center gap-3 mb-3 flex-wrap">
              <TrustBadge badge={result.badge} score={result.trust_score} size="md" />
              <span className="text-[11px] text-slate-500 font-mono">
                kind: {result.kind}
              </span>
              {result.equipment_tag && <Tag tone="blue">{result.equipment_tag}</Tag>}
              {result.cross_unit && <Tag>cross-unit</Tag>}
              <span className="text-[11px] text-slate-600 font-mono">
                llm: {result.llm_mode}
              </span>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
              <div className="min-w-0">
                <AnswerBody result={result} />
              </div>

              {/* Why this score. The question an engineer actually asks is
                  "why do you say that?", and hiding the arithmetic makes the
                  badge decorative. */}
              {result.signals.length > 0 && (
                <Panel title="Why this score" className="h-fit">
                  <div className="space-y-3">
                    {result.signals.map((signal) => (
                      <SignalRow key={signal.name} {...signal} />
                    ))}
                  </div>
                  {result.reasons.length > 0 && (
                    <ul className="mt-4 pt-3 border-t border-slate-800/60 space-y-1.5">
                      {result.reasons.map((reason, i) => (
                        <li key={i} className="text-[11px] text-slate-400 leading-relaxed">
                          {reason}
                        </li>
                      ))}
                    </ul>
                  )}
                </Panel>
              )}
            </div>
          </div>
        )}

        {/* Examples, shown before the first answer and collapsible after */}
        {!result && (
          <div className="mt-8">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
              Try one of these
            </h2>
            <p className="mt-1 text-[11px] text-slate-600">
              Each one exercises a different guardrail. The refusals matter as
              much as the answers.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  onClick={() => void submit(example.question)}
                  disabled={busy}
                  className="text-left rounded-lg border border-slate-800/60 bg-[#0f141b] px-3.5 py-3 hover:border-blue-500/40 hover:bg-[#131a24] disabled:opacity-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-200">
                      {example.label}
                    </span>
                  </div>
                  <div className="mt-1 text-[11px] font-mono text-slate-400 break-words">
                    {example.question}
                  </div>
                  <div className="mt-1.5 text-[11px] text-slate-600 leading-snug">
                    {example.why}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {result && (
          <button
            onClick={() => {
              setResult(null);
              setQuestion("");
            }}
            className="mt-6 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
          >
            Clear and pick another question
          </button>
        )}
      </div>
    </PageShell>
  );
}
