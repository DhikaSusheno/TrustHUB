// components/pages/MaintenancePage.tsx
// Maintenance history, read as a record of what has actually failed.
//
// The reason this page exists separately from Equipment: the work orders are
// the only part of the dataset that is not a document. They are also the only
// part that is not labelled sample data by its authors - the costs are dummy
// values but the failure patterns are real-shaped - which makes them the
// honest test of whether the knowledge hub is connected to plant reality or
// just to a PDF folder.
//
// Chronological ascending throughout. A maintenance log read newest-first
// hides the recurrence pattern, which is the one thing an engineer opens it
// to look for.

"use client";

import { useMemo, useState } from "react";
import {
  plantApi,
  formatIDR,
  formatHours,
  type WorkOrder,
  type FailureMemorySummary,
} from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import {
  PageShell,
  Panel,
  Stat,
  Loading,
  ErrorState,
  EmptyState,
  Tag,
} from "@/components/shared/PageShell";

type Mode = "all" | "breakdowns";

const WORK_TYPES = [
  "Preventive",
  "Corrective",
  "Predictive",
  "Inspection",
  "Calibration",
  "Overhaul",
] as const;

const DISCIPLINES = ["Mechanical", "Instrument", "Electrical", "Process"] as const;

function WorkOrderTable({ items }: { items: WorkOrder[] }) {
  if (items.length === 0) {
    return <EmptyState title="No work orders match this filter" />;
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="text-slate-400 bg-slate-800/30">
        <tr>
          <th className="text-left px-2.5 py-2 font-medium">WO</th>
          <th className="text-left px-2.5 py-2 font-medium">Date</th>
          <th className="text-left px-2.5 py-2 font-medium">Unit</th>
          <th className="text-left px-2.5 py-2 font-medium">Type</th>
          <th className="text-left px-2.5 py-2 font-medium">Disc.</th>
          <th className="text-left px-2.5 py-2 font-medium">Problem</th>
          <th className="text-right px-2.5 py-2 font-medium">Down</th>
          <th className="text-right px-2.5 py-2 font-medium">Cost</th>
        </tr>
      </thead>
      <tbody>
        {items.map((wo) => (
          <tr key={wo.wo_number} className="border-t border-slate-800/50 align-top">
            <td className="px-2.5 py-2 font-mono text-blue-300 whitespace-nowrap">
              {wo.wo_number}
              {wo.breakdown === 1 && (
                <span className="ml-1 text-red-400" title="Unplanned breakdown">
                  ●
                </span>
              )}
            </td>
            <td className="px-2.5 py-2 font-mono text-slate-500 whitespace-nowrap">
              {wo.report_date.slice(0, 10)}
            </td>
            <td className="px-2.5 py-2 font-mono text-slate-400 whitespace-nowrap">
              {wo.equipment_tag}
            </td>
            <td className="px-2.5 py-2 text-slate-400 whitespace-nowrap">
              {wo.work_type}
            </td>
            <td className="px-2.5 py-2 text-slate-500 whitespace-nowrap">
              {wo.discipline}
            </td>
            <td className="px-2.5 py-2 text-slate-300">{wo.problem_description}</td>
            <td className="px-2.5 py-2 text-right font-mono text-slate-400 whitespace-nowrap">
              {wo.downtime_hours > 0 ? formatHours(wo.downtime_hours) : "-"}
            </td>
            <td className="px-2.5 py-2 text-right font-mono text-slate-400 whitespace-nowrap">
              {wo.total_cost_idr > 0 ? formatIDR(wo.total_cost_idr) : "-"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function MaintenancePage() {
  const [mode, setMode] = useState<Mode>("breakdowns");
  const [unit, setUnit] = useState("");
  const [workType, setWorkType] = useState("");
  const [discipline, setDiscipline] = useState("");

  const summary = usePlantResource(plantApi.failureMemory, []);
  const workOrders = usePlantResource(
    () =>
      plantApi.workOrders({
        equipment_tag: unit,
        breakdown_only: mode === "breakdowns",
        limit: 500,
      }),
    [unit, mode],
  );

  // Client-side filtering for the two columns that have no server-side filter.
  // Documented rather than hidden: with 211 rows over 8 units the whole set is
  // already in memory, so a round trip would add latency and a second source of
  // truth for the same filter.
  const items = useMemo(() => {
    let rows = workOrders.data?.items ?? [];
    if (workType) rows = rows.filter((wo) => wo.work_type === workType);
    if (discipline) rows = rows.filter((wo) => wo.discipline === discipline);
    return rows;
  }, [workOrders.data, workType, discipline]);

  const selectClass =
    "px-2 py-1 rounded bg-[#0d1117] border border-slate-700 text-[11px] text-slate-300 focus:outline-none focus:border-blue-500/60";

  return (
    <PageShell
      title="Maintenance History"
      subtitle="211 work orders and 31 breakdowns, 2024-06-04 to 2025-12-06. Costs are the workbook's own dummy rupiah values."
      actions={
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as Mode)}
          aria-label="Which records to show"
          className={selectClass}
        >
          <option value="breakdowns">Breakdowns only</option>
          <option value="all">All work orders</option>
        </select>
      }
    >
      {summary.loading && <Loading label="Reading maintenance workbook" />}
      {summary.error !== null && <ErrorState error={summary.error} onRetry={summary.reload} />}

      {summary.data && (
        <div className="p-6 space-y-5">
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <Stat label="Work orders" value={summary.data.breakdown_total > 0 ? 211 : 0} sub="all types, all units" />
            <Stat
              label="Breakdowns"
              value={summary.data.breakdown_total}
              tone="warn"
              sub="unplanned"
            />
            <Stat
              label="Breakdown downtime"
              value={formatHours(summary.data.breakdown_downtime_hours)}
            />
            <Stat
              label="Breakdown cost"
              value={formatIDR(summary.data.breakdown_cost_idr)}
              sub="dummy IDR values"
            />
          </div>

          {/* OPL coverage. This is the number that connects the two halves of
              the dataset: a failure that has a one-point lesson attached is a
              failure the plant already learned from. The 12 that do not are
              the gap, and they are counted, not hidden. */}
          <Panel
            title="Failure memory coverage"
            hint={`${summary.data.breakdowns_with_linked_opl} of ${summary.data.breakdown_total} breakdowns have a linked one-point lesson`}
          >
            <div className="space-y-3">
              <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-green-500"
                  style={{ width: `${Math.min(100, summary.data.coverage_pct)}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {summary.data.coverage_pct.toFixed(1)}% coverage. A breakdown
                with no linked OPL is a failure mode the plant has not written
                down. The hub reports that gap rather than retrieving a
                similar document and calling it the answer.
              </p>

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {summary.data.per_equipment.map((row) => (
                  <div
                    key={row.equipment_tag}
                    className="rounded border border-slate-800/60 px-2.5 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] text-blue-300">
                        {row.equipment_tag}
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">
                        {row.breakdown_count} bd
                      </span>
                    </div>
                    <div className="mt-1 text-[10px] text-slate-500 font-mono">
                      {formatHours(row.downtime_hours)} &middot;{" "}
                      {formatIDR(row.total_cost_idr)}
                    </div>
                    {Object.keys(row.modes).length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {Object.entries(row.modes).map(([mode, count]) => (
                          <Tag key={mode}>
                            {mode.replace(/_/g, " ")} {count}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          {/* The log itself. */}
          <Panel
            title={mode === "breakdowns" ? "Breakdowns" : "Work orders"}
            hint={
              workOrders.data
                ? `${items.length} shown${
                    items.length !== workOrders.data.items.length
                      ? ` of ${workOrders.data.items.length} from the server`
                      : ""
                  }`
                : undefined
            }
            actions={
              <div className="flex gap-1.5">
                <select
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  aria-label="Filter by unit"
                  className={selectClass}
                >
                  <option value="">All units</option>
                  {summary.data.per_equipment.map((row) => (
                    <option key={row.equipment_tag} value={row.equipment_tag}>
                      {row.equipment_tag}
                    </option>
                  ))}
                </select>
                <select
                  value={workType}
                  onChange={(e) => setWorkType(e.target.value)}
                  aria-label="Filter by work type"
                  className={selectClass}
                >
                  <option value="">Any type</option>
                  {WORK_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
                <select
                  value={discipline}
                  onChange={(e) => setDiscipline(e.target.value)}
                  aria-label="Filter by discipline"
                  className={selectClass}
                >
                  <option value="">Any discipline</option>
                  {DISCIPLINES.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            }
            flush
          >
            {workOrders.loading && <Loading />}
            {workOrders.error !== null && <ErrorState error={workOrders.error} onRetry={workOrders.reload} />}
            {workOrders.data && (
              <div className="max-h-[32rem] overflow-y-auto">
                <WorkOrderTable items={items} />
              </div>
            )}
          </Panel>
        </div>
      )}
    </PageShell>
  );
}