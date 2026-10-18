# service-llm 模块文档

## 概述

`LLMService` 是 GraphRAG Copilot 的大语言模型调用服务，通过 OpenAI 兼容 API 统一接入多种 LLM。模块位于 `backend/app/services/llm_service.py`，通过单例 `llm_service` 对外提供服务。

## 模型配置

初始化时按优先级选择 LLM 提供商：

1. **智谱 GLM**: 若 `ZHIPU_API_KEY` 环境变量存在，使用智谱 API（`ZHIPU_BASE_URL`，默认 `https://open.bigmodel.cn/api/paas/v4`），模型固定为 `glm-4-flash`
2. **通用 OpenAI 兼容**: 否则使用 `settings.LLM_API_KEY` 和 `settings.LLM_BASE_URL`，模型为 `settings.LLM_MODEL`

客户端参数：
- `timeout=120.0` 秒
- `max_retries=3`

## chat() 方法

```python
def chat(self, messages: List[Dict[str, str]], **kwargs) -> str
```

核心 LLM 调用方法，支持重试机制：

- **重试条件**: `RateLimitError`、`APIConnectionError`、`ConnectionError`、`ConnectionResetError`、空返回内容
- **退避策略**: 指数退避，限流错误等待 5s/10s/20s，空内容等待 3s/6s/12s
- **最大重试**: 3 次
- 支持通过 kwargs 覆盖 `model`、`temperature`（默认 0.3）、`max_tokens`（默认 4096）

## chat_stream() 方法

```python
def chat_stream(self, messages, **kwargs) -> Generator[str, None, None]
```

流式调用 LLM，逐 token yield。设置 `stream=True`，遍历 chunk 提取 `delta.content`。异常时 yield 错误信息而非抛出异常。

## chat_json() 方法

```python
def chat_json(self, messages, **kwargs) -> Dict[str, Any]
```

在 `chat()` 基础上调用 `extract_json_object()` 从 LLM 返回文本中提取 JSON 对象。用于需要结构化输出的场景。

## extract_entities() 方法

```python
def extract_entities(self, text: str) -> Dict[str, Any]
```

知识图谱实体抽取专用方法：

- **System Prompt**: 指示 LLM 作为知识图谱抽取专家，输出 JSON 格式
- **输入**: 文本前 3000 字符
- **输出结构**:
  - `entities`: 列表，每项含 `name`、`type`（9 种实体类型）、`confidence`、`properties`
  - `relations`: 列表，每项含 `source`、`target`、`type`（10 种关系类型）、`confidence`、`properties`

## verify_answer() 方法

```python
def verify_answer(self, question, answer, sources) -> Dict[str, Any]
```

答案验证方法，检查 LLM 生成的答案是否被来源文档支持：

- **输入**: 原始问题、生成答案、来源文本列表
- **System Prompt**: 指示 LLM 作为答案验证专家
- **输出结构**:
  - `is_supported`: bool，答案是否被来源支持
  - `hallucination_detected`: bool，是否检测到幻觉
  - `confidence`: float，验证置信度
  - `issues`: list，问题列表
  - `source_mapping`: dict，答案与来源的映射关系

## 错误处理

所有公开方法均有异常捕获和日志记录。chat() 在重试耗尽后抛出原始异常，chat_stream() 在异常时 yield 错误文本而非崩溃。
