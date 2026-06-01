"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useMemo, useCallback, CSSProperties } from "react";
import ControlPanel from "./ControlPanel";
import {
  GraphData,
  GraphNode,
  GraphSettings,
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  EntityNeighborsResponse,
  getThemeColors,
  FALLBACK_COLOR,
  MINIMAP_SIZE,
  MINIMAP_MARGIN,
  MINIMAP_BG,
  MINIMAP_BORDER,
  MINIMAP_VIEWPORT_COLOR,
  MINIMAP_NODE_RADIUS,
} from "./types";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

//
// === Layout styles ===
// 所有 inline style 都提取为顶部命名常量，JSX 只用 single-brace 引用。
// 这是为了避开 Notion/消息传输层对 double-brace inline 对象的哎害压缩 BUG。
//
const SHELL_STYLE: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "calc(100vh - 160px)",
  minHeight: 560,
  background: "#0b0b0f",
  borderRadius: 12,
  overflow: "hidden",
  boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
};

const SEARCH_STYLE: CSSProperties = {
  position: "absolute",
  top: 16,
  left: 16,
  zIndex: 10,
  width: 240,
  padding: "8px 12px",
  background: "rgba(255,255,255,0.08)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 8,
  color: "#fff",
  outline: "none",
  backdropFilter: "blur(8px)",
};

const EMPTY_STATE_STYLE: CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "rgba(255,255,255,0.4)",
  fontSize: 16,
  pointerEvents: "none",
};

const DETAIL_PANEL_STYLE: CSSProperties = {
  position: "absolute",
  bottom: 16,
  right: 304, // 避开右侧 ControlPanel
  zIndex: 20,
  width: 288,
  maxHeight: "60%",
  overflowY: "auto",
  padding: 16,
  background: "rgba(0,0,0,0.55)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 8,
  backdropFilter: "blur(12px)",
  color: "#fff",
  fontSize: 13,
};

const DETAIL_HEADER_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: 8,
};

const DETAIL_TITLE_STYLE: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  margin: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const DETAIL_CLOSE_STYLE: CSSProperties = {
  opacity: 0.6,
  background: "transparent",
  border: 0,
  color: "#fff",
  cursor: "pointer",
  fontSize: 14,
};

const DETAIL_HINT_STYLE: CSSProperties = {
  opacity: 0.6,
  fontSize: 12,
  margin: 0,
};

const DETAIL_LIST_STYLE: CSSProperties = {
  listStyle: "none",
  padding: 0,
  margin: 0,
};

const DETAIL_ITEM_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  padding: "4px 8px",
  borderRadius: 4,
  cursor: "pointer",
  marginBottom: 2,
};

const DETAIL_ITEM_NAME_STYLE: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const DETAIL_ITEM_META_STYLE: CSSProperties = {
  fontSize: 10,
  opacity: 0.6,
  flexShrink: 0,
};

