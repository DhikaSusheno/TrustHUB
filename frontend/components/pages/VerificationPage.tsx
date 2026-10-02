// components/pages/VerificationPage.tsx
// Cross-source verification and conflict detection, shown together.
//
// They belong on one page because a conflict count of zero is meaningless in
// isolation. Zero conflicts is what you get from an extractor that found
// nothing, and from one that found 105 values and found them consistent -
// these are the same number and completely different claims. So this page
// always shows the extraction inventory beside the conflict count, and states
// the reasoning explicitly rather than leaving the reader to assume the more
// flattering interpretation.

"use client";

import { usePlantResource } from "@/hooks/usePlantResource";
import {
  plantApi,
  formatSetpoint,
  type Evaluation,
} from "@/lib/plantApi";
import { PageShell, Panel, Stat, Loading, ErrorState, EmptyState, Tag } from "@/components/shared/PageShell";

// The endpoint returns the summary only; the per-case transcript stays in the
// terminal, where `python -m plant.evaluation --verbose` can print it.
export default function VerificationPage() {
  const verification = usePlantResource(plantApi.verification, []);
  const conflicts = usePlantResource(plantApi.conflicts, []);
  const evaluation = usePlantResource(plantApi.evaluation, []);

  const v = verification.data;
  const c = conflicts.data;

  return (
    <PageShell
      title="page.verification.title"
      subtitle="page.verification.subtitle"
    >
      {verification.loading && <Loading label="Comparing documents" />}
      {verification.error !== null && <ErrorState error={verification.error} onRetry={verification.reload} />}

      {v && (
        <div className="p-6 space-y-5">
          {/* Headline. The order is deliberate: contradictions first, because
              that is the number a reviewer will ask for. */}
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <Stat
              label="Contradictions"
              value={v.conflicts_found}
              tone={v.conflicts_found === 0 ? "good" : "bad"}
              sub={v.conflicts_found === 0 ? "no value disagrees" : "routed to SME"}
            />
            <Stat label="Verified groups" value={v.verified_groups} tone="good" sub="stated identically in 7-8 documents" />
            <Stat
              label="Values extracted"
              value={v.inventory.values_extracted}
              sub={`${v.inventory.distinct_parameter_groups} distinct parameters`}
            />
            <Stat
              label="Filters applied"
              value={c?.filters.groups ?? "-"}
              sub="groups eligible for comparison"
            />
          </div>

          {/* The argument, in words, with its own limit stated. */}
          <Panel title="What this measurement does and does not show">
            <div className="space-y-3 text-[11px] text-slate-300 leading-relaxed">
              {v.conflicts_found === 0 ? (
                <p>
                  {v.inventory.values_extracted} measured values were extracted
                  from {v.inventory.values_extracted > 0 ? "the documents" : "no documents"},
                  across {v.inventory.distinct_parameter_groups} parameter groups.
                  Of those, {v.verified_groups} groups are stated with an
                  identical value in 7 or 8 documents, and no group states two
                  different values for the same parameter on the same unit.
                </p>
              ) : (
                <p>
                  {v.conflicts_found} parameter group(s) state different values
                  in different documents. The system does not choose a winner -
                  each conflict is listed with both values and routed to a
                  subject-matter expert.
                </p>
              )}
              <div className="pt-2 border-t border-slate-800/60 text-slate-500">
                <p>
                  <span className="text-slate-400">This does not mean:</span>{" "}
                  the documents are complete, that every parameter was
                  extracted, or that the plant is safe. It means that where two
                  documents state the same measured value, they state the same
                  value.
                </p>
                {c && c.filters.skipped_single_doc > 0 && (
                  <p className="mt-1.5">
                    {c.filters.skipped_operator} groups were skipped for
                    ambiguous operators, {c.filters.skipped_single_doc} for
                    appearing in only one document, and {c.filters.skipped_tolerance}{" "}
                    for falling inside tolerance. They are counted here rather
                    than silently dropped, because a group that cannot be
                    compared cannot be said to agree.
                  </p>
                )}
              </div>
            </div>
          </Panel>

          {/* Where the values came from. The by-source split is what makes
              "105 values" a description of the documents rather than a
              number of rows in a table someone built by hand. */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Extraction inventory" hint="where the values came from">
              <div className="space-y-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    By source
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(v.inventory.by_source).map(([source, count]) => (
                      <Tag key={source}>
                        {source}: {count}
                      </Tag>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    By document type
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(v.inventory.by_doc_type).map(([type, count]) => (
                      <Tag key={type}>
                        {type}: {count}
                      </Tag>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
                    Documents per verified group
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(v.document_count_histogram).map(([docs, count]) => (
                      <Tag key={docs} tone="green">
                        {count} group{count === 1 ? "" : "s"} in {docs} docs
                      </Tag>
                    ))}
                  </div>
                </div>
              </div>
            </Panel>

            {/* Accuracy, executed on this machine against this index. Not a
                constant in the frontend: if the system regresses, this number
                drops in the same place the claim is made. */}
            <Panel title="Accuracy test set" hint="executed live, not hard-coded">
              {evaluation.loading && <Loading label="Running 63 locked cases" />}
              {evaluation.data && (
                <div className="space-y-3">
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-semibold text-ink tabular-nums">
                      {evaluation.data.accuracy_pct.toFixed(1)}%
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {evaluation.data.passed} of {evaluation.data.total} cases
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Stat
                      label="Correct refusals"
                      value={`${evaluation.data.refusal.correct}/${evaluation.data.refusal.expected}`}
                      tone="good"
                      sub="questions with no source"
                    />
                    <Stat
                      label="Correct answers"
                      value={`${evaluation.data.answer.correct}/${evaluation.data.answer.expected}`}
                      sub="answerable questions"
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 leading-relaxed pt-1 border-t border-slate-800/60">
                    Spec v{evaluation.data.spec_version}, run in{" "}
                    {evaluation.data.elapsed_seconds}s. Refusal accuracy is
                    reported separately because a hub that answers everything
                    scores well on accuracy and is useless in a plant.
                  </div>
                </div>
              )}
            </Panel>
          </div>

          {/* The verified values themselves. */}
          <Panel title="Cross-confirmed values" hint={`${v.verified_groups} groups`} flush>
            {v.values.length === 0 ? (
              <EmptyState
                title="No value appears in more than one document"
                hint="With a single-document index there is nothing to cross-confirm. That is the expected result for the synthetic test fixture, not a failure."
              />
            ) : (
              <table className="w-full text-[11px]">
                <thead className="text-slate-400 bg-slate-800/30">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Unit</th>
                    <th className="text-left px-3 py-2 font-medium">Parameter</th>
                    <th className="text-left px-3 py-2 font-medium">Stated value</th>
                    <th className="text-left px-3 py-2 font-medium">Source types</th>
                    <th className="text-right px-3 py-2 font-medium">Documents</th>
                  </tr>
                </thead>
                <tbody>
                  {v.values.map((value, i) => (
                    <tr key={`${value.equipment_tag}-${value.parameter}-${i}`} className="border-t border-slate-800/50">
                      <td className="px-3 py-2 font-mono text-blue-300 whitespace-nowrap">
                        {value.equipment_tag}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-300">
                        {value.parameter}
                      </td>
                      <td className="px-3 py-2 font-mono text-green-300 whitespace-nowrap">
                        {formatSetpoint(value.operator, value.value, value.unit)}
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {value.document_types.join(", ")}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-400">
                        {value.document_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          {/* Conflicts, if any. Rendered even when empty, with the reason. */}
          <Panel
            title="Conflicts"
            hint={c ? `${c.total} found, ${c.needs_sme} need an SME` : undefined}
          >
            {conflicts.loading && <Loading label="Comparing values" />}
            {c && c.total === 0 && (
              <p className="text-[11px] text-slate-400 leading-relaxed">
                No two documents state different values for the same parameter on
                the same unit. Where a conflict were found, both values would be
                listed side by side with no recommendation between them - picking
                the higher set point would be a safety decision, and this system
                does not make safety decisions.
              </p>
            )}
            {c && c.total > 0 && (
              <ul className="space-y-2">
                {c.items.map((item, i) => (
                  <li key={i} className="text-[11px] text-slate-300">
                    {JSON.stringify(item)}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </PageShell>
  );
}
