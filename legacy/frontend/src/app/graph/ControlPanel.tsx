"use client";

import { useState, CSSProperties } from "react";
import { GraphSettings, COLOR_THEME_PRESETS } from "./types";

interface Props {
  value: GraphSettings;
  onChange: (next: GraphSettings) => void;
  onReplay: () => void;
  onReset: () => void;
  typeColor?: Record<string, string>;
}

//
// === Styles ===
// 所有 style 提取为顶部命名常量，避免双花括号内联在传输层被压缩 BUG 吃掉。
//
const PANEL_STYLE: CSSProperties = {
  position: "absolute",
  top: 0,
  right: 0,
  bottom: 0,
  zIndex: 20,
  width: 288,
  overflowY: "auto",
  padding: 16,
  background: "rgba(0,0,0,0.45)",
  borderLeft: "1px solid rgba(255,255,255,0.1)",
  backdropFilter: "blur(14px)",
  color: "#fff",
  fontSize: 13,
};

const OPEN_BUTTON_STYLE: CSSProperties = {
  position: "absolute",
  top: 16,
  right: 16,
  zIndex: 20,
  padding: "6px 12px",
  background: "rgba(255,255,255,0.1)",
  border: "1px solid rgba(255,255,255,0.15)",
  borderRadius: 8,
  color: "#fff",
  fontSize: 12,
  cursor: "pointer",
  backdropFilter: "blur(8px)",
};

const HEADER_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: 16,
};

const HEADER_TITLE_STYLE: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  letterSpacing: "0.04em",
  margin: 0,
};

const HEADER_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  fontSize: 12,
};

const LINK_BTN_STYLE: CSSProperties = {
  background: "transparent",
  border: 0,
  color: "#fff",
  opacity: 0.75,
  cursor: "pointer",
  fontSize: 12,
  padding: 0,
};

const SECTION_STYLE: CSSProperties = {
  marginBottom: 20,
};

const SECTION_TITLE_STYLE: CSSProperties = {
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.15em",
  opacity: 0.55,
  margin: "0 0 10px 0",
  fontWeight: 600,
};

const SECTION_BODY_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

const COLOR_LIST_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
};

const COLOR_ROW_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: 12,
};

const LABEL_STYLE: CSSProperties = {
  opacity: 0.9,
};

const TOGGLE_LABEL_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  cursor: "pointer",
  userSelect: "none",
  fontSize: 13,
};

const TOGGLE_TRACK_BASE: CSSProperties = {
  position: "relative",
  width: 36,
  height: 20,
  borderRadius: 999,
  border: 0,
  cursor: "pointer",
  transition: "background-color .15s",
  flexShrink: 0,
};

const TOGGLE_THUMB_BASE: CSSProperties = {
  position: "absolute",
  top: 2,
  left: 2,
  width: 16,
  height: 16,
  borderRadius: "50%",
  background: "#fff",
  transition: "transform .15s",
};

const SLIDER_WRAP_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const SLIDER_HEAD_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: 12,
  opacity: 0.9,
};

const SLIDER_VALUE_STYLE: CSSProperties = {
  opacity: 0.6,
  fontVariantNumeric: "tabular-nums",
};

const SLIDER_INPUT_STYLE: CSSProperties = {
  width: "100%",
  accentColor: "#7C5CFF",
};

const REPLAY_BTN_STYLE: CSSProperties = {
  width: "100%",
  padding: "8px 0",
  marginTop: 8,
  borderRadius: 6,
  border: 0,
  background: "rgba(124,92,255,0.9)",
  color: "#fff",
  fontSize: 13,
  fontWeight: 500,
  cursor: "pointer",
};

const SELECT_WRAP_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
  marginBottom: 8,
};

const SELECT_STYLE: CSSProperties = {
  width: "100%",
  padding: "6px 8px",
  background: "rgba(255,255,255,0.08)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 6,
  color: "#fff",
  fontSize: 13,
  outline: "none",
  cursor: "pointer",
};

// 动态颜色点：辅助函数返回一个 CSSProperties，避免在 JSX 里写内联对象
function dotStyle(color: string): CSSProperties {
  return {
    display: "inline-block",
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: color,
    boxShadow: "0 0 6px " + color + "66",
    flexShrink: 0,
  };
}

function toggleTrack(active: boolean): CSSProperties {
  return Object.assign({}, TOGGLE_TRACK_BASE, {
    background: active ? "#7C5CFF" : "rgba(255,255,255,0.18)",
  });
}

function toggleThumb(active: boolean): CSSProperties {
  return Object.assign({}, TOGGLE_THUMB_BASE, {
    transform: active ? "translateX(16px)" : "translateX(0)",
  });
}

