// components/pages/DocumentsPage.tsx
// The document register, with the approval and revision evidence visible.
//
// The reason this page exists as a first-class view rather than a filter on
// the graph: trust is a property of a document, not of an answer. An engineer
// deciding whether to follow a procedure needs to see that it is "ISSUED FOR
// OPERATION" at Rev 3 and approved by a named person, on the document, before
// they read the procedure. Hiding that behind an answer badge inverts the
// order in which the judgement should be made.
//
// The 16 documents with no approval marker are shown with an `unknown` badge
// rather than being filtered out. They are real documents in the dataset -
// the interlock PDFs carry no approval field at all - and hiding them would
// make the index look more complete than it is.

"use client";

import { useMemo, useState } from "react";
import {
  plantApi,
  type PlantDocument,
  type ApprovalStatus,
} from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import {
  PageShell,
  Panel,
  Loading,
  ErrorState,
  EmptyState,
  Tag,
} from "@/components/shared/PageShell";

const DOC_TYPES = ["datasheet", "ga", "interlock", "plot_plan", "opl"] as const;
const APPROVALS: ApprovalStatus[] = ["approved", "pending", "draft", "unknown"];

const PAGE_SIZE = 50;

/** Where the approval evidence was found, per document type. */
function evidenceSource(doc: PlantDocument): string {
  if (doc.approval_raw) {
    if (doc.doc_type === "datasheet") return "DATASHEET REV field";
    if (doc.doc_type === "opl") return "signature table";
    return "REVISION HISTORY";
  }
  if (doc.doc_type === "interlock") return "no approval field in this document type";
  return "not stated";
}

