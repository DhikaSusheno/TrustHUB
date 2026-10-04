// lib/staticDemo.ts
// Static demo mode for a frontend-only deployment (for example Vercel).
//
// Set NEXT_PUBLIC_STATIC_DEMO=true at build time. The proxy route then answers
// from this file instead of forwarding to the FastAPI backend, so no backend,
// token or dataset is needed on the host.
//
// Honesty rules for everything in this file:
//   - Counts come from DELIVERY_MASTER_PROMPT.md section 2 (verified numbers).
//   - The four preset answers are transcribed from docs/demo/beats.json, the
//     rendered text of the frames in the demo video. Nothing is invented.
//   - Quoted passages from the licensed dataset are left out on purpose.
//   - Anything not captured returns a clear English message, never a guess.

export const STATIC_DEMO = process.env.NEXT_PUBLIC_STATIC_DEMO === "true";

export const STATIC_BANNER_TEXT =
  "Static demo snapshot of verified queries. The live system is shown in the demo video.";

const NOT_CAPTURED =
  "Not included in this static snapshot. This page runs in the live system, shown in the demo video.";

const OMITTED_ANSWER =
  "Answer text omitted in this static snapshot, because it consists of passages quoted from the licensed dataset. The live system returns it with full citations.";

type StaticReply = { status: number; body: unknown };

const STATUS = {
  ready: true,
  database: "static snapshot",
  problem: null,
  counts: {
    equipment: 8,
    documents: 95,
    chunks: 362,
    work_orders: 211,
    failure_links: 92,
    measured_parameters: 105,
    approved_documents: 79,
  },
  approval_breakdown: { approved: 79, unknown: 16 },
  llm: {
    mode: "off",
    external_allowed: false,
    note: "Static snapshot: no language model is called.",
  },
  dataset_licence_note:
    "The official CALIBER-provided dataset, labelled sample data. It is not included in this deployment.",
};

const EMPTY_ANSWER = {
  llm_used: false,
  llm_mode: "off",
  verbatim: false,
  structured: null,
  related_failures: [],
  failure_memory_available: false,
  signals: [] as unknown[],
  reasons: [] as string[],
  warnings: [] as string[],
  sources: [] as unknown[],
};

const opl = (n: string, file: string) => ({
  filename: `OPL-GA-1201A-${n} - ${file}`,
  equipment_tag: "GA-1201A",
  doc_type: "opl",
  approval_status: "approved",
});

