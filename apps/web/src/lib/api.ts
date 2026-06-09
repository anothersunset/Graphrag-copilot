export interface AuditEntry {
  node: string
  timestamp: string
  summary: string
  detail: Record<string, unknown> & { crag_decision?: string }
}

export interface RetrievalTraceRow {
  chunk_id: string
  source: string
  raw_rank: number | null
  raw_score: number | null
  fused_rank: number | null
  fused_score: number | null
  rerank_score: number | null
  cited: boolean
  metadata: Record<string, unknown>
}

export interface RunResponse {
  answer: string
  audit: AuditEntry[]
  retrieval_trace: RetrievalTraceRow[]
  tool_calls: Array<{ name: string; arguments: Record<string, unknown> }>
  sources: Array<{ content: string; source: string; score: number; chunk_id: string }>
  confidence: number
  crag_decision: string
  auditor_verdict: string
  query: string
}

/** Backend QueryResponse (raw) */
interface BackendQueryResponse {
  query: string
  answer: string
  sources: Array<{ content: string; source: string; score: number; chunk_id: string }>
  analysis: Record<string, unknown>
  verification: Record<string, unknown>
  trace: {
    nodes: string[]
    audit: Array<Record<string, unknown>>
    tool_calls: Array<Record<string, unknown>>
    rewrite_iteration: number
  }
  confidence: number
  crag_decision: string
  auditor_verdict: string
}

function resolveApiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  )
}

/** Transform backend QueryResponse → RunResponse for AgentFlow */
function toRunResponse(raw: BackendQueryResponse): RunResponse {
  const audit: AuditEntry[] = (raw.trace?.audit ?? []).map((e, i) => ({
    node: (e.node as string) ?? `step-${i}`,
    timestamp: (e.timestamp as string) ?? "",
    summary: (e.summary as string) ?? JSON.stringify(e),
    detail: e as Record<string, unknown>,
  }))

  const retrievalTrace: RetrievalTraceRow[] = (raw.sources ?? []).map((s, i) => ({
    chunk_id: s.chunk_id ?? `chunk-${i}`,
    source: s.source ?? "unknown",
    raw_rank: i + 1,
    raw_score: s.score ?? null,
    fused_rank: null,
    fused_score: null,
    rerank_score: null,
    cited: true,
    metadata: {},
  }))

  const toolCalls = (raw.trace?.tool_calls ?? []).map((tc) => ({
    name: (tc.name as string) ?? "unknown",
    arguments: (tc.arguments as Record<string, unknown>) ?? {},
  }))

  return {
    answer: raw.answer,
    audit,
    retrieval_trace: retrievalTrace,
    tool_calls: toolCalls,
    sources: raw.sources ?? [],
    confidence: raw.confidence ?? 0,
    crag_decision: raw.crag_decision ?? "unknown",
    auditor_verdict: raw.auditor_verdict ?? "unknown",
    query: raw.query,
  }
}

export async function fetchRun(_id: string): Promise<RunResponse | null> {
  // Backend doesn't have a run-by-id endpoint yet
  return null
}

export async function ask(query: string): Promise<RunResponse> {
  const base = resolveApiBase()
  const r = await fetch(`${base}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  })
  if (!r.ok) throw new Error(`ask failed: ${r.status}`)
  const raw = (await r.json()) as BackendQueryResponse
  return toRunResponse(raw)
}

export interface StreamEvent {
  type: "phase" | "answer_start" | "token" | "answer_end" | "done" | "error"
  phase?: string
  data?: Record<string, unknown>
  text?: string
  error?: string
}

/** SSE streaming query */
export async function askStream(
  query: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const base = resolveApiBase()
  const r = await fetch(`${base}/api/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  })
  if (!r.ok) throw new Error(`stream failed: ${r.status}`)

  const reader = r.body?.getReader()
  if (!reader) throw new Error("no stream body")

  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6)) as StreamEvent
          onEvent(event)
        } catch {
          // skip malformed events
        }
      }
    }
  }
}
