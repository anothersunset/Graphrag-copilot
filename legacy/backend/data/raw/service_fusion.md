# service-fusion 模块文档

## 概述

`EvidenceFusionService` 是 GraphRAG Copilot 的证据融合服务，负责将向量检索、BM25 检索和知识图谱三种来源的结果进行加权合并与去重。模块位于 `backend/app/services/evidence_fusion.py`，通过单例 `evidence_fusion_service` 对外提供服务。

## fuse() 方法

```python
def fuse(self, vector_results, bm25_results, graph_results, top_k=10) -> List[Dict]
```

融合流程分为三个阶段：

### 1. 候选收集

- **向量结果**: 直接取 `content`、`metadata.file_name`，类型标记为 `"vector"`，分数取 `doc.score`。
- **BM25 结果**: 过滤掉 `score < 0.1` 的低分噪声，类型标记为 `"bm25"`。
- **图谱结果**: 取 `graph_results["related_contexts"]` 前 10 条，内容格式为 `"实体: {name}; 类型: {type}; 图谱距离: {distance}"`，分数计算为 `0.7 / max(distance, 1.0)`，类型标记为 `"graph"`。

### 2. 去重与加权合并

使用 `_fingerprint(content)` 生成去重 key：将内容规范化（去除多余空白、截取前 500 字符）后取 `hashlib.md5` hexdigest。

每个候选的加权分数 = `base_score * type_weight`，其中 type_weight 来自配置：

| 来源 | type_weight | 配置键 |
|------|-------------|--------|
| vector | 0.55 | `VECTOR_WEIGHT` |
| bm25 | 0.15 | `BM25_WEIGHT` |
| graph | 0.30 | `GRAPH_WEIGHT` |

同一 fingerprint 出现多次时，fusion_score 累加，matched_by 列表合并（如 `["vector", "bm25"]`）。

### 3. 排序与截断

按 `fusion_score` 降序排列，返回前 `top_k`（默认 10）条结果。

## compress_context() 方法

```python
def compress_context(self, evidences, max_chars=6000) -> List[Dict]
```

将融合后的证据列表压缩到指定字符数上限（默认 6000 字符），用于 LLM 上下文窗口控制：

- 遍历证据列表，累计 `content` 长度
- 若剩余空间不足，截断当前条目的 `content`（不拆分条目）
- 超出上限后停止添加更多证据
- 返回压缩后的证据副本，保持原始排序

## 数据结构

融合后的每条证据包含：

```python
{
    "content": str,           # 证据文本
    "source": str,            # 来源文件名或 "knowledge_graph"
    "type": str,              # "vector" / "bm25" / "graph"
    "score": float,           # 原始分数
    "metadata": dict,         # 原始元数据
    "fusion_score": float,    # 加权融合分数
    "matched_by": List[str],  # 命中的来源类型列表
}
```
