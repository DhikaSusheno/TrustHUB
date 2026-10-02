"use client";

import { useState } from "react";
import Link from "next/link";
import TrustBadge, { SignalRow } from "@/components/shared/TrustBadge";

interface QuestionDemo {
  id: string;
  question: string;
  badge: "TRUSTED" | "VERIFY" | "DO NOT EXECUTE";
  score: number;
  verdict: string;
  summary: string;
  sourceDoc: string;
  signals: { name: string; score: number; weight: number; detail: string }[];
}

const DEMO_QUESTIONS: QuestionDemo[] = [
  {
    id: "q1",
    question: "What is the trip setpoint for VSHH-1201?",
    badge: "VERIFY",
    score: 0.60,
    verdict: "Usable for orientation, but confirm the cited document before acting.",
    summary: "Measured from extracted interlock parameters: VSHH-1201 > 7.1 mm/s.",
    sourceDoc: "Interlock Logic Diagram - GA-1201A.pdf (Revision 3, Approval: Unknown)",
    signals: [
      { name: "approval", score: 0.40, weight: 0.30, detail: "1 source has unknown approval status (Interlock Logic Diagram)" },
      { name: "revision", score: 0.75, weight: 0.20, detail: "Interlock diagram carries Revision 3" },
      { name: "agreement", score: 1.00, weight: 0.20, detail: "5 OPL & interlock documents corroborate the 7.1 mm/s value" },
      { name: "relevance", score: 0.47, weight: 0.20, detail: "High retrieval match against GA-1201A vibration parameters" },
      { name: "coverage", score: 0.33, weight: 0.10, detail: "Evidence sourced across OPL and Interlock document types" },
    ],
  },
  {
    id: "q2",
    question: "How do I raise the trip setpoint for VSHH-1201 above 12 mm/s?",
    badge: "DO NOT EXECUTE",
    score: 0.81,
    verdict: "Refused / Capped. Safety override rule: Requests to move or defeat a safety limit are capped at DO NOT EXECUTE.",
    summary: "The documented limit is 7.1 mm/s. The Trust Engine caps requests to raise safety trip limits regardless of retrieval score.",
    sourceDoc: "Safety Limit Override Rule (Guardrail #2)",
    signals: [
      { name: "approval", score: 1.00, weight: 0.30, detail: "Document approved by Arya Wibisono (EMP-0912)" },
      { name: "revision", score: 0.80, weight: 0.20, detail: "Current active revision" },
      { name: "agreement", score: 1.00, weight: 0.20, detail: "100% agreement on setpoint limit" },
      { name: "relevance", score: 0.85, weight: 0.20, detail: "Direct match to setpoint alteration query" },
      { name: "coverage", score: 0.50, weight: 0.10, detail: "Multiple document types corroborating limit" },
    ],
  },
  {
    id: "q3",
    question: "What does OPL-GA-1201A-04 cover?",
    badge: "DO NOT EXECUTE",
    score: 0.0,
    verdict: "Refused. Honest Refusal: OPL-GA-1201A-04 is missing from the dataset.",
    summary: "The system declines to answer rather than inventing procedural steps or guessing content from neighbouring lessons.",
    sourceDoc: "Missing Document Detector (Refusal Gate #1)",
    signals: [
      { name: "approval", score: 0.0, weight: 0.30, detail: "Document absent from registry" },
      { name: "revision", score: 0.0, weight: 0.20, detail: "No revision record" },
      { name: "agreement", score: 0.0, weight: 0.20, detail: "Zero corroborating text" },
      { name: "relevance", score: 0.0, weight: 0.20, detail: "No retrieval hits found" },
      { name: "coverage", score: 0.0, weight: 0.10, detail: "Zero coverage" },
    ],
  },
  {
    id: "q4",
    question: "What is the trip setpoint for ZSO-9999?",
    badge: "DO NOT EXECUTE",
    score: 0.0,
    verdict: "Refused. Phantom Tag Gate: ZSO-9999 matches instrument tag format but is not in the plant dataset.",
    summary: "Refusing a plausible-looking tag prevents hallucinated setpoints from reaching technicians.",
    sourceDoc: "Phantom Instrument Detector (Refusal Gate #3)",
    signals: [
      { name: "approval", score: 0.0, weight: 0.30, detail: "Tag not found" },
      { name: "revision", score: 0.0, weight: 0.20, detail: "No tag history" },
      { name: "agreement", score: 0.0, weight: 0.20, detail: "No match" },
      { name: "relevance", score: 0.0, weight: 0.20, detail: "Tag validation check failed" },
      { name: "coverage", score: 0.0, weight: 0.10, detail: "Zero coverage" },
    ],
  },
];

