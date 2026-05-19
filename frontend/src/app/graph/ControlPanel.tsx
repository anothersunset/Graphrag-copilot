"use client";

import { useState } from "react";
import { GraphSettings } from "./types";

interface Props {
  value: GraphSettings;
  onChange: (next: GraphSettings) => void;
  onReplay: () => void;
  onReset: () => void;
}

export default function ControlPanel({ value, onChange, onReplay, onReset }: Props) {
  const [open, setOpen] = useState(true);
  const set = <K extends keyof GraphSettings>(k: K, v: GraphSettings[K]) =>
    onChange({ ...value, [k]: v });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="absolute top-4 right-4 z-20 px-3 py-2 bg-white/10 hover:bg-white/20 border border-white/15 rounded-lg text-white text-xs backdrop-blur-md"
      >
        ⚙ 设置
      </button>
    );
  }

  return (
    <aside className="absolute top-0 right-0 bottom-0 z-20 w-72 overflow-y-auto p-4 space-y-5 bg-black/40 backdrop-blur-xl border-l border-white/10 text-white text-sm">
      <header className="flex items-center justify-between">
        <h2 className="font-semibold tracking-wide">图谱设置</h2>
        <div className="flex items-center gap-3 text-xs">
          <button onClick={onReset} className="hover:underline opacity-75 hover:opacity-100">
            重置
          </button>
          <button onClick={() => setOpen(false)} className="opacity-75 hover:opacity-100" aria-label="收起设置">
            ✕
          </button>
        </div>
      </header>

      <Section title="筛选">
        <Toggle label="附件" v={value.showAttachments} on={(v) => set("showAttachments", v)} />
        <Toggle label="仅显示已创建的笔记" v={value.onlyCreatedNotes} on={(v) => set("onlyCreatedNotes", v)} />
        <Toggle label="孤立文件" v={value.showOrphans} on={(v) => set("showOrphans", v)} />
      </Section>

      <Section title="外观">
        <Toggle label="箭头" v={value.showArrows} on={(v) => set("showArrows", v)} />
        <Slider label="文本透明度" min={0} max={1} step={0.05} v={value.textOpacity} on={(v) => set("textOpacity", v)} />
        <Slider label="节点大小" min={1} max={10} step={0.5} v={value.nodeSize} on={(v) => set("nodeSize", v)} />
        <Slider label="连线粗细" min={0.5} max={5} step={0.1} v={value.linkWidth} on={(v) => set("linkWidth", v)} />
        <button
          onClick={onReplay}
          className="w-full py-2 rounded-md bg-purple-600/90 hover:bg-purple-500 transition text-white text-sm font-medium"
        >
          ▶ 播放动画
        </button>
      </Section>

      <Section title="力度">
        <Slider label="图谱向心力" min={0} max={1} step={0.01} v={value.centerStrength} on={(v) => set("centerStrength", v)} />
        <Slider label="节点间的排斥力" min={10} max={500} step={5} v={value.repelStrength} on={(v) => set("repelStrength", v)} />
        <Slider label="相连节点间的吸引力" min={0} max={2} step={0.05} v={value.linkStrength} on={(v) => set("linkStrength", v)} />
        <Slider label="连线长度" min={20} max={300} step={5} v={value.linkDistance} on={(v) => set("linkDistance", v)} />
      </Section>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2.5">
      <h3 className="text-xs uppercase tracking-widest opacity-60">{title}</h3>
      <div className="space-y-2.5">{children}</div>
    </section>
  );
}

function Toggle({ label, v, on }: { label: string; v: boolean; on: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 cursor-pointer select-none">
      <span className="opacity-90">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={v}
        onClick={() => on(!v)}
        className={`relative w-9 h-5 rounded-full transition-colors ${v ? "bg-purple-500" : "bg-white/15"}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${v ? "translate-x-4" : ""}`}
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
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs opacity-90">
        <span>{label}</span>
        <span className="opacity-60 tabular-nums">{step < 1 ? v.toFixed(2) : v.toFixed(0)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={v}
        onChange={(e) => on(parseFloat(e.target.value))}
        className="w-full accent-purple-500"
      />
    </div>
  );
}
