# core-security 模块文档

## 概述

`security` 模块是 GraphRAG Copilot 的 API 认证与访问控制层，基于 FastAPI 依赖注入实现。模块位于 `backend/app/core/security.py`，提供 `require_api_key` 依赖函数。

## require_api_key 依赖

```python
async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str
```

FastAPI 依赖函数，用于在路由级别验证 API Key。使用方式：在路由装饰器或路由器上添加 `dependencies=[Depends(require_api_key)]`。

### 认证流程

1. **检查 ENABLE_AUTH 开关**：若 `settings.ENABLE_AUTH == False`（默认），直接返回 `"auth_disabled"`，不拦截任何请求。该设计保证本地开发和 Demo 场景零配置可用。

2. **验证 API_KEYS 配置**：若 ENABLE_AUTH 为 True 但 `API_KEYS` 为空，返回 **503 Service Unavailable**。这是安全兜底，避免"认证已开启但无密钥"导致的裸奔。

3. **验证请求头**：检查 `X-API-Key` 请求头是否在允许列表中。缺少或不匹配返回 **401 Unauthorized**，响应头包含 `WWW-Authenticate: ApiKey`。

### API_KEYS 格式

`API_KEYS` 环境变量为逗号分隔的字符串，由 `_allowed_keys()` 函数解析：

```python
def _allowed_keys() -> list[str]:
    raw = (settings.API_KEYS or "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()]
```

示例：`API_KEYS=key1,key2,key3`。空白项会被自动过滤。

## SlowAPIMiddleware 速率限制

在 FastAPI 应用层通过 `slowapi` 库实现基于 IP 的速率限制：

- 默认限制：`settings.RATE_LIMIT_PER_MIN = 60` 次/分钟/每 IP
- 超限返回 **429 Too Many Requests**
- 限流装饰器应用于需要保护的路由

## 安全设计原则

1. **默认开放，按需启用**：`ENABLE_AUTH` 默认为 `False`，降低本地开发门槛
2. **Fail-safe 设计**：认证开启但未配置密钥时拒绝请求（503），而非默默放行
3. **密钥不入库**：真实 API Key 只能写在 `.env` 文件中（已被 `.gitignore` 排除），仓库代码、测试、文档中不得出现真实密钥
4. **Header 规范**：使用标准 `X-API-Key` 自定义请求头，别名通过 FastAPI 的 `Header(alias=...)` 映射

## 使用示例

```python
from app.core.security import require_api_key

@router.post("/documents/upload", dependencies=[Depends(require_api_key)])
async def upload_document(file: UploadFile = File(...)):
    ...
```

所有需要认证的路由（upload、query、stream）均已添加该依赖。