export default function ControlPanel({
  value,
  onChange,
  onReplay,
  onReset,
  typeColor,
}: Props) {
  const [open, setOpen] = useState(true);
  const set = <K extends keyof GraphSettings>(k: K, v: GraphSettings[K]) =>
    onChange(Object.assign({}, value, { [k]: v }));

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={OPEN_BUTTON_STYLE}>
        ⚙ 设置
      </button>
    );
  }

  return (
    <aside style={PANEL_STYLE}>
      <header style={HEADER_STYLE}>
        <h2 style={HEADER_TITLE_STYLE}>图谱设置</h2>
        <div style={HEADER_ACTIONS_STYLE}>
          <button onClick={onReset} style={LINK_BTN_STYLE}>
            重置
          </button>
          <button
            onClick={() => setOpen(false)}
            style={LINK_BTN_STYLE}
            aria-label="收起设置"
          >
            ✕
          </button>
        </div>
      </header>

      <Section title="筛选">
        <Toggle label="附件" v={value.showAttachments} on={(v) => set("showAttachments", v)} />
        <Toggle
          label="仅显示已创建的笔记"
          v={value.onlyCreatedNotes}
          on={(v) => set("onlyCreatedNotes", v)}
        />
        <Toggle label="孤立文件" v={value.showOrphans} on={(v) => set("showOrphans", v)} />
      </Section>

      {typeColor && Object.keys(typeColor).length > 0 && (
        <Section title="颜色组">
          <div style={SELECT_WRAP_STYLE}>
            <select
              value={value.colorTheme}
              onChange={(e) => set("colorTheme", e.target.value)}
              style={SELECT_STYLE}
            >
              {Object.keys(COLOR_THEME_PRESETS).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div style={COLOR_LIST_STYLE}>
            {Object.entries(typeColor).map(([type, color]) => (
              <div key={type} style={COLOR_ROW_STYLE}>
                <span style={dotStyle(color)} />
                <span style={LABEL_STYLE}>{type}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="外观">
        <Toggle label="箭头" v={value.showArrows} on={(v) => set("showArrows", v)} />
        <Toggle label="显示小地图" v={value.showMinimap} on={(v) => set("showMinimap", v)} />
        <Slider
          label="文本透明度"
          min={0}
          max={1}
          step={0.05}
          v={value.textOpacity}
          on={(v) => set("textOpacity", v)}
        />
        <Slider
          label="节点大小"
          min={1}
          max={10}
          step={0.5}
          v={value.nodeSize}
          on={(v) => set("nodeSize", v)}
        />
        <Slider
          label="连线粗细"
          min={0.5}
          max={5}
          step={0.1}
          v={value.linkWidth}
          on={(v) => set("linkWidth", v)}
        />
        <button onClick={onReplay} style={REPLAY_BTN_STYLE}>
          ▶ 播放动画
        </button>
      </Section>

      <Section title="力度">
        <Slider
          label="图谱向心力"
          min={0}
          max={1}
          step={0.01}
          v={value.centerStrength}
          on={(v) => set("centerStrength", v)}
        />
        <Slider
          label="节点间的排斥力"
          min={10}
          max={500}
          step={5}
          v={value.repelStrength}
          on={(v) => set("repelStrength", v)}
        />
        <Slider
          label="相连节点间的吸引力"
          min={0}
          max={2}
          step={0.05}
          v={value.linkStrength}
          on={(v) => set("linkStrength", v)}
        />
        <Slider
          label="连线长度"
          min={20}
          max={300}
          step={5}
          v={value.linkDistance}
          on={(v) => set("linkDistance", v)}
        />
      </Section>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={SECTION_STYLE}>
      <h3 style={SECTION_TITLE_STYLE}>{title}</h3>
      <div style={SECTION_BODY_STYLE}>{children}</div>
    </section>
  );
}

function Toggle({
  label,
  v,
  on,
}: {
  label: string;
  v: boolean;
  on: (v: boolean) => void;
}) {
  return (
    <label style={TOGGLE_LABEL_STYLE}>
      <span style={LABEL_STYLE}>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={v}
        onClick={() => on(!v)}
        style={toggleTrack(v)}
      >
        <span style={toggleThumb(v)} />
      </button>
    </label>
  );
}

function Slider({
  label,
  min,
  max,
  step,
  v,
  on,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  v: number;
  on: (v: number) => void;
}) {
  return (
    <div style={SLIDER_WRAP_STYLE}>
      <div style={SLIDER_HEAD_STYLE}>
        <span>{label}</span>
        <span style={SLIDER_VALUE_STYLE}>
          {step < 1 ? v.toFixed(2) : v.toFixed(0)}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={v}
        onChange={(e) => on(parseFloat(e.target.value))}
        style={SLIDER_INPUT_STYLE}
      />
    </div>
  );
}
