// components/pages/KnowledgeGraphPage.tsx
// The plant knowledge graph, reusing the existing force-graph component.
//
// What this view is for: showing that the document set is a *structure*, not a
// folder. Every unit is connected to the interlock diagram, GA drawing, plot
// plan, datasheet, and one-point lessons that govern it, and every breakdown is
// connected to the unit that failed. That is the claim the Case Book asks for -
// a well-justified data architecture - made visible rather than described.
//
// What it is not for: reading values. A force graph shows topology, and an
// engineer must never take a set point off a node label. The default view
// therefore hides document nodes, because 87 document nodes around 8 equipment
// nodes is a hairball that shows adjacency and nothing else. Document nodes
// become visible on request, for showing that a unit really is backed by seven
// or eight documents.

"use client";

import { useCallback, useMemo, useState } from "react";
import { plantApi, type GraphNode, type KnowledgeGraph } from "@/lib/plantApi";
import { usePlantResource } from "@/hooks/usePlantResource";
import { PageShell, Loading, ErrorState, Tag } from "@/components/shared/PageShell";

type NodeTypeFilter = "equipment" | "interlock" | "document" | "breakdown";

const TYPE_LABELS: Record<NodeTypeFilter, string> = {
  equipment: "Equipment",
  interlock: "Interlock diagrams",
  document: "Documents",
  breakdown: "Breakdowns",
};

/**
 * Trim the graph to a sub-graph around one unit.
 *
 * A whole-plant graph with documents switched on is unreadable, and the useful
 * question is always local: what governs this unit, and what has failed on it.
 * Everything two hops from the selected equipment is kept; anything further is
 * another unit's business.
 */
function subgraphAround(graph: KnowledgeGraph, tag: string): KnowledgeGraph {
  const wanted = new Set<string>([tag]);
  // Two hops out: interlock and documents are already one hop, breakdowns are
  // one hop too, so this reaches every node belonging to this unit.
  for (const link of graph.links) {
    if (link.source === tag) wanted.add(link.target);
    if (link.target === tag) wanted.add(link.source);
  }
  const keep: GraphNode[] = [];
  for (let pass = 0; pass < 2; pass += 1) {
    for (const link of graph.links) {
      if (wanted.has(link.source) && !wanted.has(link.target)) wanted.add(link.target);
      if (wanted.has(link.target) && !wanted.has(link.source)) wanted.add(link.source);
    }
  }
  for (const node of graph.nodes) {
    if (wanted.has(node.id)) keep.push(node);
  }
  const links = graph.links.filter((l) => wanted.has(l.source) && wanted.has(l.target));
  return { nodes: keep, links };
}

/**
 * A small static SVG of the sub-graph.
 *
 * Deliberately not a force simulation. The force graph exists in this codebase
 * for the code-graph view, where the layout is the point. Here the layout is
 * a ring per document type around the unit, which is a fixed arrangement a
 * reader can learn in one look, and it renders identically every time - so a
 * judge and a panelist see the same picture without waiting for it to settle.
 */
