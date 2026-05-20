import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ImageClip, concatenate_videoclips

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "video_tools_catalog.json"
OUT_DIR = ROOT / "output"
FRAME_DIR = OUT_DIR / "frames"
VIDEO_PATH = OUT_DIR / "apiverse_ai_video_tools_showcase.mp4"
W, H = 1080, 1920
FPS = 24

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def bg(seed=0):
    y = np.linspace(0, 1, H)[:, None]
    a = np.array([24, 18 + seed * 8 % 30, 64 + seed * 13 % 60])
    b = np.array([88 + seed * 11 % 80, 28, 135 + seed * 17 % 80])
    grad = (a * (1 - y) + b * y).astype(np.uint8)
    img = np.tile(grad[:, None, :], (1, W, 1))
    return Image.fromarray(img, "RGB").filter(ImageFilter.GaussianBlur(0.2))


def pill(draw, xy, fill, outline=None, radius=26):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)


def draw_header(draw, title, subtitle=None):
    pill(draw, (55, 70, W - 55, 220), (0, 0, 0, 105), radius=34)
    draw.text((90, 100), title, fill=(255, 255, 255), font=font(58))
    if subtitle:
        draw.text((92, 170), subtitle, fill=(210, 210, 235), font=font(30))


def save_frame(img, name):
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    path = FRAME_DIR / f"{name}.png"
    img.save(path)
    return path


def split_text(text, width):
    lines, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= width:
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    return lines


def cover_frame():
    img = bg(1)
    d = ImageDraw.Draw(img, "RGBA")
    draw_header(d, "APIVerse AI 视频工具专区", "六个工具组成完整短剧生产闭环")
    stages = ["GPT 写剧情", "工具定角色", "Kling/Veo 出视频", "配音字幕", "合成导出"]
    y = 440
    for i, s in enumerate(stages):
        x = 90 + (i % 2) * 450
        if i == 4:
            x = 315
        pill(d, (x, y, x + 360, y + 130), (255, 255, 255, 42), (255, 255, 255, 90), 30)
        d.text((x + 180, y + 38), s, fill=(255, 255, 255), font=font(34), anchor="ma")
        if i % 2 == 1:
            y += 190
    d.text((W // 2, 1580), "你负责验收，我负责实现闭环", fill=(255, 235, 160), font=font(54), anchor="mm")
    d.text((W // 2, 1680), "AI Short Drama Pipeline", fill=(220, 220, 240), font=font(34), anchor="mm")
    return save_frame(img, "00_cover")


def tool_frame(tool, idx):
    img = bg(idx + 2)
    d = ImageDraw.Draw(img, "RGBA")
    draw_header(d, f"{tool['icon']} {tool['name']}", f"{tool['category']} · {tool['role']}")
    color = tuple(tool["color"]) + (255,)
    pill(d, (95, 340, W - 95, 920), (0, 0, 0, 92), color, 42)
    d.text((W // 2, 430), tool["name"], fill=(255, 255, 255), font=font(82), anchor="mm")
    d.text((W // 2, 535), tool["category"], fill=color, font=font(42), anchor="mm")
    y = 650
    for f in tool["features"]:
        pill(d, (170, y, W - 170, y + 78), (255, 255, 255, 38), None, 28)
        d.text((W // 2, y + 22), f"✓ {f}", fill=(255, 255, 255), font=font(34), anchor="ma")
        y += 100
    d.text((W // 2, 1160), "在最终短剧闭环中负责", fill=(220, 220, 235), font=font(36), anchor="mm")
    for line_i, line in enumerate(split_text(tool["role"], 16)):
        d.text((W // 2, 1240 + line_i * 65), line, fill=(255, 240, 180), font=font(48), anchor="mm")
    d.text((W // 2, 1740), f"{idx + 1}/6 · APIVerse Video Tools", fill=(210, 210, 230), font=font(30), anchor="mm")
    return save_frame(img, f"tool_{idx+1}_{tool['id']}")


def workflow_frame():
    img = bg(9)
    d = ImageDraw.Draw(img, "RGBA")
    draw_header(d, "最终生成闭环", "创意输入 → 工具协作 → 完整 MP4")
    steps = [
        ("1", "剧情", "火宝/Toonflow"),
        ("2", "角色资产", "Jellyfish/ComfyUI"),
        ("3", "镜头视频", "ComfyUI/AnimateDiff"),
        ("4", "专业增强", "魔影创作者"),
        ("5", "合成导出", "FFmpeg/MoviePy"),
    ]
    y = 360
    for n, title, tools in steps:
        pill(d, (95, y, W - 95, y + 170), (0, 0, 0, 96), (255, 255, 255, 80), 36)
        d.ellipse((130, y + 43, 214, y + 127), fill=(124, 58, 237, 255))
        d.text((172, y + 65), n, fill=(255, 255, 255), font=font(38), anchor="ma")
        d.text((250, y + 34), title, fill=(255, 255, 255), font=font(48))
        d.text((252, y + 100), tools, fill=(255, 235, 170), font=font(34))
        y += 215
    d.text((W // 2, 1620), "输出：output/apiverse_ai_video_tools_showcase.mp4", fill=(230, 230, 245), font=font(30), anchor="mm")
    return save_frame(img, "99_workflow")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    tools = json.loads(CATALOG.read_text(encoding="utf-8"))
    frames = [cover_frame()] + [tool_frame(t, i) for i, t in enumerate(tools)] + [workflow_frame()]
    durations = [4] + [3.5] * len(tools) + [5]
    clips = []
    for path, dur in zip(frames, durations):
        clip = ImageClip(str(path)).set_duration(dur).resize(lambda t: 1 + 0.012 * math.sin(t * 1.2))
        clips.append(clip)
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(str(VIDEO_PATH), fps=FPS, codec="libx264", audio=False, preset="medium", threads=4)
    print(f"Generated: {VIDEO_PATH}")


if __name__ == "__main__":
    main()
