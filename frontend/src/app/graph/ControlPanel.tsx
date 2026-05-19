"use client";

import { useState, CSSProperties } from "react";
import { GraphSettings } from "./types";

interface Props {
  value: GraphSettings;
  onChange: (next: GraphSettings) => void;
  onReplay: () => void;
  onReset: () => void;
  /** 节点类型→颜色映射，用于「颜色组」一节 */
  typeColor?: Record<string, string>;
}

// 布局关键属性一律用内联 style，避免 Tailwind 未生效时坍方
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

const TOGGLE_BUTTON_STYLE: CSSProperties = {
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

export default function ControlPanel({
  value,
  onChange,
  onReplay,
  onReset,
  typeColor,
}: Props) {
  const [open, setOpen] = useState(true);
  const set = <K extends keyof GraphSettings>(k: K, v: GraphSettings[K]) =>
    onChange({ ...value, [k]: v });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={TOGGLE_BUTTON_STYLE}>
        ⚙ 设置
      </button>
    );
  }

  return (
    <aside style={PANEL_STYLE}>
      <header
        style=
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        
      >
        <h2 style= fontSize: 14, fontWeight: 600, letterSpacing: "0.04em", margin: 0 >
          图谱设置
        </h2>
        <div style= display: "flex", alignItems: "center", gap: 12, fontSize: 12 >
          <button onClick={onReset} style={linkBtnStyle}>
            重置
          </button>
          <button onClick={() => setOpen(false)} style={linkBtnStyle} aria-label="收起设置">
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
          <div style= display: "flex", flexDirection: "column", gap: 6 >
            {Object.entries(typeColor).map(([type, color]) => (
              <div
                key={type}
                style= display: "flex", alignItems: "center", gap: 8, fontSize: 12 
              >
                <span
                  style=
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: color,
                    boxShadow: "0 0 6px " + color + "66",
                    flexShrink: 0,
                  
                />
                <span style= opacity: 0.9 >{type}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="外观">
        <Toggle label="箭头" v={value.showArrows} on={(v) => set("showArrows", v)} />
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
        <button
          onClick={onReplay}
          style=
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
          
        >
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

const linkBtnStyle: CSSProperties = {
  background: "transparent",
  border: 0,
  color: "#fff",
  opacity: 0.75,
  cursor: "pointer",
  fontSize: 12,
  padding: 0,
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style= marginBottom: 20 >
      <h3
        style=
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.15em",
          opacity: 0.55,
          margin: "0 0 10px 0",
          fontWeight: 600,
        
      >
        {title}
      </h3>
      <div style= display: "flex", flexDirection: "column", gap: 10 >{children}</div>
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
    <label
      style=
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        cursor: "pointer",
        userSelect: "none",
        fontSize: 13,
      
    >
      <span style= opacity: 0.9 >{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={v}
        onClick={() => on(!v)}
        style=
          position: "relative",
          width: 36,
          height: 20,
          borderRadius: 999,
          border: 0,
          cursor: "pointer",
          transition: "background-color .15s",
          background: v ? "#7C5CFF" : "rgba(255,255,255,0.18)",
        
      >
        <span
          style=
            position: "absolute",
            top: 2,
            left: 2,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: "#fff",
            transition: "transform .15s",
            transform: v ? "translateX(16px)" : "translateX(0)",
          
        />
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
    <div style= display: "flex", flexDirection: "column", gap: 4 >
      <div
        style=
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 12,
          opacity: 0.9,
        
      >
        <span>{label}</span>
        <span style= opacity: 0.6, fontVariantNumeric: "tabular-nums" >
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
        style= width: "100%", accentColor: "#7C5CFF" 
      />
    </div>
  );
}
