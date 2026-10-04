// lib/plantApi.ts
// Typed client for the Manufacturing Knowledge Hub endpoints under
// `/api/plant/*`.
//
// Two things this file deliberately does not do.
//
// 1. It never sees the API token. Every call goes through the Next.js route
//    handler at app/backend/[...path]/route.ts, which injects
//    TRUSTHUB_API_TOKEN from the server environment. A token in the browser
//    bundle would ship the credential to anyone who opens devtools.
//
// 2. It never guesses a shape. Every interface below was measured against a
//    running backend with the official CALIBER dataset ingested, not written
//    from the route signatures. `documents/{doc_id}` returns the same object
//    as an item of `documents`; `equipment/{tag}/documents` returns a bare
//    array, not a paginated envelope, and that asymmetry is typed here so
//    callers cannot get it wrong.

const BASE = "/backend";
const PLANT = `${BASE}/api/plant`;

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

/** A backend error that kept its HTTP status and FastAPI `detail` message. */
export class PlantApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "PlantApiError";
    this.status = status;
    this.detail = detail;
  }

  /** True when the index has not been built yet, so the user needs a command. */
  get needsIndex(): boolean {
    return this.status === 503;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/**
 * Read a JSON response, turning a non-2xx into a PlantApiError.
 *
 * The 503 body matters more than the status: it is the only place the backend
 * says "run `python -m plant.fetch_dataset`", and a UI that replaces that with
 * "something went wrong" has thrown away the only useful instruction it was
 * ever given.
 */
async function read<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T;

  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: unknown; error?: unknown };
    const raw = body?.detail ?? body?.error;
    if (typeof raw === "string" && raw) detail = raw;
  } catch {
    // Non-JSON error body. The status line above is all we have.
  }
  throw new PlantApiError(response.status, detail);
}

