"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import ControlPanel from "./ControlPanel";
import {
  GraphData,
  GraphNode,
  GraphSettings,
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  EntityNeighborsResponse,
} from "./types";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const TYPE_COLOR: Record<string, string> = {
  Technology: "#7C5CFF",
  Concept: "#FF6BD6",
  Organization: "#FFB454",
  Product: "#4ECDC4",
  Document: "#9AA0A6",
  Event: "#F25C54",
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function GraphPage() {
  const fgRef = useRef<any>(null);
  const [data, setData] = useState<GraphData>({ nodes: [], links: [], status: "" });
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [query, setQuery] = useState("");
  const [settings, setSettings] = useState<GraphSettings>(DEFAULT_SETTINGS);
  const [detailEntity, setDetailEntity] = useState<EntityNeighborsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 读取本地保存的设置
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (raw) setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(raw) });
    } catch {
      /* ignore */
    }
  }, []);

  // 持久化设置
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    } catch {
      /* ignore */
    }
  }, [settings]);

  const fetchGraph = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/graph?limit=500&type=all`);
      if (response.ok) {
        const json = await response.json();
        setData(json);
      }
    } catch (error) {
      console.error("获取图谱数据失败:", error);
    }
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // 实时应用力度参数
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    try {
      fg.d3Force("center")?.strength(settings.centerStrength);
      fg.d3Force("charge")?.strength(-settings.repelStrength);
      const linkForce = fg.d3Force("link");
      if (linkForce) {
        linkForce.strength(settings.linkStrength).distance(settings.linkDistance);
      }
      fg.d3ReheatSimulation();
    } catch (e) {
      console.warn("应用力度参数失败:", e);
    }
  }, [
    settings.centerStrength,
    settings.repelStrength,
    settings.linkStrength,
    settings.linkDistance,
    data,
  ]);

  // 筛选后的数据
  const filteredData = useMemo<GraphData>(() => {
    let nodes = data.nodes;
    if (!settings.showAttachments) nodes = nodes.filter((n) => n.type !== "Attachment");
    if (settings.onlyCreatedNotes) nodes = nodes.filter((n) => n.exists !== false);
    if (!settings.showOrphans) nodes = nodes.filter((n) => (n.degree ?? 0) > 0);
    const keep = new Set(nodes.map((n) => n.id));
    const links = data.links.filter((l) => {
      const s = typeof l.source === "object" ? (l.source as any).id : l.source;
      const t = typeof l.target === "object" ? (l.target as any).id : l.target;
      return keep.has(s) && keep.has(t);
    });
    return { nodes, links, status: data.status };
  }, [data, settings.showAttachments, settings.onlyCreatedNotes, settings.showOrphans]);

  // 邻居索引用于悬停高亮
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    filteredData.links.forEach((l) => {
      const s = typeof l.source === "object" ? (l.source as any).id : l.source;
      const t = typeof l.target === "object" ? (l.target as any).id : l.target;
      if (!m.has(s)) m.set(s, new Set());
      if (!m.has(t)) m.set(t, new Set());
      m.get(s)!.add(t);
      m.get(t)!.add(s);
    });
    return m;
  }, [filteredData]);

  const isHighlighted = useCallback(
    (id: string) => {
      if (!hoverNode) {
        return query
          ? filteredData.nodes.some((n) => n.id === id && n.label.includes(query))
          : true;
      }
      if (id === hoverNode.id) return true;
      return neighbors.get(hoverNode.id)?.has(id) ?? false;
    },
    [hoverNode, neighbors, query, filteredData.nodes]
  );

  // 节点跳转 / 打开详情
  const openNodeSource = useCallback(async (node: GraphNode) => {
    const s = node.source;
    if (s && s.kind === "url" && s.url) {
      window.open(s.url, "_blank", "noopener,noreferrer");
      return;
    }
    if (s && s.kind === "doc" && s.doc_id) {
      window.location.href = `/docs/${encodeURIComponent(s.doc_id)}`;
      return;
    }
    setDetailLoading(true);
    setDetailEntity({ entity: node.id, neighbors: [], status: "loading" });
    try {
      const resp = await fetch(
        `${API_BASE}/api/graph/entity/${encodeURIComponent(node.id)}?depth=2`
      );
      if (resp.ok) {
        const json = (await resp.json()) as EntityNeighborsResponse;
        setDetailEntity(json);
      }
    } catch (e) {
      console.error("加载实体邻居失败:", e);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // 单击居中聚焦,双击跳转/打开详情
  const lastClickRef = useRef<{ id: string; t: number }>({ id: "", t: 0 });
  const handleNodeClick = useCallback(
    (node: any) => {
      fgRef.current?.centerAt(node.x, node.y, 600);
      fgRef.current?.zoom(2.2, 600);
      const now = Date.now();
      if (lastClickRef.current.id === node.id && now - lastClickRef.current.t < 350) {
        openNodeSource(node as GraphNode);
      }
      lastClickRef.current = { id: node.id, t: now };
    },
    [openNodeSource]
  );

  const stats = useMemo(
    () => ({
      nodes: filteredData.nodes.length,
      links: filteredData.links.length,
      types: [...new Set(filteredData.nodes.map((n) => n.type))].length,
    }),
    [filteredData]
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">知识图谱</h1>
          <p className="text-gray-600">
            Obsidian 风格力导向可视化 — {stats.nodes} 节点 · {stats.links} 边 · {stats.types} 类型
          </p>
          <p className="text-xs text-gray-400 mt-1">提示：单击节点聚焦，双击节点跳转或打开详情</p>
        </div>
        <button
          onClick={fetchGraph}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition text-sm"
        >
          刷新数据
        </button>
      </div>

      <div
        className="relative rounded-xl overflow-hidden border border-gray-200 shadow-lg"
        style={{ height: "calc(100vh - 220px)", background: "#0b0b0f" }}
      >
        {/* 搜索框 */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索实体..."
          className="absolute top-4 left-4 z-10 px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-white w-60 backdrop-blur-md outline-none focus:border-purple-500/50 transition placeholder:text-white/30"
        />

        {/* 图例 */}
        <div className="absolute top-4 left-72 z-10 p-3 rounded-lg text-white text-xs space-y-1 bg-white/5 border border-white/10 backdrop-blur-md">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <span
                className="inline-block w-2.5 h-2.5 rounded-full"
                style={{ background: color }}
              />
              {type}
            </div>
          ))}
        </div>

        {/* 控制面板 */}
        <ControlPanel
          value={settings}
          onChange={setSettings}
          onReplay={() => fgRef.current?.d3ReheatSimulation()}
          onReset={() => setSettings(DEFAULT_SETTINGS)}
        />

        {/* 实体详情面板 */}
        {detailEntity && (
          <div className="absolute bottom-4 right-80 z-20 w-72 max-h-[60%] overflow-y-auto p-4 rounded-lg bg-black/60 backdrop-blur-xl border border-white/10 text-white text-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold truncate">{detailEntity.entity}</h3>
              <button
                onClick={() => setDetailEntity(null)}
                className="opacity-60 hover:opacity-100"
                aria-label="关闭"
              >
                ✕
              </button>
            </div>
            {detailLoading ? (
              <p className="opacity-60 text-xs">加载中...</p>
            ) : detailEntity.neighbors.length === 0 ? (
              <p className="opacity-60 text-xs">
                {detailEntity.status === "disconnected" ? "Neo4j 未连接" : "暂无相邻实体"}
              </p>
            ) : (
              <ul className="space-y-1.5">
                {detailEntity.neighbors.map((n) => (
                  <li
                    key={n.name}
                    className="flex items-center justify-between gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer"
                    onClick={() => {
                      const target = filteredData.nodes.find((x) => x.id === n.name) as any;
                      if (target && fgRef.current && target.x !== undefined) {
                        fgRef.current.centerAt(target.x, target.y, 600);
                        fgRef.current.zoom(2.4, 600);
                      }
                    }}
                  >
                    <span className="truncate">{n.name}</span>
                    <span className="text-[10px] opacity-60 shrink-0">
                      {n.type} · d{n.distance}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {filteredData.nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-white/40 text-lg">
            {data.status === "disconnected" ? "Neo4j 未连接" : "加载图谱数据中..."}
          </div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            graphData={filteredData as any}
            backgroundColor="#0b0b0f"
            nodeRelSize={settings.nodeSize}
            nodeVal={(n: any) => Math.max(2, n.degree ?? 1)}
            nodeColor={(n: any) => TYPE_COLOR[n.type] ?? "#888"}
            nodeLabel={(n: any) => `${n.label}（${n.type} | 度数: ${n.degree}）`}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              if (!isFinite(node.x) || !isFinite(node.y)) return;
              const r = Math.max(2, node.degree ?? 1) * 1.2;
              const highlighted = isHighlighted(node.id);
              if (highlighted) {
                const color = TYPE_COLOR[node.type] ?? "#fff";
                const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r * 4);
                grad.addColorStop(0, color + "66");
                grad.addColorStop(1, "transparent");
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(node.x, node.y, r * 4, 0, 2 * Math.PI);
                ctx.fill();
              }
              if (scale > 1.2 || highlighted) {
                const fontSize = Math.max(10, 12 / scale);
                ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
                const alpha = highlighted ? 1 : settings.textOpacity;
                ctx.fillStyle = `rgba(255,255,255,${alpha})`;
                ctx.textAlign = "center";
                ctx.fillText(node.label ?? node.id, node.x, node.y + r + 10 / scale);
              }
            }}
            linkColor={(l: any) => {
              const sid = typeof l.source === "object" ? l.source.id : l.source;
              const tid = typeof l.target === "object" ? l.target.id : l.target;
              if (!hoverNode) return "rgba(255,255,255,0.12)";
              const on = sid === hoverNode.id || tid === hoverNode.id;
              return on ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.06)";
            }}
            linkWidth={(l: any) => (l.weight ?? 0.5) * settings.linkWidth}
            linkDirectionalArrowLength={settings.showArrows ? 6 : 0}
            linkDirectionalArrowRelPos={1}
            linkDirectionalParticles={(l: any) => {
              if (!hoverNode) return 0;
              const sid = typeof l.source === "object" ? l.source.id : l.source;
              const tid = typeof l.target === "object" ? l.target.id : l.target;
              return sid === hoverNode.id || tid === hoverNode.id ? 2 : 0;
            }}
            linkDirectionalParticleSpeed={0.006}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            cooldownTicks={120}
            onNodeHover={(n: any) => setHoverNode(n)}
            onNodeClick={handleNodeClick}
          />
        )}
      </div>
    </div>
  );
}
