// components/pages/EquipmentPage.tsx
// Equipment list with an inline detail panel.
//
// The detail is documents, work orders, and failure memory for one unit, in
// that order, because that is the order an engineer works in: "what does the
// documentation say, has this thing broken, and do we have a procedure for the
// failure mode we actually hit."

"use client";

import { useState } from "react";
import {
  plantApi,
  formatIDR,
  formatHours,
  type Equipment,
  type PlantDocument,
  type WorkOrder,
  type FailureRecord,
} from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import { PageShell, Panel, Loading, ErrorState, EmptyState, Stat, Tag } from "@/components/shared/PageShell";

function DocumentTable({ documents }: { documents: PlantDocument[] }) {
  if (documents.length === 0) {
    return <EmptyState title="No documents for this unit" />;
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="text-slate-400">
        <tr>
          <th className="text-left px-2.5 py-1.5 font-medium">Document</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Type</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Doc no.</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Rev</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Approval</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.doc_id} className="border-t border-slate-800/50 align-top">
            <td className="px-2.5 py-1.5 text-slate-200">
              <div className="break-words">{doc.filename}</div>
              {doc.effective_date && (
                <div className="mt-0.5 font-mono text-[10px] text-slate-600">
                  effective {doc.effective_date}
                </div>
              )}
            </td>
            <td className="px-2.5 py-1.5 text-slate-400">{doc.doc_type}</td>
            <td className="px-2.5 py-1.5 font-mono text-slate-400">{doc.doc_no ?? "-"}</td>
            <td className="px-2.5 py-1.5 font-mono text-slate-400">{doc.revision ?? "-"}</td>
            <td className="px-2.5 py-1.5">
              <Tag tone={doc.approval_status === "approved" ? "green" : "amber"}>
                {doc.approval_status}
              </Tag>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function WorkOrderTable({ workOrders }: { workOrders: WorkOrder[] }) {
  if (workOrders.length === 0) {
    return <EmptyState title="No work orders recorded for this unit" />;
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="text-slate-400">
        <tr>
          <th className="text-left px-2.5 py-1.5 font-medium">WO</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Date</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Type</th>
          <th className="text-left px-2.5 py-1.5 font-medium">Problem</th>
          <th className="text-right px-2.5 py-1.5 font-medium">Down</th>
          <th className="text-right px-2.5 py-1.5 font-medium">Cost</th>
        </tr>
      </thead>
      <tbody>
        {workOrders.map((wo) => (
          <tr key={wo.wo_number} className="border-t border-slate-800/50 align-top">
            <td className="px-2.5 py-1.5 font-mono text-blue-300 whitespace-nowrap">
              {wo.wo_number}
              {wo.breakdown === 1 && (
                <span className="ml-1 text-red-400" title="Unplanned breakdown">
                  ●
                </span>
              )}
            </td>
            {/* ISO on every row of this dataset, so the sort and the display
                agree. Sorted ascending: chronology is what an engineer wants
                from a maintenance log, not reverse-chronology. */}
            <td className="px-2.5 py-1.5 font-mono text-slate-500 whitespace-nowrap">
              {wo.report_date.slice(0, 10)}
            </td>
            <td className="px-2.5 py-1.5 text-slate-400 whitespace-nowrap">{wo.work_type}</td>
            <td className="px-2.5 py-1.5 text-slate-300">{wo.problem_description}</td>
            <td className="px-2.5 py-1.5 text-right font-mono text-slate-400 whitespace-nowrap">
              {wo.downtime_hours > 0 ? formatHours(wo.downtime_hours) : "-"}
            </td>
            <td className="px-2.5 py-1.5 text-right font-mono text-slate-400 whitespace-nowrap">
              {wo.total_cost_idr > 0 ? formatIDR(wo.total_cost_idr) : "-"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Breakdown history with the one-point lessons linked to each failure. */
function FailureMemory({ records }: { records: FailureRecord[] }) {
  if (records.length === 0) {
    return <EmptyState title="No failures recorded for this unit" />;
  }
  return (
    <div className="space-y-2.5">
      {records.map((record) => (
        <div key={record.wo_number} className="rounded border border-slate-800/60 p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-[11px] text-blue-300">{record.wo_number}</span>
            <span className="text-[10px] text-slate-600">
              {record.report_date.slice(0, 10)}
            </span>
            {record.failure_mode && record.failure_mode !== "unclassified" && (
              <Tag tone="blue">{record.failure_mode.replace(/_/g, " ")}</Tag>
            )}
            <span className="text-[10px] text-slate-500 ml-auto font-mono">
              {formatHours(record.downtime_hours)} &middot; {formatIDR(record.total_cost_idr)}
            </span>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-300 leading-relaxed">
            {record.problem_description}
          </p>
          {record.root_cause && (
            <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
              <span className="text-slate-600">Root cause:</span> {record.root_cause}
            </p>
          )}
          {record.corrective_action && (
            <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
              <span className="text-slate-600">Action:</span> {record.corrective_action}
            </p>
          )}
          {record.linked_opls.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-800/60">
              <div className="text-[10px] uppercase tracking-wide text-slate-600 mb-1">
                Related one-point lessons
              </div>
              <ul className="space-y-0.5">
                {record.linked_opls.map((opl) => (
                  <li key={opl.doc_id} className="text-[11px] text-slate-400 flex items-start gap-2">
                    <span className="text-slate-600 font-mono shrink-0">
                      {opl.overlap} shared term{opl.overlap === 1 ? "" : "s"}
                    </span>
                    <span className="break-words">
                      {opl.filename}{" "}
                      <Tag tone={opl.approval_status === "approved" ? "green" : "amber"}>
                        {opl.approval_status}
                      </Tag>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function EquipmentDetail({ tag }: { tag: string }) {
  const detail = usePlantResource(() => plantApi.equipmentDetail(tag), [tag]);
  const documents = usePlantResource(() => plantApi.equipmentDocuments(tag), [tag]);
  const workOrders = usePlantResource(() => plantApi.equipmentWorkOrders(tag), [tag]);
  const memory = usePlantResource(() => plantApi.equipmentFailureMemory(tag), [tag]);

  if (detail.error) {
    // A 404 here means the unit is not in the dataset. The backend names the
    // tags that do exist, so show them instead of a bare failure.
    const detailText =
      detail.error instanceof Error ? detail.error.message : String(detail.error);
    return (
      <div className="p-4">
        <ErrorState error={detail.error} onRetry={detail.reload} />
        {detailText.includes("Available") && (
          <p className="px-6 text-[11px] text-slate-500 -mt-4 break-words">{detailText}</p>
        )}
      </div>
    );
  }

  if (detail.loading || !detail.data) return <Loading label={`Loading ${tag}`} />;

  const unit: Equipment = detail.data;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-800/60 bg-panel-2 p-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-ink font-mono">{unit.equipment_tag}</h2>
              <Tag tone="amber">{unit.criticality}</Tag>
            </div>
            <p className="mt-1 text-sm text-slate-300">{unit.equipment_name}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">{unit.area_name}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div>
              <div className="text-slate-600">Functional location</div>
              <div className="font-mono text-slate-300">{unit.functional_location}</div>
            </div>
            <div>
              <div className="text-slate-600">Interlock</div>
              <div className="font-mono text-slate-300">
                {unit.interlock_ref}
                {unit.interlock_sil ? ` (${unit.interlock_sil})` : ""}
              </div>
            </div>
            <div>
              <div className="text-slate-600">P&ID ref</div>
              <div className="font-mono text-slate-300">{unit.pid_ref}</div>
            </div>
            <div>
              <div className="text-slate-600">Plant</div>
              <div className="text-slate-300">{unit.plant}</div>
            </div>
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-slate-800/60 grid grid-cols-4 gap-3">
          <Stat label="Documents" value={unit.doc_count} sub={`${unit.opl_count} OPL`} />
          <Stat
            label="Approved"
            value={unit.approved_doc_count}
            tone={unit.approved_doc_count > 0 ? "good" : "warn"}
          />
          <Stat label="Work orders" value={unit.wo_count} />
          <Stat
            label="Breakdowns"
            value={memory.data?.record_count ?? "-"}
            tone={(memory.data?.record_count ?? 0) > 0 ? "warn" : "default"}
          />
        </div>
      </div>

      <Panel title="Documents" hint={`${documents.data?.length ?? 0} files`} flush>
        {documents.loading && <Loading />}
        {documents.data && <div className="px-2 py-1"><DocumentTable documents={documents.data} /></div>}
      </Panel>

      <Panel title="Work orders" hint="chronological" flush>
        {workOrders.loading && <Loading />}
        {workOrders.data && (
          <div className="px-2 py-1 max-h-96 overflow-y-auto">
            <WorkOrderTable workOrders={workOrders.data} />
          </div>
        )}
      </Panel>

      <Panel
        title="Failure memory"
        hint={
          memory.data
            ? `${memory.data.record_count} records, ${memory.data.linked_count} with a linked OPL`
            : undefined
        }
      >
        {memory.loading && <Loading />}
        {memory.data && <FailureMemory records={memory.data.records} />}
      </Panel>
    </div>
  );
}

export default function EquipmentPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const equipment = usePlantResource(plantApi.equipment, []);

  return (
    <PageShell
      title="page.equipment.title"
      subtitle="page.equipment.subtitle"
    >
      {equipment.loading && <Loading label="Loading equipment" />}
      {equipment.error !== null && <ErrorState error={equipment.error} onRetry={equipment.reload} />}

      {equipment.data && (
        <div className="flex h-full">
          {/* List */}
          <div className="w-72 shrink-0 border-r border-slate-800/60 overflow-y-auto">
            {equipment.data.map((unit) => (
              <button
                key={unit.equipment_tag}
                onClick={() => setSelected(unit.equipment_tag)}
                aria-current={selected === unit.equipment_tag ? "true" : undefined}
                className={`w-full text-left px-4 py-3 border-b border-slate-800/50 transition-colors ${
                  selected === unit.equipment_tag
                    ? "bg-blue-500/10 border-l-2 border-l-blue-500"
                    : "hover:bg-slate-800/40 border-l-2 border-l-transparent"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-200">{unit.equipment_tag}</span>
                  {unit.criticality?.includes("HIGH") && <Tag tone="amber">high</Tag>}
                </div>
                <div className="mt-0.5 text-[11px] text-slate-400 truncate">
                  {unit.equipment_name}
                </div>
                <div className="mt-1 text-[10px] text-slate-600 font-mono">
                  {unit.doc_count} docs &middot; {unit.wo_count} WO
                  {unit.opl_count > 0 ? ` · ${unit.opl_count} OPL` : ""}
                </div>
              </button>
            ))}
          </div>

          {/* Detail */}
          <div className="flex-1 overflow-y-auto p-4">
            {selected ? (
              <EquipmentDetail key={selected} tag={selected} />
            ) : (
              <EmptyState
                title="Select a unit"
                hint="Each unit opens its document set, its full work-order history in chronological order, and the failures that have a one-point lesson attached to them."
              />
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
