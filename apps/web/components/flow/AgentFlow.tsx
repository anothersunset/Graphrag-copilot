"use client";

import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { buildLayout } from "./nodes";
import { AuditDrawer } from "./AuditDrawer";
import type { RunResponse } from "@/lib/api";

export function AgentFlow({ data }: { data: RunResponse | null }) {
  const [activeNode, setActiveNode] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => buildLayout(data), [data]);

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      <div className="flex-1 rounded-2xl border bg-card shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions= padding: 0.2 
          onNodeClick={(_, n: Node) => setActiveNode(n.id)}
          proOptions= hideAttribution: true 
        >
          <Background gap={16} />
          <Controls position="bottom-right" />
          <MiniMap pannable zoomable className="!bg-muted/40" />
        </ReactFlow>
      </div>
      <AuditDrawer
        run={data}
        activeNode={activeNode}
        onClose={() => setActiveNode(null)}
      />
    </div>
  );
}