function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query}` : "";
  return fetch(`${PLANT}${path}${suffix}`, { cache: "no-store" }).then(read<T>);
}

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

export type Badge = "TRUSTED" | "VERIFY" | "DO NOT EXECUTE";
export type ApprovalStatus = "approved" | "pending" | "draft" | "unknown";
export type LlmMode = "off" | "local" | "external";

export interface PlantCounts {
  equipment: number;
  documents: number;
  chunks: number;
  work_orders: number;
  failure_links: number;
  measured_parameters: number;
  approved_documents: number;
}

export interface PlantStatus {
  ready: boolean;
  database: string;
  /** Recovery command when the index is missing; null when it is fine. */
  problem: string | null;
  counts: PlantCounts;
  approval_breakdown: Partial<Record<ApprovalStatus, number>>;
  llm: { mode: LlmMode; external_allowed: boolean; note: string };
  dataset_licence_note: string;
}

export interface PlantDocument {
  doc_id: string;
  filename: string;
  doc_type: string;
  equipment_tag: string | null;
  title: string;
  doc_no: string | null;
  revision: string | null;
  approval_status: ApprovalStatus;
  approval_raw: string | null;
  effective_date: string | null;
  revision_history: string | null;
  functional_location: string | null;
  criticality: string | null;
  interlock_ref: string | null;
}

export interface Equipment {
  equipment_tag: string;
  equipment_name: string;
  area_code: string | null;
  area_name: string;
  plant: string;
  functional_location: string;
  criticality: string;
  interlock_ref: string;
  interlock_sil: string | null;
  pid_ref: string;
  doc_count: number;
  opl_count: number;
  approved_doc_count: number;
  wo_count: number;
}

export interface WorkOrder {
  wo_number: string;
  notification_no: string;
  equipment_tag: string;
  equipment_name: string;
  functional_location: string;
  area_name: string;
  plant: string;
  work_type: string;
  discipline: string;
  priority: string;
  criticality: string;
  problem_description: string;
  root_cause: string;
  corrective_action: string;
  spare_parts_used: string;
  /** 1 for an unplanned breakdown, 0 otherwise. Integer, not boolean. */
  breakdown: number;
  downtime_hours: number;
  labor_hours: number;
  total_cost_idr: number;
  /** ISO 8601. Every row in the official dataset is ISO, so this sorts. */
  report_date: string;
  related_interlock: string;
  remarks: string;
}

export interface LinkedOpl {
  wo_number: string;
  doc_id: string;
  overlap: number;
  score: number;
  title: string;
  opl_no: string;
  filename: string;
  approval_status: ApprovalStatus;
  revision: string | null;
  approved_by: string | null;
}

export interface FailureRecord extends WorkOrder {
  linked_opls: LinkedOpl[];
  failure_mode: string | null;
}

export interface FailureMemory {
  equipment_tag: string;
  records: FailureRecord[];
  record_count: number;
  linked_count: number;
  link_rate: number;
  total_downtime_hours: number;
  total_cost_idr: number;
}

export interface FailureMemorySummary {
  breakdown_total: number;
  breakdown_downtime_hours: number;
  breakdown_cost_idr: number;
  breakdowns_with_linked_opl: number;
  coverage_pct: number;
  per_equipment: {
    equipment_tag: string;
    breakdown_count: number;
    downtime_hours: number;
    total_cost_idr: number;
    linked_count: number;
    modes: Record<string, number>;
  }[];
}

export interface AnswerSource {
  doc_id?: string;
  filename?: string;
  title?: string;
  doc_type?: string;
  equipment_tag?: string | null;
  doc_no?: string | null;
  revision?: string | null;
  approval_status?: ApprovalStatus;
  approved_by?: string | null;
  relevance?: number;
  content?: string;
  section?: string | null;
}

export interface TrustSignal {
  name: string;
  score: number;
  weight: number;
  detail: string;
}

export interface PlantAnswer {
  question: string;
  kind: string;
  answer: string;
  badge: Badge;
  trust_score: number;
  refused: boolean;
  refusal_reason: string | null;
  equipment_tag: string | null;
  cross_unit: boolean;
  verbatim: boolean;
  sources: AnswerSource[];
  signals: TrustSignal[];
  reasons: string[];
  warnings: string[];
  structured: Record<string, unknown> | null;
  related_failures: WorkOrder[];
  failure_memory_available: boolean;
  llm_used: boolean;
  llm_mode: LlmMode;
}

export interface VerifiedValue {
  equipment_tag: string;
  parameter: string;
  operator: string;
  value: number;
  unit: string;
  kind: string;
  document_count: number;
  document_types: string[];
}

export interface ParameterInventory {
  values_extracted: number;
  by_source: Record<string, number>;
  by_doc_type: Record<string, number>;
  distinct_parameter_groups: number;
}

export interface Verification {
  verified_groups: number;
  verified_trip_setpoints: number;
  conflicts_found: number;
  /** doc_count -> how many parameter groups have that many agreeing docs. */
  document_count_histogram: Record<string, number>;
  values: VerifiedValue[];
  inventory: ParameterInventory;
}

export interface ConflictReport {
  total: number;
  needs_sme: number;
  by_equipment: Record<string, number>;
  by_parameter: Record<string, number>;
  items: unknown[];
  inventory: ParameterInventory;
  filters: {
    groups: number;
    skipped_operator: number;
    skipped_single_doc: number;
    skipped_tolerance: number;
  };
}

export interface EvaluationBucket {
  expected: number;
  correct: number;
  pct: number;
}

/** Summary of the locked accuracy set, as returned by `/evaluation`.
 *
 *  Deliberately excludes the per-case `results`: 63 cases times their answers
 *  and citations is hundreds of kilobytes for data no screen displays. The CLI
 *  keeps the transcript. */
export interface Evaluation {
  spec_version: string | null;
  total: number;
  passed: number;
  accuracy_pct: number;
  /** Cases that must be refused. Reported apart from accuracy because a hub
   *  that answers everything scores well on accuracy and is useless in a
   *  plant. */
  refusal: EvaluationBucket;
  answer: EvaluationBucket;
  by_category: Record<string, { total: number; passed: number }>;
  elapsed_seconds: number;
}

export interface TrustWeights {
  weights: Record<string, number>;
  thresholds: { trusted: number; verify: number; relevance_floor: number };
  approval_scores: Record<ApprovalStatus, number>;
  badges: Badge[];
}

export interface AuditEntry {
  id: number;
  asked_at: string;
  question: string;
  equipment_tag: string | null;
  badge: Badge;
  trust_score: number;
  /** JSON-encoded string, not an array. Parsed by `sourceList` below. */
  sources: string;
  role: string;
}

export interface AuditLog {
  total: number;
  refused: number;
  by_badge: Record<string, number>;
  items: AuditEntry[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: "equipment" | "interlock" | "document" | "breakdown";
  name: string;
  criticality?: string;
  doc_count?: number;
  breakdown_count?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  label: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface DatasetReport {
  root: string;
  pdf_count: number;
  png_count: number;
  xlsx_path: string;
  by_doc_type: Record<string, number>;
  opl_counts: Record<string, number>;
  missing_opl: Record<string, number[]>;
  wo_total: number;
  breakdown_total: number;
  downtime_hours: number;
  total_cost_idr: number;
  breakdown_cost_idr: number;
  per_equipment: {
    equipment_tag: string;
    equipment_name: string;
    area_name: string;
    criticality: string;
    functional_location: string;
    interlock_ref: string;
    wo_count: number;
    breakdown_count: number;
    downtime_hours: number;
    total_cost_idr: number;
  }[];
  date_range: string[];
  problems: string[];
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export const plantApi = {
  status: () => get<PlantStatus>("/status"),
  dataset: () => get<DatasetReport>("/dataset"),
  reindex: () =>
    fetch(`${PLANT}/reindex`, { method: "POST", cache: "no-store" }).then(read<{
      ingested?: Record<string, number>;
      root?: string;
    }>),

  equipment: () => get<Equipment[]>("/equipment"),
  equipmentDetail: (tag: string) => get<Equipment>(`/equipment/${encodeURIComponent(tag)}`),
  equipmentDocuments: (tag: string) =>
    get<PlantDocument[]>(`/equipment/${encodeURIComponent(tag)}/documents`),
  equipmentWorkOrders: (tag: string, breakdownOnly = false) =>
    get<WorkOrder[]>(`/equipment/${encodeURIComponent(tag)}/work-orders`, {
      breakdown_only: breakdownOnly,
    }),
  equipmentFailureMemory: (tag: string) =>
    get<FailureMemory>(`/equipment/${encodeURIComponent(tag)}/failure-memory`),

  documents: (params: {
    equipment_tag?: string;
    doc_type?: string;
    approval_status?: string;
    safety_critical?: boolean;
    limit?: number;
    offset?: number;
  } = {}) => get<{ total: number; limit: number; offset: number; items: PlantDocument[] }>("/documents", params),
  document: (docId: string) => get<PlantDocument>(`/documents/${encodeURIComponent(docId)}`),

  workOrders: (params: { equipment_tag?: string; breakdown_only?: boolean; limit?: number } = {}) =>
    get<{ total: number; returned: number; items: WorkOrder[] }>("/work-orders", params),
  failureMemory: () => get<FailureMemorySummary>("/failure-memory"),

  graph: () => get<KnowledgeGraph>("/graph"),
  verification: () => get<Verification>("/verification"),
  /** Runs the locked accuracy set. ~1s for 63 cases, so call it on page open
   *  rather than on every render. */
  evaluation: () => get<Evaluation>("/evaluation"),
  conflicts: () => get<ConflictReport>("/conflicts"),
  trustWeights: () => get<TrustWeights>("/trust/weights"),
  audit: (limit = 50) => get<AuditLog>("/audit", { limit }),

  search: (q: string, equipmentTag?: string, docType?: string, topK = 8) =>
    get<{ query: string; equipment_tag: string | null; hit_count: number; hits: AnswerSource[] }>(
      "/search",
      { q, equipment_tag: equipmentTag, doc_type: docType, top_k: topK },
    ),

  ask: (question: string, topK = 6) =>
    fetch(`${PLANT}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({ question, top_k: topK, use_llm: false }),
    }).then(read<PlantAnswer>),
};

/** Audit rows store sources as a JSON string. Tolerate both shapes. */
export function sourceList(entry: AuditEntry): string[] {
  if (!entry.sources) return [];
  try {
    const parsed = JSON.parse(entry.sources) as unknown;
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const IDR = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** Indonesian rupiah rendered compactly. The workbook is in IDR; hiding that
 *  behind a "$" symbol would misstate every cost in the dataset. */
export function formatIDR(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "IDR 0";
  if (Math.abs(value) >= 1_000_000_000) return `IDR ${(value / 1_000_000_000).toFixed(2)} B`;
  if (Math.abs(value) >= 1_000_000) return `IDR ${(value / 1_000_000).toFixed(1)} M`;
  if (Math.abs(value) >= 1_000) return `IDR ${(value / 1_000).toFixed(0)} K`;
  return `IDR ${IDR.format(value)}`;
}

export function formatHours(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "0 h";
  return `${IDR.format(Math.round(value * 10) / 10)} h`;
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** A measured limit rendered the way the documents state it. */
export function formatSetpoint(operator: string, value: number, unit: string): string {
  return `${operator} ${value} ${unit}`.trim();
}
