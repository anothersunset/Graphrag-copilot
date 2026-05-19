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
};

export const SETTINGS_STORAGE_KEY = "graphrag-copilot:graph-settings:v1";

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
