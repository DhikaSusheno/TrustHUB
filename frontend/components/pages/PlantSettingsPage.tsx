// components/pages/PlantSettingsPage.tsx
// Dataset provenance, index state, and the LLM policy.
//
// Three jobs, and the page is arranged in that order because it is a
// credibility page, not a preference page.
//
//  1. Where the data came from. The dataset is a committee-licensed download
//     and is deliberately NOT in the repository, so the licence note and the
//     fetch command are the two things a reviewer needs in order to reproduce
//     the demo. Both are printed verbatim.
//  2. What the index actually contains, including its gaps. The missing
//     one-point lesson is listed here rather than hidden, because a demo that
//     quietly omits an incomplete part of the dataset invites the question
//     "what else is missing?".
//  3. The LLM policy. Off by default, and it says why: the committee has not
//     confirmed whether the dataset may leave the machine, so the system
//     assumes it may not. That is why every answer in the demo is composed from
//     indexed text rather than generated, and why the trust scores are computed
//     from document metadata rather than from a model's confidence.

"use client";

import { useState } from "react";
import { plantApi, formatIDR, formatHours } from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import { PageShell, Panel, Stat, Loading, ErrorState, Tag } from "@/components/shared/PageShell";

/** Shown when reindex is pressed. The backend reads the PDFs again and
 *  rebuilds the index, so this is slow and its result is worth showing. */