const ANSWERS: Record<string, unknown> = {
  "what is the trip setpoint for vshh-1201?": {
    ...EMPTY_ANSWER,
    question: "What is the trip setpoint for VSHH-1201?",
    kind: "parameter_value",
    answer:
      "Measured from the documents themselves: VSHH-1201 = > 7.1 mm/s.\n" +
      "Every value is read from a named document, with its revision and approval status. " +
      "The same numbers feed the conflict detector, so there is a single source of truth for safety limits.",
    badge: "VERIFY",
    trust_score: 0.7795,
    refused: false,
    refusal_reason: null,
    equipment_tag: null,
    cross_unit: false,
    sources: [
      opl("07", "Vibration_Trend_Monitoring_Alarm_Respons_EDITED.pdf"),
      opl("03", "Pump_Motor_Alignment_Check_Laser_edited.pdf"),
      opl("01", "Mechanical_Seal_Flush_API_Plan_11_Verifi_edited_one_page.pdf"),
      opl("02", "Bearing_Oil_Bath_Level_Greasing_EDITED_ONE_PAGE.pdf"),
      opl("03", "Pump_Motor_Alignment_Check_Laser_edited.pdf"),
      opl("05", "Cold_Alignment_vs_Hot_Check_for_Hexane_S_edited.pdf"),
    ],
    signals: [
      { name: "approval", score: 1.0, weight: 0.3, detail: "lowest source approval = approved (1.00)" },
      { name: "revision", score: 0.75, weight: 0.2, detail: "sources carry no revision number" },
      { name: "agreement", score: 1.0, weight: 0.2, detail: "5 documents corroborate each other" },
      {
        name: "relevance",
        score: 0.48,
        weight: 0.2,
        detail: "normalised retrieval strength 0.48 (mean of top 3 raw 7.41) over 6 chunks",
      },
      { name: "coverage", score: 0.33, weight: 0.1, detail: "1 document type(s) contribute evidence" },
    ],
    reasons: [
      "approval=1.00 (weight 0.3)",
      "revision=0.75 (weight 0.2)",
      "agreement=1.00 (weight 0.2)",
      "relevance=0.48 (weight 0.2)",
      "coverage=0.33 (weight 0.1)",
    ],
  },

  "what does opl-ga-1201a-04 cover?": {
    ...EMPTY_ANSWER,
    question: "What does OPL-GA-1201A-04 cover?",
    kind: "document",
    answer: "",
    badge: "DO NOT EXECUTE",
    trust_score: 0,
    refused: true,
    refusal_reason:
      "OPL-GA-1201A-04 does not exist in the indexed dataset. I will not substitute a different document for it.",
    equipment_tag: "GA-1201A",
    cross_unit: false,
  },

  "how do i open a bank account?": {
    ...EMPTY_ANSWER,
    question: "How do I open a bank account?",
    kind: "document",
    answer: "",
    badge: "DO NOT EXECUTE",
    trust_score: 0,
    refused: true,
    refusal_reason:
      "This question is not about any equipment, document, work order, or maintenance record in the indexed dataset, so there is nothing here I can ground an answer in. I will not answer without a source.",
    equipment_tag: null,
    cross_unit: false,
  },

  "can i bypass the psll-1201 trip to keep the feed running?": {
    ...EMPTY_ANSWER,
    question: "Can I bypass the PSLL-1201 trip to keep the feed running?",
    kind: "document",
    answer: OMITTED_ANSWER,
    badge: "DO NOT EXECUTE",
    trust_score: 0.57,
    refused: false,
    refusal_reason: null,
    equipment_tag: null,
    cross_unit: true,
    sources: [
      opl("06", "Start_Up_Priming_Procedure_GA_1201A_EDITED_ONE_PAGE.pdf"),
      {
        filename: "Interlock Logic Diagram - GA-1201A.pdf",
        equipment_tag: "GA-1201A",
        doc_type: "interlock",
        revision: "3",
        approval_status: "unknown",
      },
      opl("07", "Vibration_Trend_Monitoring_Alarm_Respons_EDITED.pdf"),
      opl("07", "Vibration_Trend_Monitoring_Alarm_Respons_EDITED.pdf"),
      {
        filename: "OPL-LV-6701-05 - Manual_Bypass_HV_6701_Operation.pdf",
        equipment_tag: "LV-6701",
        doc_type: "opl",
        approval_status: "approved",
      },
      opl("03", "Pump_Motor_Alignment_Check_Laser_edited.pdf"),
    ],
    signals: [
      {
        name: "approval",
        score: 0.4,
        weight: 0.3,
        detail: "lowest source approval = unknown (0.40); 1 source(s) do not state approval status",
      },
      { name: "revision", score: 1.0, weight: 0.2, detail: "1/6 sources state a revision" },
      {
        name: "agreement",
        score: 0.4,
        weight: 0.2,
        detail:
          "cross-unit question answered from 2 different units (GA-1201A, LV-6701); they do not corroborate each other",
      },
      {
        name: "relevance",
        score: 0.54,
        weight: 0.2,
        detail: "normalised retrieval strength 0.54 (mean of top 3 raw 9.27) over 6 chunks",
      },
      { name: "coverage", score: 0.67, weight: 0.1, detail: "2 document type(s) contribute evidence" },
    ],
    reasons: [
      "safety-critical answer whose source does not state approval status",
      "question asks to modify a safety limit ('bypass the PSLL-1201 trip') -> DO NOT EXECUTE regardless of score; a change to a safety limit is approved through the document's own authority, not by this system",
    ],
  },
};

/** Answer a proxied request from the snapshot instead of a backend. */
export function staticReply(
  segments: readonly string[],
  method: string,
  question: string | null
): StaticReply {
  const path = `/${segments.join("/")}`;

  if (path === "/health" && method === "GET") {
    return { status: 200, body: { status: "ok", mode: "static snapshot" } };
  }
  if (path === "/api/plant/status" && method === "GET") {
    return { status: 200, body: STATUS };
  }
  if (path === "/api/plant/ask" && method === "POST") {
    const key = (question ?? "").trim().toLowerCase();
    const hit = ANSWERS[key];
    if (hit) return { status: 200, body: hit };
    return {
      status: 404,
      body: {
        detail:
          "Not included in this static snapshot. Pick one of the four captured preset scenarios, or see the demo video for the live system.",
      },
    };
  }
  return { status: 404, body: { detail: NOT_CAPTURED } };
}
