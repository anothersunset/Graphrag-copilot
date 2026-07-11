"use client";

import {
	Background,
	Controls,
	MiniMap,
	type Node,
	ReactFlow,
} from "@xyflow/react";
import { useMemo, useState, useSyncExternalStore } from "react";
import "@xyflow/react/dist/style.css";
import "@/styles/flow.css";
import type { RunResponse } from "@/lib/api";
import { AuditDrawer } from "./AuditDrawer";
import { buildLayout } from "./nodes";

const FIT_VIEW_OPTIONS = { padding: 0.2 };
const PRO_OPTIONS = { hideAttribution: true };
const MOBILE_GRAPH_QUERY = "(max-width: 639px)";

function subscribeToMobileGraph(onChange: () => void) {
	const query = window.matchMedia(MOBILE_GRAPH_QUERY);
	query.addEventListener("change", onChange);
	return () => query.removeEventListener("change", onChange);
}

function isMobileGraph() {
	return window.matchMedia(MOBILE_GRAPH_QUERY).matches;
}

export function AgentFlow({ data }: { data: RunResponse | null }) {
	const [activeNode, setActiveNode] = useState<string | null>(null);
	const mobileGraph = useSyncExternalStore(
		subscribeToMobileGraph,
		isMobileGraph,
		() => false,
	);

	const { nodes, edges } = useMemo(
		() => buildLayout(data, mobileGraph ? "TB" : "LR"),
		[data, mobileGraph],
	);

	return (
		<div className="flex h-[min(46rem,calc(100vh-7rem))] min-h-[32rem] flex-col gap-3 lg:flex-row lg:gap-4">
			<div className="min-h-[22rem] min-w-0 flex-1 overflow-hidden rounded-2xl border bg-card shadow-sm">
				<ReactFlow
					key={mobileGraph ? "mobile" : "desktop"}
					nodes={nodes}
					edges={edges}
					fitView
					fitViewOptions={FIT_VIEW_OPTIONS}
					onNodeClick={(_, n: Node) => setActiveNode(n.id)}
					proOptions={PRO_OPTIONS}
				>
					<Background gap={16} />
					<Controls position="bottom-right" />
					<MiniMap pannable zoomable className="hidden !bg-muted/40 sm:block" />
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
