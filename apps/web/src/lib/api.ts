export interface AuditEntry {
	node: string;
	timestamp: string;
	decision?: string;
	rationale?: string;
	summary?: string;
	detail?: Record<string, unknown> & { crag_decision?: string };
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

export interface SourceRow {
	chunk_id: string;
	content: string;
	source: string;
	score: number;
	cited: boolean;
	metadata: Record<string, unknown>;
}

export interface RunResponse {
	run_id: string;
	query: string;
	answer: string;
	verdict: string;
	confidence: number;
	crag_decision: string;
	cited_chunk_ids: string[];
	sources: SourceRow[];
	retrieval_trace: RetrievalTraceRow[];
	audit: AuditEntry[];
	claims: Array<Record<string, unknown>>;
	query_history: string[];
	tool_calls: Array<{
		tool?: string;
		name?: string;
		args?: Record<string, unknown>;
	}>;
	evidence_pack: Record<string, unknown> | null;
}

const API_BASE = "/api/graphrag";

async function readJson<T>(response: Response, operation: string): Promise<T> {
	if (!response.ok) {
		const detail = await response.text();
		throw new Error(
			`${operation} failed: ${response.status}${detail ? ` ${detail}` : ""}`,
		);
	}
	return (await response.json()) as T;
}

export async function ask(query: string): Promise<RunResponse> {
	const response = await fetch(`${API_BASE}/v1/ask`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ query }),
	});
	return readJson<RunResponse>(response, "ask");
}

export interface StreamEvent {
	type: "phase" | "answer_start" | "token" | "answer_end" | "done" | "error";
	phase?: string;
	data?: RunResponse;
	text?: string;
	error?: string;
}

export async function askStream(
	query: string,
	onEvent: (event: StreamEvent) => void,
): Promise<void> {
	const response = await fetch(`${API_BASE}/v1/ask/stream`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ query }),
	});
	if (!response.ok)
		throw new Error(
			`stream failed: ${response.status} ${await response.text()}`,
		);

	const reader = response.body?.getReader();
	if (!reader) throw new Error("stream response has no body");

	const decoder = new TextDecoder();
	let buffer = "";
	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });
		const frames = buffer.split("\n\n");
		buffer = frames.pop() ?? "";
		for (const frame of frames) {
			const data = frame
				.split("\n")
				.find((line) => line.startsWith("data: "))
				?.slice(6);
			if (!data) continue;
			let event: StreamEvent;
			try {
				event = JSON.parse(data) as StreamEvent;
			} catch {
				onEvent({ type: "error", error: "malformed stream event" });
				continue;
			}
			onEvent(event);
		}
	}
}
