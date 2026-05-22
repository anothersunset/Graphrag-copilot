"use client"

import { Background, Controls, MiniMap, type Node, ReactFlow } from "@xyflow/react"
import { useMemo, useState } from "react"
import "@xyflow/react/dist/style.css"
import type { RunResponse } from "@/lib/api"
import { AuditDrawer } from "./AuditDrawer"
import { buildLayout } from "./nodes"

const FIT_VIEW_OPTIONS = { padding: 0.2 }
const PRO_OPTIONS = { hideAttribution: true }

export function AgentFlow({ data }: { data: RunResponse | null }) {
  const [activeNode, setActiveNode] = useState<string | null>(null)

  const { nodes, edges } = useMemo(() => buildLayout(data), [data])

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      <div className="flex-1 rounded-2xl border bg-card shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={FIT_VIEW_OPTIONS}
          onNodeClick={(_, n: Node) => setActiveNode(n.id)}
          proOptions={PRO_OPTIONS}
        >
          <Background gap={16} />
          <Controls position="bottom-right" />
          <MiniMap pannable zoomable className="!bg-muted/40" />
        </ReactFlow>
      </div>
      <AuditDrawer run={data} activeNode={activeNode} onClose={() => setActiveNode(null)} />
    </div>
  )
}
