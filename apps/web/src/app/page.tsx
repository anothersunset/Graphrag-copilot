"use client"

import { useCallback, useRef, useState } from "react"
import { ask, askStream, type RunResponse, type StreamEvent } from "@/lib/api"
import { AgentFlow } from "@/components/flow/AgentFlow"

export default function HomePage() {
  const [query, setQuery] = useState("")
  const [answer, setAnswer] = useState("")
  const [runData, setRunData] = useState<RunResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [showTrace, setShowTrace] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!query.trim() || loading) return

      setLoading(true)
      setAnswer("")
      setRunData(null)
      setShowTrace(false)

      try {
        const result = await ask(query.trim())
        setAnswer(result.answer)
        setRunData(result)
      } catch (err) {
        setAnswer(`Error: ${err instanceof Error ? err.message : String(err)}`)
      } finally {
        setLoading(false)
      }
    },
    [query, loading],
  )

  const handleStream = useCallback(async () => {
    if (!query.trim() || streaming) return

    setStreaming(true)
    setAnswer("")
    setRunData(null)
    setShowTrace(false)

    const tokens: string[] = []

    try {
      await askStream(query.trim(), (event: StreamEvent) => {
        if (event.type === "token" && event.text) {
          tokens.push(event.text)
          setAnswer(tokens.join(""))
        } else if (event.type === "done") {
          const data = event.data as Record<string, unknown>
          setRunData({
            answer: tokens.join(""),
            audit: [],
            retrieval_trace: [],
            tool_calls: [],
            sources: (data?.sources as RunResponse["sources"]) ?? [],
            confidence: (data?.confidence as number) ?? 0,
            crag_decision: "unknown",
            auditor_verdict: "unknown",
            query,
          })
        }
      })
    } catch (err) {
      setAnswer(`Error: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setStreaming(false)
    }
  }, [query, streaming])

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">GraphRAG Copilot</h1>

        <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入问题..."
            className="flex-1 rounded-lg border bg-card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={loading || streaming}
          />
          <button
            type="submit"
            disabled={loading || streaming || !query.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? "查询中..." : "查询"}
          </button>
          <button
            type="button"
            onClick={handleStream}
            disabled={loading || streaming || !query.trim()}
            className="rounded-lg border bg-card px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
          >
            {streaming ? "流式中..." : "流式"}
          </button>
        </form>

        {answer && (
          <div className="mb-6 rounded-lg border bg-card p-4">
            <h2 className="text-sm font-semibold text-muted-foreground mb-2">回答</h2>
            <div className="text-sm whitespace-pre-wrap">{answer}</div>
          </div>
        )}

        {runData && (
          <>
            <div className="mb-4 flex items-center gap-4 text-xs text-muted-foreground">
              <span>置信度: {(runData.confidence * 100).toFixed(0)}%</span>
              <span>CRAG: {runData.crag_decision}</span>
              <span>Auditor: {runData.auditor_verdict}</span>
              <button
                type="button"
                onClick={() => setShowTrace(!showTrace)}
                className="ml-auto text-primary hover:underline"
              >
                {showTrace ? "隐藏流程图" : "查看流程图"}
              </button>
            </div>

            {runData.sources.length > 0 && (
              <div className="mb-6 rounded-lg border bg-card p-4">
                <h2 className="text-sm font-semibold text-muted-foreground mb-2">
                  来源 ({runData.sources.length})
                </h2>
                <ul className="space-y-2">
                  {runData.sources.map((s, i) => (
                    <li key={s.chunk_id ?? i} className="text-xs border rounded-md p-2">
                      <span className="font-mono text-muted-foreground">
                        {s.source} · score={s.score.toFixed(3)}
                      </span>
                      <p className="mt-1 text-sm">{s.content}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {showTrace && <AgentFlow data={runData} />}
          </>
        )}
      </div>
    </main>
  )
}