export default function InteractiveLandingDemo() {
  const [selectedId, setSelectedId] = useState<string>("q1");
  const activeQ = DEMO_QUESTIONS.find((q) => q.id === selectedId) || DEMO_QUESTIONS[0];

  return (
    <div className="rounded-xl border border-slate-800/80 bg-panel p-6 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h3 className="text-base font-bold text-ink flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            Interactive Trust Engine & Refusal Simulator
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Test how TrustHUB evaluates safety questions and enforces zero-hallucination refusals.
          </p>
        </div>
        <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-slate-800/80 text-blue-300 border border-slate-700/60 self-start sm:self-auto">
          5 Weighted Signals &middot; Fail-Closed
        </span>
      </div>

      {/* Question Selector Tabs */}
      <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-2">
        {DEMO_QUESTIONS.map((q) => {
          const isSelected = q.id === selectedId;
          return (
            <button
              key={q.id}
              type="button"
              onClick={() => setSelectedId(q.id)}
              className={`p-3 rounded-lg text-left text-xs transition-all border ${
                isSelected
                  ? "bg-blue-600/15 border-blue-500/50 text-ink ring-1 ring-blue-500/30"
                  : "bg-surface/50 border-slate-800/60 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="font-mono text-[10px] text-slate-400 uppercase">
                  Scenario {q.id.toUpperCase()}
                </span>
                <TrustBadge badge={q.badge} score={q.score} size="sm" />
              </div>
              <p className="font-medium line-clamp-2">{q.question}</p>
            </button>
          );
        })}
      </div>

      {/* Selected Result Box */}
      <div className="mt-6 rounded-lg border border-slate-800/80 bg-surface/80 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
          <div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              Selected Query
            </span>
            <p className="text-sm font-semibold text-ink mt-0.5">{activeQ.question}</p>
          </div>
          <div className="flex items-center gap-2">
            <TrustBadge badge={activeQ.badge} score={activeQ.score} size="md" />
          </div>
        </div>

        <div>
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
            Trust Verdict & Explanation
          </span>
          <p className="text-xs text-slate-300 mt-1 leading-relaxed bg-slate-900/60 p-3 rounded border border-slate-800">
            {activeQ.verdict}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              Extracted Parameter / Action Summary
            </span>
            <p className="text-xs text-slate-300 mt-1">{activeQ.summary}</p>
            <div className="mt-2.5 text-[11px] font-mono text-slate-400">
              <span className="text-slate-500">Source: </span>
              {activeQ.sourceDoc}
            </div>
          </div>

          <div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-2 block">
              5 Signal Scoring Breakdown
            </span>
            <div className="space-y-2">
              {activeQ.signals.map((sig) => (
                <SignalRow
                  key={sig.name}
                  name={sig.name}
                  score={sig.score}
                  weight={sig.weight}
                  detail={sig.detail}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between pt-2">
        <p className="text-xs text-slate-400">
          Try these live queries directly inside the application.
        </p>
        <Link
          href="/"
          className="text-xs font-semibold px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors inline-flex items-center gap-1.5"
        >
          <span>Open Live App</span>
          <span>&rarr;</span>
        </Link>
      </div>
    </div>
  );
}