function DocumentRow({ doc }: { doc: PlantDocument }) {
  const [open, setOpen] = useState(false);
  const approved = doc.approval_status === "approved";
  // A revision history is multi-line and would blow out the row, so it lives
  // behind a toggle. It is the actual provenance, so it must be one click away.
  const hasHistory = Boolean(doc.revision_history);

  return (
    <>
      <tr className="border-t border-slate-800/50 align-top">
        <td className="px-2.5 py-2">
          <button
            onClick={() => hasHistory && setOpen((v) => !v)}
            className={`text-left ${hasHistory ? "hover:text-blue-300 cursor-pointer" : "cursor-default"}`}
          >
            <div className="break-words text-slate-200">
              {hasHistory && (
                <span className="text-slate-600 font-mono mr-1">
                  {open ? "▾" : "▸"}
                </span>
              )}
              {doc.filename}
            </div>
            {doc.title && (
              <div className="mt-0.5 text-[10px] text-slate-600 truncate">{doc.title}</div>
            )}
          </button>
        </td>
        <td className="px-2.5 py-2 text-slate-400 whitespace-nowrap">{doc.doc_type}</td>
        <td className="px-2.5 py-2 font-mono text-blue-300 whitespace-nowrap">
          {doc.equipment_tag ?? "-"}
        </td>
        <td className="px-2.5 py-2 font-mono text-slate-400 whitespace-nowrap">
          {doc.doc_no ?? "-"}
        </td>
        <td className="px-2.5 py-2 font-mono text-slate-400 whitespace-nowrap">
          {doc.revision ?? "-"}
        </td>
        <td className="px-2.5 py-2 whitespace-nowrap">
          <Tag tone={approved ? "green" : doc.approval_status === "unknown" ? "slate" : "amber"}>
            {doc.approval_status}
          </Tag>
        </td>
        <td className="px-2.5 py-2 font-mono text-slate-500 whitespace-nowrap">
          {doc.effective_date ?? "-"}
        </td>
      </tr>
      {open && hasHistory && (
        <tr className="bg-inset">
          <td colSpan={7} className="px-4 py-2.5">
            <div className="text-[10px] uppercase tracking-wide text-slate-600 mb-1">
              Revision history &mdash; read from {evidenceSource(doc)}
            </div>
            <pre className="text-[11px] text-slate-300 whitespace-pre-wrap font-mono leading-relaxed break-words">
              {doc.revision_history}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

export default function DocumentsPage() {
  const [docType, setDocType] = useState<string>("");
  const [approval, setApproval] = useState<string>("");
  const [page, setPage] = useState(0);

  // Reset to the first page when a filter changes, otherwise a filter that
  // narrows to two documents can leave the reader on page 3 seeing nothing.
  const filterKey = `${docType}|${approval}`;
  const [lastFilter, setLastFilter] = useState(filterKey);
  if (lastFilter !== filterKey) {
    setLastFilter(filterKey);
    setPage(0);
  }

  const offset = page * PAGE_SIZE;
  const documents = usePlantResource(
    () =>
      plantApi.documents({
        doc_type: docType,
        approval_status: approval,
        limit: PAGE_SIZE,
        offset,
      }),
    [docType, approval, offset],
  );

  const total = documents.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const selectClass =
    "px-2 py-1 rounded bg-panel border border-slate-700 text-[11px] text-slate-300 focus:outline-none focus:border-blue-500/60";

  const summary = useMemo(() => {
    if (!documents.data) return null;
    const byType: Record<string, number> = {};
    const byApproval: Record<string, number> = {};
    for (const doc of documents.data.items) {
      byType[doc.doc_type] = (byType[doc.doc_type] ?? 0) + 1;
      byApproval[doc.approval_status] = (byApproval[doc.approval_status] ?? 0) + 1;
    }
    return { byType, byApproval };
  }, [documents.data]);

  return (
    <PageShell
      title="page.documents.title"
      subtitle="page.documents.subtitle"
      actions={
        <>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            aria-label="Filter by document type"
            className={selectClass}
          >
            <option value="">All types</option>
            {DOC_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <select
            value={approval}
            onChange={(e) => setApproval(e.target.value)}
            aria-label="Filter by approval status"
            className={selectClass}
          >
            <option value="">Any approval</option>
            {APPROVALS.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </>
      }
    >
      {documents.loading && page === 0 && <Loading label="Loading documents" />}
      {documents.error !== null && <ErrorState error={documents.error} onRetry={documents.reload} />}

      {documents.data && (
        <div className="p-6 space-y-4">
          {/* Counts for what is on screen, so a filtered view is honest about
              being filtered rather than silently smaller. */}
          {summary && (
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="text-slate-500">
                {documents.data.items.length} shown of {total}
              </span>
              {Object.entries(summary.byType).map(([type, count]) => (
                <Tag key={type}>
                  {type}: {count}
                </Tag>
              ))}
              {Object.entries(summary.byApproval).map(([status, count]) => (
                <Tag
                  key={status}
                  tone={status === "approved" ? "green" : status === "unknown" ? "slate" : "amber"}
                >
                  {status}: {count}
                </Tag>
              ))}
            </div>
          )}

          {documents.data.items.length === 0 ? (
            <EmptyState
              title="No documents match this filter"
              hint="Clear the filters to see the full register."
            />
          ) : (
            <Panel flush>
              <table className="w-full text-[11px]">
                <thead className="text-slate-400 bg-slate-800/30">
                  <tr>
                    <th className="text-left px-2.5 py-2 font-medium">Document</th>
                    <th className="text-left px-2.5 py-2 font-medium">Type</th>
                    <th className="text-left px-2.5 py-2 font-medium">Unit</th>
                    <th className="text-left px-2.5 py-2 font-medium">Doc no.</th>
                    <th className="text-left px-2.5 py-2 font-medium">Rev</th>
                    <th className="text-left px-2.5 py-2 font-medium">Approval</th>
                    <th className="text-left px-2.5 py-2 font-medium">Effective</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.data.items.map((doc) => (
                    <DocumentRow key={doc.doc_id} doc={doc} />
                  ))}
                </tbody>
              </table>
            </Panel>
          )}

          {pages > 1 && (
            <div className="flex items-center justify-between text-[11px]">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 disabled:text-slate-600 disabled:bg-slate-900 text-slate-200 border border-slate-700 disabled:border-slate-800"
              >
                Previous
              </button>
              <span className="text-slate-500 font-mono">
                page {page + 1} of {pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 disabled:text-slate-600 disabled:bg-slate-900 text-slate-200 border border-slate-700 disabled:border-slate-800"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </PageShell>
  );
}