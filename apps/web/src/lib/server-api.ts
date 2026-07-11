import "server-only"

import type { RunResponse } from "./api"

function backendUrl(path: string): string {
  const base = process.env.GRAPHRAG_API_URL ?? "http://127.0.0.1:8000"
  return `${base.replace(/\/$/, "")}${path}`
}

export async function fetchRun(id: string): Promise<RunResponse | null> {
  const headers = new Headers()
  const apiKey = process.env.GRAPHRAG_API_KEY
  if (apiKey) headers.set("x-api-key", apiKey)

  const response = await fetch(backendUrl(`/v1/runs/${encodeURIComponent(id)}`), {
    headers,
    cache: "no-store",
  })
  if (response.status === 404) return null
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`fetch run failed: ${response.status}${detail ? ` ${detail}` : ""}`)
  }
  return (await response.json()) as RunResponse
}
