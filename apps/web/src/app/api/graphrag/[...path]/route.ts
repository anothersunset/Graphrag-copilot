import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(
	request: NextRequest,
	context: { params: Promise<{ path: string[] }> },
) {
	const { path } = await context.params;
	const backend = process.env.GRAPHRAG_API_URL ?? "http://127.0.0.1:8000";
	const target = `${backend.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}`;
	const headers = new Headers();
	const contentType = request.headers.get("content-type");
	if (contentType) headers.set("content-type", contentType);
	const apiKey = process.env.GRAPHRAG_API_KEY;
	if (apiKey) headers.set("x-api-key", apiKey);

	const body =
		request.method === "GET" || request.method === "HEAD"
			? undefined
			: await request.arrayBuffer();
	const upstream = await fetch(target, {
		method: request.method,
		headers,
		body,
		cache: "no-store",
	});
	const responseHeaders = new Headers();
	for (const name of [
		"content-type",
		"cache-control",
		"deprecation",
		"sunset",
		"x-accel-buffering",
	]) {
		const value = upstream.headers.get(name);
		if (value) responseHeaders.set(name, value);
	}
	return new Response(upstream.body, {
		status: upstream.status,
		headers: responseHeaders,
	});
}

export const GET = proxy;
export const POST = proxy;
