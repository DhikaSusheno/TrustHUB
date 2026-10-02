// components/pages/AuditPage.tsx
// The answer audit trail, and why the trust score is what it is.
//
// Two things share this page because they answer the same question from
// different directions. "Why did it answer that?" is answered by the weight
// table and thresholds, which are printed here rather than buried. "What has
// it said so far?" is answered by the log, which is the only record in the
// system of what was actually asked.
//
// The log matters for a reason beyond QA. A knowledge hub that gets an answer
// wrong has no way to know unless someone reports it; an audit trail of every
// question, its badge, and its sources means the failure is discoverable by
// reading the log instead of by trusting the user.

"use client";

import { Fragment, useState } from "react";
import {
  plantApi,
  sourceList,
  formatIDR,
  type AuditLog as AuditLogShape,
  type Badge,
} from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import { PageShell, Panel, Stat, Loading, ErrorState, EmptyState } from "@/components/shared/PageShell";
import TrustBadge from "@/components/shared/TrustBadge";

const WEIGHT_NOTES: Record<string, string> = {
  approval: "Is the source an approved, issued revision?",
  revision: "Does it carry a revision and an effective date?",
  agreement: "Do several documents state the same value?",
  relevance: "How well does the retrieved text match the question?",
  coverage: "How much of the answer comes from more than one source?",
};

