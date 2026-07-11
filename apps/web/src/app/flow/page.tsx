import { AgentFlow } from "@/components/flow/AgentFlow";
import { fetchRun } from "@/lib/server-api";
/**
 * Agent run visualization page.
 *
 * Loads a run by id (via search param ?run=...) and renders:
 *   - the 7-node LangGraph with the cited path highlighted
 *   - an audit drawer for the active node
 *   - per-node retrieval trace rows
 */
import { Suspense } from "react";

export const dynamic = "force-dynamic";

async function FlowContent({ run }: { run?: string }) {
	if (!run) {
		return (
			<div className="rounded-2xl border bg-card p-6 text-sm text-muted-foreground">
				Add a{" "}
				<code className="rounded bg-muted px-1 py-0.5">
					?run=&lt;run-id&gt;
				</code>{" "}
				query to inspect a completed GraphRAG run.
			</div>
		);
	}

	try {
		const data = await fetchRun(run);
		if (!data) {
			return (
				<output className="block rounded-2xl border bg-card p-6 text-sm">
					Run <span className="break-all font-mono">{run}</span> was not found
					or has expired.
				</output>
			);
		}
		return <AgentFlow data={data} />;
	} catch (error) {
		return (
			<div
				className="rounded-2xl border border-destructive bg-card p-6 text-sm"
				role="alert"
			>
				Unable to load this run.{" "}
				{error instanceof Error ? error.message : String(error)}
			</div>
		);
	}
}

export default async function FlowPage({
	searchParams,
}: {
	searchParams: Promise<{ run?: string }>;
}) {
	const { run } = await searchParams;

	return (
		<main className="min-h-screen bg-background p-4 text-foreground sm:p-6">
			<header className="mb-4 flex flex-wrap items-center justify-between gap-3">
				<h1 className="min-w-0 text-xl font-semibold sm:text-2xl">
					Agent run ·{" "}
					<span className="break-all font-mono text-base sm:text-lg">
						{run ?? "new"}
					</span>
				</h1>
				<a
					className="rounded-md text-sm text-muted-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
					href="/"
				>
					← back
				</a>
			</header>
			<Suspense
				fallback={
					<output className="block rounded-2xl border bg-card p-6 text-sm text-muted-foreground">
						Loading flow…
					</output>
				}
			>
				<FlowContent run={run} />
			</Suspense>
		</main>
	);
}
