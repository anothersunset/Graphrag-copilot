# service-parser 模块文档

## 概述

`DocumentParser` 是 GraphRAG Copilot 的多模态文档解析服务，负责将上传的文件解析为统一的文本格式。模块位于 `backend/app/services/document_parser.py`，通过单例 `doc_parser` 对外提供服务。

## 支持的文件格式

解析器通过 `supported_formats` 字典映射文件后缀到对应的解析方法：

- **文档类**: `.pdf`（PyPDF2）、`.docx`（python-docx）、`.pptx`（python-pptx）、`.txt`、`.md`
- **图片类**: `.jpg`、`.jpeg`、`.png`（PaddleOCR，`lang="ch"`）
- **音视频类**: `.mp4`、`.wav`、`.mp3`（Whisper ASR，`language="zh"`）

其中 `parse_audio` 直接复用 `parse_video` 的 Whisper 转录逻辑。

## 文件哈希计算

`_calculate_hash(path)` 方法使用 `hashlib.sha256` 对文件内容进行分块读取（每次 4096 字节），生成唯一的文件指纹（hexdigest）。该哈希值存储在返回结果的 `file_hash` 字段中，用于文档去重和索引关联。

## 文本分块

`chunk_text(text, chunk_size=None, overlap=None)` 方法将长文本切分为重叠片段：

- **chunk_size**: 默认 `settings.CHUNK_SIZE = 512` 字符
- **overlap**: 默认 `settings.CHUNK_OVERLAP = 50` 字符
- 算法：滑动窗口，步长 = chunk_size - overlap。若文本长度不超过 chunk_size，直接返回单个块。

## 解析输出结构

`parse(file_path)` 返回统一的字典结构：

```python
{
    "file_path": str,       # 绝对路径
    "file_name": str,       # 文件名
    "file_type": str,       # 后缀（如 ".pdf"）
    "file_hash": str,       # SHA256 hexdigest
    "content": {            # 含 type、full_text 及格式特有字段
        "type": str,
        "full_text": str,
        # PDF: total_pages, pages; DOCX: paragraphs, tables; PPTX: total_slides, slides
        # Image: ocr_results; Video: duration, segments
    },
    "metadata": {"size": int, "modified": float}
}
```

## PDF 解析细节

`parse_pdf` 使用 `pypdf2.PdfReader` 逐页提取文本，返回 `total_pages`、`pages`（含页码和内容的列表）以及拼接后的 `full_text`。空页会被跳过。

## DOCX 解析细节

`parse_docx` 使用 `python-docx` 提取段落和表格。段落通过 `doc.paragraphs` 获取，表格通过 `doc.tables` 遍历每行每格。`full_text` 为所有非空段落的双换行拼接。

## OCR 与 ASR

- 图片解析使用 `PaddleOCR(use_angle_cls=True, lang="ch")`，返回每个识别行的文本、置信度和边界框。
- 音视频解析使用 Whisper（模型由 `settings.ASR_MODEL` 指定，默认 `"base"`），返回时间片段（start/end/text）和全文。
