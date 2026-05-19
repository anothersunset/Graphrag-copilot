"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useMemo, useCallback } from "react";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const TYPE_COLOR: Record<string, string> = {
  Technology: "#7C5CFF",
  Concept: "#FF6BD6",
  Organization: "#FFB454",
  Product: "#4ECDC4",
  Document: "#9AA0A6",
  Event: "#F25C54",
};

interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  confidence: number;
}

interface GraphLink {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  status: string;
}

export default function GraphPage() {
  const fgRef = useRef<any>(null);
  const [data, setData] = useState<GraphData>({ nodes: [], links: [], status: "" });
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [query, setQuery] = useState("");

  const fetchGraph = useCallback(async () => {
    try {
      const response = await fetch("http://localhost:8000/api/graph?limit=500&type=all");
      if (response.ok) {
        const json = await response.json();
        setData(json);
      }
    } catch (error) {
      console.error("获取图谱数据失败:", error);
    }
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // 构建邻居索引用于悬停高亮
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    data.links.forEach((l) => {
      const s = typeof l.source === "object" ? (l.source as any).id : l.source;
      const t = typeof l.target === "object" ? (l.target as any).id : l.target;
      if (!m.has(s)) m.set(s, new Set());
      if (!m.has(t)) m.set(t, new Set());
      m.get(s)!.add(t);
      m.get(t)!.add(s);
    });
    return m;
  }, [data]);

  const isHighlighted = useCallback(
    (id: string) => {
      if (!hoverNode) {
        return query ? data.nodes.some((n) => n.id === id && n.label.includes(query)) : true;
      }
      if (id === hoverNode.id) return true;
      return neighbors.get(hoverNode.id)?.has(id) ?? false;
    },
    [hoverNode, neighbors, query, data.nodes]
  );

  const stats = useMemo(() => {
    return {
      nodes: data.nodes.length,
      links: data.links.length,
      types: [...new Set(data.nodes.map((n) => n.type))].length,
    };
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">知识图谱</h1>
          <p className="text-gray-600">Obsidian 风格力导向可视化 — {stats.nodes} 节点 · {stats.links} 边 · {stats.types} 类型</p>
        </div>
        <button onClick={fetchGraph} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition text-sm">
          刷新数据
        </button>
      </div>

      <div className="relative rounded-xl overflow-hidden border border-gray-200 shadow-lg" style={{ width: "100%", height: "calc(100vh - 180px)", background: "#0b0b0f" }}>
        {/* 搜索框 */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索实体..."
          className="absolute top-4 left-4 z-10 px-3 py-2 bg-white/6 border border-white/10 rounded-lg text-white w-60 backdrop-blur-md outline-none focus:border-purple-500/50 transition placeholder:text-white/30"
          style={{ background: "rgba(255,255,255,0.06)" }}
        />

        {/* 图例 */}
        <div
          className="absolute top-4 right-4 z-10 p-3 rounded-lg text-white text-xs space-y-1"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <span className="inline-block rounded-full" style={{ width: 10, height: 10, background: color }} />
              {type}
            </div>
          ))}
        </div>

        {data.nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-white/40 text-lg">
            {data.status === "disconnected" ? "Neo4j 未连接" : "加载图谱数据中..."}
          </div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            graphData={data}
            backgroundColor="#0b0b0f"
            nodeRelSize={4}
            nodeVal={(n: any) => Math.max(2, (n.degree ?? 1))}
            nodeColor={(n: any) => TYPE_COLOR[n.type] ?? "#888"}
            nodeLabel={(n: any) => `${n.label}（${n.type} | 度数: ${n.degree}）`}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              // 初始化阶段坐标可能无效，跳过渲染
              if (!isFinite(node.x) || !isFinite(node.y)) return;

              const r = Math.max(2, node.degree ?? 1) * 1.2;
              const highlighted = isHighlighted(node.id);

              // 高亮节点的光晕
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

              // 标签（放大到一定程度或高亮时显示）
              if (scale > 1.2 || highlighted) {
                const fontSize = Math.max(10, 12 / scale);
                ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
                ctx.fillStyle = highlighted ? "#fff" : "rgba(255,255,255,0.55)";
                ctx.textAlign = "center";
                ctx.fillText(node.label ?? node.id, node.x, node.y + r + 10 / scale);
              }
            }}
            // 边颜色
            linkColor={(l: any) => {
              const sid = typeof l.source === "object" ? l.source.id : l.source;
              const tid = typeof l.target === "object" ? l.target.id : l.target;
              if (!hoverNode) return "rgba(255,255,255,0.12)";
              const on = sid === hoverNode.id || tid === hoverNode.id;
              return on ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.06)";
            }}
            linkWidth={(l: any) => (l.weight ?? 0.5) * 1.5}
            linkDirectionalParticles={(l: any) => {
              if (!hoverNode) return 0;
              const sid = typeof l.source === "object" ? l.source.id : l.source;
              const tid = typeof l.target === "object" ? l.target.id : l.target;
              return sid === hoverNode.id || tid === hoverNode.id ? 2 : 0;
            }}
            linkDirectionalParticleSpeed={0.006}
            // 物理参数
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            cooldownTicks={120}
            onNodeHover={setHoverNode}
            onNodeClick={(node: any) => {
              fgRef.current?.centerAt(node.x, node.y, 600);
            }}
          />
        )}
      </div>
    </div>
  );
}
