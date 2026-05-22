/**
 * Deterministic LR layout of the 7-node LangGraph using @dagrejs/dagre.
 *
 * Node visibility is conditional on whether the actual run touched the node
 * (e.g. rewriter only appears if the run rewrote at least once; fallback
 * only appears if CRAG routed to fallback). The cited path is rendered with
 * an accent color.
 */
import Dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";
import type { RunResponse } from "@/lib/api";

const NODE_W = 168;
const NODE_H = 56;

const BASE_ORDER = ["planner", "retriever", "evaluator", "rewriter", "generator", "fallback", "auditor"] as const;

export function buildLayout(run: RunResponse | null): { nodes: Node[]; edges: Edge[] } {
  const touched = new Set<string>(
    run?.audit.map((e) => e.node).filter(Boolean) ?? BASE_ORDER
  );

  const visible = BASE_ORDER.filter((n) => touched.has(n));
  const edges: Edge[] = buildEdges(visible, run);
  const layouted = dagreLayout(visible, edges);

  return {
    nodes: layouted.map((n) => ({
      ...n,
      data: { label: n.id, audit: run?.audit.find((a) => a.node === n.id) },
      type: "default",
      style: nodeStyle(n.id, run),
    })),
    edges: edges.map((e) => ({ ...e, animated: e.data?.cited === true })),
  };
}

function buildEdges(visible: readonly string[], run: RunResponse | null): Edge[] {
  const out: Edge[] = [];
  const has = (n: string) => visible.includes(n);
  if (has("planner") && has("retriever")) out.push(edge("planner", "retriever"));
  if (has("retriever") && has("evaluator")) out.push(edge("retriever", "evaluator"));
  if (has("evaluator") && has("rewriter")) out.push(edge("evaluator", "rewriter", { label: "rewrite" }));
  if (has("rewriter") && has("retriever")) out.push(edge("rewriter", "retriever", { label: "loop" }));
  if (has("evaluator") && has("generator")) out.push(edge("evaluator", "generator", { label: "use" }));
  if (has("evaluator") && has("fallback")) out.push(edge("evaluator", "fallback", { label: "fallback" }));
  if (has("generator") && has("auditor")) out.push(edge("generator", "auditor"));
  if (has("fallback") && has("auditor")) out.push(edge("fallback", "auditor"));

  const cited = new Set(run?.retrieval_trace.filter((r) => r.cited).map((r) => r.source) ?? []);
  return out.map((e) => ({
    ...e,
    data: { ...(e.data ?? {}), cited: cited.size > 0 && /retriever|generator|auditor/.test(e.target) },
  }));
}

function edge(source: string, target: string, opts?: { label?: string }): Edge {
  return { id: `${source}->${target}`, source, target, label: opts?.label };
}

function dagreLayout(ids: readonly string[], edges: Edge[]): Node[] {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 32, ranksep: 56 });
  ids.forEach((id) => g.setNode(id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  Dagre.layout(g);

  return ids.map((id) => {
    const pos = g.node(id);
    return {
      id,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
      data: { label: id },
    } satisfies Node;
  });
}

function nodeStyle(id: string, run: RunResponse | null) {
  const decision = run?.audit.find((a) => a.node === "evaluator")?.detail?.crag_decision;
  if (id === "generator" && decision === "use") return accent();
  if (id === "fallback" && decision === "fallback") return warn();
  return base();
}

const base = () => ({
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 8,
});
const accent = () => ({ ...base(), border: "1px solid hsl(var(--primary))" });
const warn = () => ({ ...base(), border: "1px solid hsl(var(--destructive))" });