function BadgeCounts({ log }: { log: AuditLogShape }) {
  const total = log.total || 1;
  return (
    <div className="space-y-2">
      {(["TRUSTED", "VERIFY", "DO NOT EXECUTE"] as Badge[]).map((badge) => {
        const count = log.by_badge[badge] ?? 0;
        const pct = Math.round((count / total) * 100);
        const tone =
          badge === "TRUSTED"
            ? "bg-green-500"
            : badge === "VERIFY"
              ? "bg-amber-500"
              : "bg-red-500";
        return (
          <div key={badge} className="flex items-center gap-2 text-[11px]">
            <span className="w-28 text-slate-400">{badge}</span>
            <div className="flex-1 h-1 rounded-full bg-slate-800 overflow-hidden">
              <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="font-mono text-slate-500 w-12 text-right">
              {count} · {pct}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function AuditPage() {
  const weights = usePlantResource(plantApi.trustWeights, []);
  const log = usePlantResource(() => plantApi.audit(100), []);
  const [expanded, setExpanded] = useState<number | null>(null);

  const weightTotal = weights.data
    ? Object.values(weights.data.weights).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <PageShell
      title="page.audit.title"
      subtitle="page.audit.subtitle"
    >
      <div className="p-6 space-y-5">
        {/* The weight table, printed in full. A reader should be able to
            recompute any score by hand from what is on this page. */}
        <Panel title="Trust model" hint="weights sum to 1.00 by construction">
          {weights.loading && <Loading label="Reading weights" />}
          {weights.data && (
            <div className="space-y-4">
              <div className="grid gap-2 md:grid-cols-2">
                {Object.entries(weights.data.weights).map(([name, weight]) => (
                  <div key={name} className="flex items-start gap-2.5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[11px] text-slate-300 capitalize">
                          {name}
                        </span>
                        <span className="font-mono text-[11px] text-slate-500">
                          {(weight / weightTotal).toFixed(2)}
                        </span>
                      </div>
                      <div className="mt-1 h-1 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-blue-500"
                          style={{ width: `${(weight / weightTotal) * 100}%` }}
                        />
                      </div>
                      <p className="mt-1 text-[10px] text-slate-600 leading-snug">
                        {WEIGHT_NOTES[name] ?? ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-slate-800/60">
                <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-2">
                  Approval scores
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(weights.data.approval_scores).map(([status, score]) => (
                    <span
                      key={status}
                      className="px-2 py-1 rounded bg-slate-800/60 border border-slate-700 text-[10px] font-mono text-slate-300"
                    >
                      {status}: {score.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800/60 grid gap-2 sm:grid-cols-3">
                <div className="text-[11px]">
                  <span className="text-green-300 font-semibold">
                    TRUSTED at {weights.data.thresholds.trusted.toFixed(2)}
                  </span>
                  <p className="text-slate-600 mt-0.5 leading-snug">
                    Approved, revisioned, corroborated.
                  </p>
                </div>
                <div className="text-[11px]">
                  <span className="text-amber-300 font-semibold">
                    VERIFY at {weights.data.thresholds.verify.toFixed(2)}
                  </span>
                  <p className="text-slate-600 mt-0.5 leading-snug">
                    Usable after checking the cited document.
                  </p>
                </div>
                <div className="text-[11px]">
                  <span className="text-red-300 font-semibold">
                    Refuse below {weights.data.thresholds.relevance_floor.toFixed(2)}{" "}
                    retrieval
                  </span>
                  <p className="text-slate-600 mt-0.5 leading-snug">
                    Below this relevance floor the system declines rather than
                    answering weakly.
                  </p>
                </div>
              </div>
            </div>
          )}
        </Panel>

        {/* The log. */}
        <Panel
          title="Answer audit trail"
          hint={
            log.data
              ? `${log.data.total} questions, ${log.data.refused} refused`
              : undefined
          }
        >
          {log.loading && <Loading label="Reading audit log" />}
          {log.error !== null && <ErrorState error={log.error} onRetry={log.reload} />}

          {log.data && (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="Questions asked" value={log.data.total} />
                <Stat
                  label="Refused"
                  value={log.data.refused}
                  tone={log.data.refused > 0 ? "good" : "default"}
                  sub="no trustworthy source"
                />
                {/* Badges issued is the same kind of entry as the two counts beside it, so it
                  gets the same ruled treatment instead of a box. A hand-rolled
                  copy of Stat here used to put a bordered panel in the third
                  cell of a grid whose other two cells had no border at all. */}
                <div className="border-t border-slate-800/70 pt-2.5">
                  <div className="text-[10px] uppercase tracking-wide text-slate-400 mb-2">
                    Badges issued
                  </div>
                  <BadgeCounts log={log.data} />
                </div>
              </div>

              {log.data.items.length === 0 ? (
                <EmptyState
                  title="Nothing asked yet"
                  hint="Every question submitted on the Ask page is recorded here with its badge and sources."
                />
              ) : (
                <div className="rounded border border-slate-800/60 overflow-x-auto overflow-y-hidden">
                  <table className="w-full min-w-[640px] text-[11px]">
                    <thead className="text-slate-400 bg-slate-800/30">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Asked</th>
                        <th className="text-left px-3 py-2 font-medium">Question</th>
                        <th className="text-left px-3 py-2 font-medium">Unit</th>
                        <th className="text-left px-3 py-2 font-medium">Badge</th>
                        <th className="text-right px-3 py-2 font-medium">Sources</th>
                      </tr>
                    </thead>
                    <tbody>
                      {log.data.items.map((entry) => {
                        const sources = sourceList(entry);
                        const open = expanded === entry.id;
                        return (
                          // Key harus di fragment, bukan di <tr> di dalam.
                          // Element larik yang dikembalikan `.map` adalah
                          // fragment-nya, jadi React tidak pernah melihat key
                          // tersebut - ia memperingatkan "each child should
                          // have a unique key" dan meng identitasikan baris
                          // secara posisional. Saat baris detail dibuka atau
                          // ditutup, identitas posisional ikut bergeser.
                          <Fragment key={entry.id}>
                            <tr
                              onClick={() => setExpanded(open ? null : entry.id)}
                              className="border-t border-slate-800/50 cursor-pointer hover:bg-slate-800/30"
                            >
                              <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap">
                                {entry.asked_at.slice(0, 16).replace("T", " ")}
                              </td>
                              <td className="px-3 py-2 text-slate-200">
                                {entry.question}
                              </td>
                              <td className="px-3 py-2 font-mono text-slate-400 whitespace-nowrap">
                                {entry.equipment_tag ?? "-"}
                              </td>
                              <td className="px-3 py-2">
                                <TrustBadge badge={entry.badge} score={entry.trust_score} />
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-slate-500">
                                {sources.length}
                              </td>
                            </tr>
                            {open && (
                              <tr className="bg-inset">
                                <td colSpan={5} className="px-3 py-2">
                                  {sources.length === 0 ? (
                                    <p className="text-[11px] text-slate-500">
                                      No sources. This entry was a refusal, and
                                      the reason it was refused is on the Ask
                                      page where it was returned.
                                    </p>
                                  ) : (
                                    <ul className="space-y-0.5">
                                      {sources.map((source, i) => (
                                        <li
                                          key={`${i}-${source}`}
                                          className="text-[11px] font-mono text-slate-400 break-words"
                                        >
                                          {source}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <p className="text-[11px] text-slate-600 leading-relaxed">
                Questions asked at runtime are stored in the local index, not
                sent anywhere. No LLM is called in the default configuration, so
                there is no external service that could see them.
              </p>
            </div>
          )}
        </Panel>
      </div>
    </PageShell>
  );
}