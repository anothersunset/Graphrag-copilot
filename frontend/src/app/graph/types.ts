// Graph visualization shared types & default settings
// Used by app/graph/page.tsx and ControlPanel.tsx

export type GraphSettings = {
  // 筛选 Filter
  showAttachments: boolean;
  onlyCreatedNotes: boolean;
  showOrphans: boolean;
  // 外观 Appearance
  showArrows: boolean;
  textOpacity: number;   // 0 – 1
  nodeSize: number;      // 1 – 10
  linkWidth: number;     // 0.5 – 5
  // 力度 Force
  centerStrength: number; // 0 – 1
  repelStrength: number;  // 10 – 500
  linkStrength: number;   // 0 – 2
  linkDistance: number;   // 20 – 300
  // 颜色 Colour
  colorTheme: string;      // key into COLOR_THEME_PRESETS
  // 小地图 Minimap
  showMinimap: boolean;
};

export const DEFAULT_SETTINGS: GraphSettings = {
  showAttachments: true,
  onlyCreatedNotes: false,
  showOrphans: true,
  showArrows: false,
  textOpacity: 0.55,
  nodeSize: 4,
  linkWidth: 1.5,
  centerStrength: 0.1,
  repelStrength: 120,
  linkStrength: 1,
  linkDistance: 60,
  colorTheme: "默认",
  showMinimap: false,
};

export const SETTINGS_STORAGE_KEY = "graphrag-copilot:graph-settings:v1";

// Color theme presets (Feature A)
export const COLOR_THEME_PRESETS: Record<string, Record<string, string>> = {
  "默认": {
    Technology: "#7C5CFF",
    Concept: "#FF6BD6",
    Organization: "#FFB454",
    Product: "#4ECDC4",
    Document: "#9AA0A6",
    Event: "#F25C54",
  },
  "柔和": {
    Technology: "#B8A9E8",
    Concept: "#F0B8D8",
    Organization: "#FFD5A5",
    Product: "#A8E6DC",
    Document: "#C5C8CB",
    Event: "#F7A8A4",
  },
  "高对比度": {
    Technology: "#0066CC",
    Concept: "#CC0066",
    Organization: "#CC6600",
    Product: "#008877",
    Document: "#555555",
    Event: "#CC0000",
  },
  "暗色": {
    Technology: "#2D1B69",
    Concept: "#5C1A4A",
    Organization: "#5C3A1A",
    Product: "#1A4A3F",
    Document: "#3A3C3E",
    Event: "#5C1A1A",
  },
};

export const FALLBACK_COLOR = "#888";

export function getThemeColors(theme: string): Record<string, string> {
  return COLOR_THEME_PRESETS[theme] ?? COLOR_THEME_PRESETS["默认"];
}

// Minimap constants (Feature B)
export const MINIMAP_SIZE = 150;
export const MINIMAP_MARGIN = 16;
export const MINIMAP_BG = "rgba(0,0,0,0.5)";
export const MINIMAP_BORDER = "1px solid rgba(255,255,255,0.15)";
export const MINIMAP_VIEWPORT_COLOR = "rgba(255,255,255,0.6)";
export const MINIMAP_NODE_RADIUS = 2;

export type NodeSource =
  | { kind: "url"; url: string }
  | { kind: "doc"; doc_id: string }
  | { kind: "neo4j"; entity: string };

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  confidence?: number;
  exists?: boolean;
  source?: NodeSource;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  relation: string;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  status: string;
}

export interface EntityNeighbor {
  name: string;
  type: string;
  distance: number;
}

export interface EntityNeighborsResponse {
  entity: string;
  neighbors: EntityNeighbor[];
  status: string;
}
