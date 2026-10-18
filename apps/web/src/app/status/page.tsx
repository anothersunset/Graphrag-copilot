"use client"

import { useEffect, useState } from "react"

// Same-origin proxy (app/api/graphrag/[...path]) forwards to the v3 API.
const API_BASE = "/api/graphrag"

type SystemStatus = {
  status: string
  llm_model: string | null
  llm_wired: boolean
  graph_store: {
    total_nodes: number
    total_relations: number
    communities: number
    status: string
  }
  auth_enabled: boolean
  run_store: string
  readiness: string
}

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetch(`${API_BASE}/api/system/status`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (alive) setStatus(data)
      })
      .catch((exc) => {
        if (alive) setError(String(exc))
      })
    return () => {
      alive = false
    }
  }, [])

  const rowStyle = {
    display: "flex",
    justifyContent: "space-between",
    padding: "10px 0",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
  } as const

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 22, marginBottom: 16 }}>系统状态</h1>
      {error && <p style={{ color: "#F25C54" }}>读取失败：{error}</p>}
      {!status && !error && <p>加载中…</p>}
      {status && (
        <div>
          <div style={rowStyle}>
            <span>服务状态</span>
            <span>{status.status}</span>
          </div>
          <div style={rowStyle}>
            <span>Readiness</span>
            <span>{status.readiness}</span>
          </div>
          <div style={rowStyle}>
            <span>LLM 模型</span>
            <span>
              {status.llm_wired ? (status.llm_model ?? "已配置") : "未接线（离线骨架模式）"}
            </span>
          </div>
          <div style={rowStyle}>
            <span>知识图谱</span>
            <span>
              {status.graph_store.total_nodes} 实体 · {status.graph_store.total_relations} 关系 ·{" "}
              {status.graph_store.communities} 社区
            </span>
          </div>
          <div style={rowStyle}>
            <span>鉴权</span>
            <span>{status.auth_enabled ? "已启用" : "关闭（dev）"}</span>
          </div>
          <div style={rowStyle}>
            <span>Run 存储</span>
            <span>{status.run_store}</span>
          </div>
        </div>
      )}
    </main>
  )
}
