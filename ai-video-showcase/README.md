# APIVerse AI 视频工具专区展示片

这个目录用于生成一个类似上传 MP4 风格的竖屏展示视频，内容来自 APIVerse 的六个 AI 视频生成工具：

- Toonflow
- Jellyfish
- 火宝短剧
- 魔影创作者
- ComfyUI
- AnimateDiff

## 本地运行

```bash
cd ai-video-showcase
pip install -r requirements-video.txt
python render_showcase_video.py
```

输出文件：

```text
ai-video-showcase/output/apiverse_ai_video_tools_showcase.mp4
```

## 作用

这是第一阶段可运行样片，用于验证“AI 视频工具专区”的展示风格、内容结构和生成闭环。后续可以继续接入真实 ComfyUI / AnimateDiff / Kling / Veo / ElevenLabs 生成真实短剧镜头。
