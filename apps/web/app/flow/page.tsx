/**
 * Agent run visualization page.
 *
 * Loads a run by id (via search param ?run=...) and renders:
 *   - the 7-node LangGraph with the cited path highlighted
 *   - an audit drawer for the active node
 *   - per-node retrieval trace rows
 */
import { Suspense } from "react";
import { AgentFlow } from "@/components/flow/AgentFlow";
import { fetchRun } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function FlowPage({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const { run } = await searchParams;
  const data = run ? await fetchRun(run) : null;

  return (
    <main className="min-h-screen bg-background text-foreground p-6">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agent run · {run ?? "new"}</h1>
        <a
          className="text-sm text-muted-foreground underline-offset-4 hover:underline"
          href="/"
        >
          ← back
        </a>
      </header>
      <Suspense fallback={<div>Loading flow…</div>}>
        <AgentFlow data={data} />
      </Suspense>
    </main>
  );
}