function ReindexButton() {
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function run() {
    setState("running");
    setMessage(null);
    try {
      const result = await plantApi.reindex();
      const ingested = result.ingested ?? {};
      const parts = Object.entries(ingested)
        .map(([key, value]) => `${key} ${value}`)
        .join(", ");
      setMessage(parts || "Index rebuilt.");
      setState("done");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
      setState("error");
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={run}
        disabled={state === "running"}
        className="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-slate-200 border border-slate-700 text-[11px] transition-colors"
      >
        {state === "running" ? "Rebuilding index" : "Rebuild index"}
      </button>
      {message && (
        <p
          className={`text-[11px] leading-relaxed ${
            state === "error" ? "text-red-300" : "text-slate-500"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}

export default function PlantSettingsPage() {
  const status = usePlantResource(plantApi.status, []);
  const dataset = usePlantResource(plantApi.dataset, []);

  const s = status.data;
  const d = dataset.data;
  const llmExternal = s?.llm.mode === "external";

  return (
    <PageShell
      title="page.dataset.title"
      subtitle="page.dataset.subtitle"
    >
      {status.loading && <Loading label="Reading configuration" />}
      {status.error !== null && <ErrorState error={status.error} onRetry={status.reload} />}

      {s && (
        <div className="p-6 space-y-5">
          {/* Index health. A missing index is shown as a state with the exact
              command to fix it, not as an empty dashboard. */}
          <Panel
            title="Index status"
            actions={
              <span className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${s.ready ? "bg-green-400" : "bg-amber-400"}`}
                />
                <span className={`text-[11px] ${s.ready ? "text-green-300" : "text-amber-300"}`}>
                  {s.ready ? "ready" : "not built"}
                </span>
              </span>
            }
          >
            {s.ready ? (
              <div className="space-y-3">
                <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
                  <Stat label="Documents" value={s.counts.documents} />
                  <Stat label="Chunks" value={s.counts.chunks} />
                  <Stat label="Equipment" value={s.counts.equipment} />
                  <Stat label="Work orders" value={s.counts.work_orders} />
                  <Stat
                    label="Approved"
                    value={s.counts.approved_documents}
                    tone="good"
                    sub={`of ${s.counts.documents} documents`}
                  />
                  <Stat
                    label="Measured parameters"
                    value={s.counts.measured_parameters}
                    sub="linear and table values"
                  />
                  <Stat label="Failure links" value={s.counts.failure_links} />
                  <Stat
                    label="Unverified approval"
                    value={(s.counts.documents ?? 0) - (s.counts.approved_documents ?? 0)}
                    tone="warn"
                    sub="no approval marker"
                  />
                </div>
                <p className="text-[10px] text-slate-600 font-mono break-all">
                  {s.database}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-[11px] text-amber-200 leading-relaxed">
                  {s.problem}
                </p>
                <pre className="text-[11px] font-mono text-slate-300 bg-[#0a0e14] border border-slate-800 rounded px-3 py-2 overflow-x-auto">
                  python -m plant.fetch_dataset
                </pre>
              </div>
            )}
          </Panel>

          {/* LLM policy. The most important panel on the page. */}
          <Panel
            title="LLM policy"
            hint={
              <span className={llmExternal ? "text-amber-400" : "text-slate-600"}>
                mode: {s.llm.mode}
              </span>
            }
          >
            <div className="space-y-3">
              <p className="text-[11px] text-slate-300 leading-relaxed">
                {s.llm.note}
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                {(["off", "local", "external"] as const).map((mode) => (
                  <div
                    key={mode}
                    className={`rounded border px-2.5 py-2 ${
                      s.llm.mode === mode
                        ? "border-blue-500/40 bg-blue-500/10"
                        : "border-slate-800"
                    }`}
                  >
                    <div className="text-[11px] font-mono text-slate-200">{mode}</div>
                    <div className="mt-0.5 text-[10px] text-slate-600 leading-snug">
                      {mode === "off" && "No model is called. Default."}
                      {mode === "local" && "Only a provider on localhost."}
                      {mode === "external" && "Any provider. Needs a second opt-in."}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed pt-1 border-t border-slate-800/60">
                Consequences of the default, stated plainly: answers are
                assembled from indexed text and measured values, so nothing is
                generated and nothing can be hallucinated &mdash; but nothing is
                paraphrased either, and procedural steps are quoted rather than
                restated. That is a deliberate trade. A paraphrase of an
                isolation procedure is a safety defect, and a system that can
                generate prose can eventually generate a wrong step.
              </p>
            </div>
          </Panel>

          {/* Provenance. */}
          <Panel title="Dataset provenance" hint="not committed to the repository">
            {dataset.loading && <Loading label="Reading dataset" />}
            {d && (
              <div className="space-y-4">
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  {s.dataset_licence_note}
                </p>
                <p className="text-[10px] text-slate-600 font-mono break-all">
                  {d.root}
                </p>

                <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
                  <Stat label="PDFs" value={d.pdf_count} />
                  <Stat label="P&ID drawings" value={d.png_count} />
                  <Stat label="One-point lessons" value={d.by_doc_type.opl ?? 0} />
                  <Stat
                    label="Date range"
                    value={`${d.date_range[0]?.slice(0, 10) ?? "?"} → ${
                      d.date_range[1]?.slice(0, 10) ?? "?"
                    }`}
                  />
                </div>

                <div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    Documents by type
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(d.by_doc_type).map(([type, count]) => (
                      <Tag key={type} tone={type === "opl" ? "slate" : "blue"}>
                        {type}: {count}
                      </Tag>
                    ))}
                  </div>
                </div>

                {/* The gaps. Printed because a demo that hides an incomplete
                    dataset is asking to be audited for it. */}
                <div className="pt-3 border-t border-slate-800/60">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    Known gaps in the dataset
                  </div>
                  {d.problems.length === 0 ? (
                    <p className="text-[11px] text-slate-500">
                      No structural gaps detected.
                    </p>
                  ) : (
                    <ul className="space-y-1.5">
                      {d.problems.map((problem, i) => (
                        <li
                          key={i}
                          className="text-[11px] text-amber-200/90 leading-relaxed"
                        >
                          {problem}
                        </li>
                      ))}
                      {Object.entries(d.missing_opl).map(([tag, numbers]) => (
                        <li
                          key={tag}
                          className="text-[11px] text-slate-400 leading-relaxed"
                        >
                          {tag} is missing one-point lesson
                          {numbers.length > 1 ? "s " : " "}
                          {numbers.map((n) => `${n}`).join(", ")}. Questions
                          about {numbers.map((n) => `OPL-${tag}-0${n}`).join(", ")}{" "}
                          are refused rather than answered from a similar
                          document.
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-800/60">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    Maintenance workbook totals
                  </div>
                  <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
                    <Stat label="Work orders" value={d.wo_total} />
                    <Stat label="Breakdowns" value={d.breakdown_total} tone="warn" />
                    <Stat label="Downtime" value={formatHours(d.downtime_hours)} />
                    <Stat
                      label="Breakdown cost"
                      value={formatIDR(d.breakdown_cost_idr)}
                      sub={`of ${formatIDR(d.total_cost_idr)} total`}
                    />
                  </div>
                  <p className="mt-2 text-[10px] text-slate-600 leading-relaxed">
                    Costs are the workbook authors&rsquo; stated dummy rupiah
                    values. They are shown to prove the join between documents
                    and maintenance data is real, not to make a financial
                    claim.
                  </p>
                </div>
              </div>
            )}
          </Panel>

          {/* Index maintenance. */}
          <Panel title="Index maintenance">
            <div className="space-y-2">
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Rebuilding re-reads every PDF and workbook from the dataset root
                and rewrites the index. It takes a few seconds and replaces the
                current index, so the audit trail above is cleared.
              </p>
              <ReindexButton />
            </div>
          </Panel>
        </div>
      )}
    </PageShell>
  );
}