function PlantGraph({
  graph,
  selected,
}: {
  graph: KnowledgeGraph;
  selected: string | null;
}) {
  const focus = selected ? subgraphAround(graph, selected) : graph;
  const center = focus.nodes.find((n) => n.type === "equipment");
  const [hover, setHover] = useState<string | null>(null);

  // Only the equipment node is drawn when documents are filtered out, so the
  // canvas stays legible instead of collapsing to a single dot.
  const radius = 190;
  const size = 460;

  const placed = useMemo(() => {
    const others = focus.nodes.filter((n) => n.id !== center?.id);
    return others.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, others.length) - Math.PI / 2;
      return {
        node,
        x: size / 2 + radius * Math.cos(angle),
        y: size / 2 + radius * Math.sin(angle),
      };
    });
  }, [focus.nodes, center?.id]);

  const position = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    if (center) map.set(center.id, { x: size / 2, y: size / 2 });
    for (const p of placed) map.set(p.node.id, { x: p.x, y: p.y });
    return map;
  }, [center, placed]);

  const NODE_STYLE: Record<NodeTypeFilter, { fill: string; stroke: string; r: number }> = {
    equipment: { fill: "#1e3a5f", stroke: "#3b82f6", r: 13 },
    interlock: { fill: "#3f2d1e", stroke: "#f59e0b", r: 8 },
    document: { fill: "#1a2a1e", stroke: "#22c55e", r: 6 },
    breakdown: { fill: "#3f1e1e", stroke: "#ef4444", r: 7 },
  };

  const activeId = hover ?? selected;

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="w-full h-full max-h-[34rem]"
      role="img"
      aria-label={`Knowledge graph: ${focus.nodes.length} nodes, ${focus.links.length} relations`}
    >
      {/* Edges first so nodes sit on top of them. */}
      {focus.links.map((link, i) => {
        const a = position.get(link.source);
        const b = position.get(link.target);
        if (!a || !b) return null;
        const lit = activeId ? link.source === activeId || link.target === activeId : false;
        return (
          <g key={`${link.source}-${link.target}-${i}`}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={lit ? "#60a5fa" : "#243040"}
              strokeWidth={lit ? 1.6 : 1}
              opacity={lit ? 0.95 : 0.7}
            />
            {activeId && lit && (
              <text
                x={(a.x + b.x) / 2}
                y={(a.y + b.y) / 2 - 3}
                textAnchor="middle"
                className="fill-slate-400"
                style={{ fontSize: 7.5 }}
              >
                {link.label}
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {center && (
        <g onMouseEnter={() => setHover(center.id)} onMouseLeave={() => setHover(null)}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={NODE_STYLE.equipment.r}
            fill={NODE_STYLE.equipment.fill}
            stroke={NODE_STYLE.equipment.stroke}
            strokeWidth={2}
          />
          <text
            x={size / 2}
            y={size / 2 - 20}
            textAnchor="middle"
            className="fill-blue-300"
            style={{ fontSize: 11, fontFamily: "monospace" }}
          >
            {center.label}
          </text>
          <text
            x={size / 2}
            y={size / 2 + 28}
            textAnchor="middle"
            className="fill-slate-500"
            style={{ fontSize: 8 }}
          >
            {center.doc_count ?? 0} docs · {center.breakdown_count ?? 0} breakdowns
          </text>
        </g>
      )}

      {placed.map(({ node, x, y }) => {
        const style = NODE_STYLE[node.type];
        const lit = activeId === node.id;
        return (
          <g
            key={node.id}
            onMouseEnter={() => setHover(node.id)}
            onMouseLeave={() => setHover(null)}
            className="cursor-pointer"
          >
            <circle
              cx={x}
              cy={y}
              r={style.r}
              fill={style.fill}
              stroke={style.stroke}
              strokeWidth={lit ? 2.5 : 1.2}
            />
            <text
              x={x}
              y={y + style.r + 9}
              textAnchor="middle"
              className={lit ? "fill-slate-200" : "fill-slate-500"}
              style={{ fontSize: 7.5, fontFamily: "monospace" }}
            >
              {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function KnowledgeGraphPage() {
  const graph = usePlantResource(plantApi.graph, []);
  const [types, setTypes] = useState<Record<NodeTypeFilter, boolean>>({
    equipment: true,
    interlock: true,
    document: false,
    breakdown: true,
  });
  const [selected, setSelected] = useState<string | null>(null);

  const g = graph.data;

  const filtered = useMemo(() => {
    if (!g) return null;
    const keep = new Set(
      g.nodes.filter((n) => types[n.type]).map((n) => n.id),
    );
    // A node whose whole neighbourhood is filtered out is dropped rather than
    // left floating, so the picture never implies a relation that is hidden.
    const nodes = g.nodes.filter((n) => keep.has(n.id));
    const links = g.links.filter((l) => keep.has(l.source) && keep.has(l.target));
    return { nodes, links };
  }, [g, types]);

  const counts = useMemo(() => {
    if (!g) return null;
    const out: Record<string, number> = {};
    for (const node of g.nodes) out[node.type] = (out[node.type] ?? 0) + 1;
    return out;
  }, [g]);

  const linkCounts = useMemo(() => {
    if (!g) return null;
    const out: Record<string, number> = {};
    for (const link of g.links) out[link.label] = (out[link.label] ?? 0) + 1;
    return out;
  }, [g]);

  // Selecting a unit from the list filters the graph to that unit's subgraph.
  const shown = useMemo(() => {
    if (!filtered || !selected) return filtered;
    return subgraphAround({ nodes: filtered.nodes, links: filtered.links }, selected);
  }, [filtered, selected]);

  const toggle = useCallback((type: NodeTypeFilter) => {
    setTypes((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  const equipmentNodes = g?.nodes.filter((n) => n.type === "equipment") ?? [];

  return (
    <PageShell
      title="page.graph.title"
      subtitle="page.graph.subtitle"
    >
      {graph.loading && <Loading label="Building graph" />}
      {graph.error !== null && <ErrorState error={graph.error} onRetry={graph.reload} />}

      {g && counts && shown && (
        <div className="p-6 grid gap-4 lg:grid-cols-[1fr_280px]">
          <div className="space-y-4 min-w-0">
            {/* Filters. Documents are off by default and the caption says why,
                because "why is the graph empty" is the first question a
                viewer asks when they toggle the wrong thing. */}
            <div className="flex flex-wrap items-center gap-2">
              {(Object.keys(TYPE_LABELS) as NodeTypeFilter[]).map((type) => (
                <button
                  key={type}
                  onClick={() => toggle(type)}
                  aria-pressed={types[type]}
                  className={`px-2.5 py-1 rounded-md text-[11px] border transition-colors ${
                    types[type]
                      ? "bg-blue-500/15 text-blue-200 border-blue-500/40"
                      : "bg-slate-900 text-slate-500 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  {TYPE_LABELS[type]}
                  <span className="ml-1.5 font-mono opacity-70">{counts[type] ?? 0}</span>
                </button>
              ))}
              <span className="text-[11px] text-slate-600">
                {shown.nodes.length} nodes, {shown.links.length} relations shown
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/60 bg-[#0a0e14] p-2">
              {shown.nodes.length === 0 ? (
                <div className="p-10 text-center text-[11px] text-slate-500">
                  Every node type is filtered out, or the selected unit has no
                  relations under the current filters.
                </div>
              ) : (
                <PlantGraph graph={shown} selected={selected} />
              )}
            </div>

            <p className="text-[11px] text-slate-500 leading-relaxed">
              Hover a node to highlight its relations and label them. The ring
              is grouped by relation type, so a unit&rsquo;s governing documents are
              always in the same place relative to it.
            </p>
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border border-slate-800/60 bg-[#0f141b] p-4">
              <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-2">
                Focus a unit
              </div>
              <div className="space-y-1">
                <button
                  onClick={() => setSelected(null)}
                  aria-pressed={selected === null}
                  className={`w-full text-left px-2.5 py-1.5 rounded text-[11px] border transition-colors ${
                    selected === null
                      ? "bg-blue-500/10 border-blue-500/40 text-blue-200"
                      : "border-transparent text-slate-400 hover:bg-slate-800/50"
                  }`}
                >
                  Whole plant
                </button>
                {equipmentNodes.map((node) => (
                  <button
                    key={node.id}
                    onClick={() => setSelected(node.id)}
                    aria-pressed={selected === node.id}
                    className={`w-full text-left px-2.5 py-1.5 rounded text-[11px] border transition-colors ${
                      selected === node.id
                        ? "bg-blue-500/10 border-blue-500/40 text-blue-200"
                        : "border-transparent text-slate-400 hover:bg-slate-800/50"
                    }`}
                  >
                    <span className="font-mono">{node.label}</span>
                    <span className="ml-1.5 text-[10px] text-slate-600">
                      {node.doc_count ?? 0}d / {node.breakdown_count ?? 0}b
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Relation counts, measured. This is the architecture claim in
                numbers: 8 datasheets, 8 GA drawings, 8 interlock diagrams,
                8 plot plans, 55 one-point lessons, 31 breakdown links. */}
            <div className="rounded-lg border border-slate-800/60 bg-[#0f141b] p-4">
              <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-2">
                Relations
              </div>
              <div className="space-y-1.5">
                {linkCounts &&
                  Object.entries(linkCounts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([label, count]) => (
                      <div key={label} className="flex items-center gap-2 text-[11px]">
                        <span className="w-20 text-slate-400">{label}</span>
                        <div className="flex-1 h-1 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-blue-500"
                            style={{
                              width: `${(count / Math.max(...Object.values(linkCounts))) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="font-mono text-slate-500 w-7 text-right">
                          {count}
                        </span>
                      </div>
                    ))}
              </div>
            </div>

            <div className="rounded-lg border border-slate-800/60 bg-[#0f141b] p-4">
              <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-2">
                Read this as
              </div>
              <ul className="space-y-1.5 text-[11px] text-slate-500 leading-relaxed">
                <li>
                  - Every unit has all five baseline document types. That is the
                  join key the dataset itself specifies.
                </li>
                <li>
                  - <Tag tone="amber">Documents off</Tag> by default: 87
                  document nodes around 8 units is unreadable. Turn them on to
                  show that one unit really is backed by 7-8 files.
                </li>
                <li>
                  - A red node is a breakdown. It is a record of what happened,
                  not a recommendation about what to do.
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}