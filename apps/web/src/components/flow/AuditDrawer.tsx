"use client"

import type { RunResponse } from "@/lib/api"

export function AuditDrawer({
  run,
  activeNode,
  onClose,
}: {
  run: RunResponse | null
  activeNode: string | null
  onClose: () => void
}) {
  if (!activeNode || !run) return null
  const entry = run.audit.find((a) => a.node === activeNode)
  const traceRows = run.retrieval_trace.filter((r) => activeNode !== "retriever" || r.source)
  return (
    <aside className="w-96 shrink-0 rounded-2xl border bg-card p-4 shadow-sm overflow-y-auto">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold capitalize">{activeNode}</h2>
          <p className="text-xs text-muted-foreground">{entry?.timestamp}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-muted-foreground hover:underline"
        >
          close
        </button>
      </header>
      <section className="mb-4">
        <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1">summary</h3>
        <p className="text-sm">{entry?.summary ?? "—"}</p>
      </section>
      <section className="mb-4">
        <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1">detail</h3>
        <pre className="text-xs bg-muted/40 rounded-md p-2 whitespace-pre-wrap">
          {JSON.stringify(entry?.detail ?? {}, null, 2)}
        </pre>
      </section>
      {activeNode === "retriever" && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
            retrieval trace
          </h3>
          <ul className="space-y-1">
            {traceRows.slice(0, 10).map((r) => (
              <li
                key={`${r.source}:${r.chunk_id}`}
                className="text-xs flex justify-between gap-2 rounded-md border p-2"
              >
                <span className="font-mono">
                  {r.source}·{r.chunk_id.slice(0, 12)}
                </span>
                <span className="text-muted-foreground">
                  rrf={r.fused_score?.toFixed(3) ?? "–"} rerank={r.rerank_score?.toFixed(3) ?? "–"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  )
}