const SEARCH_WRAP_STYLE: CSSProperties = {
  position: "absolute",
  top: 16,
  left: 16,
  zIndex: 10,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const SEARCH_MATCH_STYLE: CSSProperties = {
  fontSize: 11,
  color: "rgba(255,255,255,0.5)",
  whiteSpace: "nowrap",
  fontVariantNumeric: "tabular-nums",
};

const MINIMAP_CONTAINER_STYLE: CSSProperties = {
  position: "absolute",
  bottom: MINIMAP_MARGIN,
  left: MINIMAP_MARGIN,
  zIndex: 15,
  width: MINIMAP_SIZE,
  height: MINIMAP_SIZE,
  borderRadius: 8,
  overflow: "hidden",
  border: MINIMAP_BORDER,
  background: MINIMAP_BG,
};

const MINIMAP_CANVAS_STYLE: CSSProperties = {
  width: "100%",
  height: "100%",
  display: "block",
};

export default function GraphPage() {
  const fgRef = useRef<any>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const minimapCanvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<GraphData>({ nodes: [], links: [], status: "" });
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const [query, setQuery] = useState("");
  const [searchIndex, setSearchIndex] = useState(0);
  const [settings, setSettings] = useState<GraphSettings>(DEFAULT_SETTINGS);
  const [detailEntity, setDetailEntity] = useState<EntityNeighborsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 动态颜色主题
  const typeColor = useMemo<Record<string, string>>(
    () => getThemeColors(settings.colorTheme),
    [settings.colorTheme]
  );

  // 读取本地保存的设置
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (raw) setSettings(Object.assign({}, DEFAULT_SETTINGS, JSON.parse(raw)));
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

  // 搜索匹配节点（Feature C）
  const matchedNodes = useMemo(() => {
    if (!query) return [];
    return filteredData.nodes.filter((n) => n.label.includes(query));
  }, [query, filteredData.nodes]);

  // 查询变化时重置搜索索引
  useEffect(() => {
    setSearchIndex(0);
  }, [query]);

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
      if (hoverNode) {
        if (id === hoverNode.id) return true;
        return neighbors.get(hoverNode.id)?.has(id) ?? false;
      }
      if (query) return matchedNodes.some((n) => n.id === id);
      return true;
    },
    [hoverNode, neighbors, query, matchedNodes]
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
        // 去重：同名实体保留最短距离
        const seen = new Map<string, typeof json.neighbors[0]>();
        for (const n of json.neighbors) {
          if (!seen.has(n.name) || seen.get(n.name)!.distance > n.distance) {
            seen.set(n.name, n);
          }
        }
        setDetailEntity({ ...json, neighbors: [...seen.values()] });
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

  // -- 小地图绘制（Feature B） --
  const onRenderFramePost = useCallback(
    (_ctx: CanvasRenderingContext2D, _globalScale: number) => {
      if (!settings.showMinimap) return;
      const miniCanvas = minimapCanvasRef.current;
      if (!miniCanvas) return;
      const fg = fgRef.current;
      if (!fg) return;
      const miniCtx = miniCanvas.getContext("2d");
      if (!miniCtx) return;

      const mw = MINIMAP_SIZE;
      const mh = MINIMAP_SIZE;
      const bbox = fg.getGraphBbox();
      if (!bbox || bbox.x[1] === bbox.x[0] || bbox.y[1] === bbox.y[0]) return;

      const gxRange = bbox.x[1] - bbox.x[0];
      const gyRange = bbox.y[1] - bbox.y[0];
      const pad = 0.08;
      const gxMin = bbox.x[0] - gxRange * pad;
      const gxMax = bbox.x[1] + gxRange * pad;
      const gyMin = bbox.y[0] - gyRange * pad;
      const gyMax = bbox.y[1] + gyRange * pad;
      const gxSpan = gxMax - gxMin;
      const gySpan = gyMax - gyMin;

      const scaleX = mw / gxSpan;
      const scaleY = mh / gySpan;
      const sc = Math.min(scaleX, scaleY);
      const ox = (mw - gxSpan * sc) / 2;
      const oy = (mh - gySpan * sc) / 2;
      const toX = (gx: number) => ox + (gx - gxMin) * sc;
      const toY = (gy: number) => oy + (gy - gyMin) * sc;

      miniCtx.clearRect(0, 0, mw, mh);

      // 连线
      miniCtx.strokeStyle = "rgba(255,255,255,0.06)";
      miniCtx.lineWidth = 0.3;
      data.links.forEach((l) => {
        const s = typeof l.source === "object" ? l.source as any : null;
        const t = typeof l.target === "object" ? l.target as any : null;
        if (!s || !t) return;
        miniCtx.beginPath();
        miniCtx.moveTo(toX(s.x ?? 0), toY(s.y ?? 0));
        miniCtx.lineTo(toX(t.x ?? 0), toY(t.y ?? 0));
        miniCtx.stroke();
      });

      // 节点
      data.nodes.forEach((n: any) => {
        if (n.x == null || n.y == null) return;
        miniCtx.beginPath();
        miniCtx.arc(toX(n.x), toY(n.y), MINIMAP_NODE_RADIUS, 0, 2 * Math.PI);
        miniCtx.fillStyle = typeColor[n.type] ?? FALLBACK_COLOR;
        miniCtx.fill();
      });

      // 视口矩形
      const shellEl = shellRef.current;
      if (!shellEl) return;
      const shW = shellEl.clientWidth;
      const shH = shellEl.clientHeight;
      const tl = fg.screen2GraphCoords(0, 0);
      const br = fg.screen2GraphCoords(shW, shH);
      const vx1 = Math.min(tl.x, br.x);
      const vy1 = Math.min(tl.y, br.y);
      const vx2 = Math.max(tl.x, br.x);
      const vy2 = Math.max(tl.y, br.y);

      miniCtx.strokeStyle = MINIMAP_VIEWPORT_COLOR;
      miniCtx.lineWidth = 1;
      miniCtx.strokeRect(toX(vx1), toY(vy1), Math.max(2, (vx2 - vx1) * sc), Math.max(2, (vy2 - vy1) * sc));
    },
    [settings.showMinimap, data.nodes, data.links, typeColor]
  );

  // -- 小地图点击跳转 --
  const handleMinimapClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const fg = fgRef.current;
      if (!fg) return;
      const canvas = minimapCanvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const bbox = fg.getGraphBbox();
      if (!bbox) return;
      const gxRange = bbox.x[1] - bbox.x[0];
      const gyRange = bbox.y[1] - bbox.y[0];
      const pad = 0.08;
      const gxMin = bbox.x[0] - gxRange * pad;
      const gxMax = bbox.x[1] + gxRange * pad;
      const gyMin = bbox.y[0] - gyRange * pad;
      const gyMax = bbox.y[1] + gyRange * pad;
      const gxSpan = gxMax - gxMin;
      const gySpan = gyMax - gyMin;
      const scaleX = MINIMAP_SIZE / gxSpan;
      const scaleY = MINIMAP_SIZE / gySpan;
      const sc = Math.min(scaleX, scaleY);
      const ox = (MINIMAP_SIZE - gxSpan * sc) / 2;
      const oy = (MINIMAP_SIZE - gySpan * sc) / 2;

      const gx = (mx - ox) / sc + gxMin;
      const gy = (my - oy) / sc + gyMin;
      fg.centerAt(gx, gy, 400);
    },
    []
  );

  // -- 搜索 Enter 循环（Feature C） --
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== "Enter" || matchedNodes.length === 0) return;
      const idx = e.shiftKey
        ? (searchIndex - 1 + matchedNodes.length) % matchedNodes.length
        : searchIndex;
      const target = matchedNodes[idx] as any;
      if (target && fgRef.current && typeof target.x === "number" && typeof target.y === "number") {
        fgRef.current.centerAt(target.x, target.y, 600);
        fgRef.current.zoom(2.2, 600);
      }
      setSearchIndex(e.shiftKey ? idx : (searchIndex + 1) % matchedNodes.length);
    },
    [matchedNodes, searchIndex]
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">知识图谱</h1>
          <p className="text-sm text-gray-600">
            Obsidian 风格力导向可视化 · {stats.nodes} 节点 · {stats.links} 边 · {stats.types} 类型
            <span className="text-gray-400 ml-2">（单击聚焦，双击跳转或看邻居）</span>
          </p>
        </div>
        <button
          onClick={fetchGraph}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition text-sm"
        >
          刷新数据
        </button>
      </div>

      {/* 画布容器：内联 style 保证高度/背景/相对定位一定生效 */}
      <div style={SHELL_STYLE} ref={shellRef}>
        {/* 搜索框 + 匹配计数 */}
        <div style={SEARCH_WRAP_STYLE}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="搜索实体（Enter 循环定位）..."
            style={SEARCH_STYLE}
          />
          {query && (
            <span style={SEARCH_MATCH_STYLE}>
              {matchedNodes.length > 0
                ? `${((searchIndex - 1 + matchedNodes.length) % matchedNodes.length) + 1}/${matchedNodes.length}`
                : "0/0"}
            </span>
          )}
        </div>

        {/* 右侧设置面板（含颜色组 / 筛选 / 外观 / 力度） */}
        <ControlPanel
          value={settings}
          onChange={setSettings}
          onReplay={() => fgRef.current?.d3ReheatSimulation()}
          onReset={() => setSettings(DEFAULT_SETTINGS)}
          typeColor={typeColor}
        />

        {/* 小地图 */}
        {settings.showMinimap && filteredData.nodes.length > 0 && (
          <div style={MINIMAP_CONTAINER_STYLE}>
            <canvas
              ref={minimapCanvasRef}
              width={MINIMAP_SIZE}
              height={MINIMAP_SIZE}
              style={MINIMAP_CANVAS_STYLE}
              onClick={handleMinimapClick}
              data-minimap="true"
            />
          </div>
        )}

        {/* 实体详情面板 */}
        {detailEntity && (
          <div style={DETAIL_PANEL_STYLE}>
            <div style={DETAIL_HEADER_STYLE}>
              <h3 style={DETAIL_TITLE_STYLE}>{detailEntity.entity}</h3>
              <button
                onClick={() => setDetailEntity(null)}
                style={DETAIL_CLOSE_STYLE}
                aria-label="关闭"
              >
                ✕
              </button>
            </div>
            {detailLoading ? (
              <p style={DETAIL_HINT_STYLE}>加载中...</p>
            ) : detailEntity.neighbors.length === 0 ? (
              <p style={DETAIL_HINT_STYLE}>
                {detailEntity.status === "disconnected" ? "Neo4j 未连接" : "暂无相邻实体"}
              </p>
            ) : (
              <ul style={DETAIL_LIST_STYLE}>
                {detailEntity.neighbors.map((n) => (
                  <li
                    key={n.name}
                    onClick={() => {
                      const target = filteredData.nodes.find((x) => x.id === n.name) as any;
                      if (target && fgRef.current && target.x !== undefined) {
                        fgRef.current.centerAt(target.x, target.y, 600);
                        fgRef.current.zoom(2.4, 600);
                      }
                    }}
                    style={DETAIL_ITEM_STYLE}
                  >
                    <span style={DETAIL_ITEM_NAME_STYLE}>{n.name}</span>
                    <span style={DETAIL_ITEM_META_STYLE}>
                      {n.type} · d{n.distance}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {filteredData.nodes.length === 0 ? (
          <div style={EMPTY_STATE_STYLE}>
            {data.status === "disconnected" ? "Neo4j 未连接" : "加载图谱数据中..."}
          </div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            graphData={filteredData as any}
            backgroundColor="#0b0b0f"
            nodeRelSize={settings.nodeSize}
            nodeVal={(n: any) => Math.max(2, n.degree ?? 1)}
            nodeColor={(n: any) => typeColor[n.type] ?? FALLBACK_COLOR}
            nodeLabel={(n: any) => `${n.label}（${n.type} | 度数: ${n.degree}）`}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              if (!isFinite(node.x) || !isFinite(node.y)) return;
              const r = Math.max(2, node.degree ?? 1) * 1.2;
              const highlighted = isHighlighted(node.id);
              const isSearchMode = !!query && !hoverNode;

              // 搜索模式下暗化非匹配节点
              if (isSearchMode && !highlighted) {
                ctx.globalAlpha = 0.12;
              }
              if (highlighted) {
                const color = typeColor[node.type] ?? "#fff";
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
              if (isSearchMode && !highlighted) {
                ctx.globalAlpha = 1;
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
            onRenderFramePost={onRenderFramePost}
          />
        )}
      </div>
    </div>
  );
}
