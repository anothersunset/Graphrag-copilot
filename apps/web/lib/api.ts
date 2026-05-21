export interface AuditEntry {
  node: string;
  timestamp: string;
  summary: string;
  detail: Record<string, unknown> & { crag_decision?: string };
}

export interface RetrievalTraceRow {
  chunk_id: string;
  source: string;
  raw_rank: number | null;
  raw_score: number | null;
  fused_rank: number | null;
  fused_score: number | null;
  rerank_score: number | null;
  cited: boolean;
  metadata: Record<string, unknown>;
}

export interface RunResponse {
  answer: string;
  audit: AuditEntry[];
  retrieval_trace: RetrievalTraceRow[];
  tool_calls: Array<{ name: string; arguments: Record<string, unknown> }>;
}

export async function fetchRun(id: string): Promise<RunResponse | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
  try {
    const r = await fetch(`${base}/v1/runs/${encodeURIComponent(id)}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as RunResponse;
  } catch {
    return null;
  }
}

export async function ask(query: string): Promise<RunResponse> {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
  const r = await fetch(`${base}/v1/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!r.ok) throw new Error(`ask failed: ${r.status}`);
  return (await r.json()) as RunResponse;
}
