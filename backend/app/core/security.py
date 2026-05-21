"""GraphRAG Copilot - API Key 认证依赖

使用方式：在 FastAPI 路由/路由器上增加依赖 `Depends(require_api_key)`。

安全红线（与 Notion 限制页、README 保持一致）：
- 真实 API Key 只能写在本地 .env （已被 .gitignore 排除）
- 仓库文件、demo、测试代码、commit message 中不出现真实密钥
- ENABLE_AUTH 默认 false，快速 Demo 不受影响；上线/公网部署请设为 true
"""
from typing import Optional

from fastapi import Header, HTTPException, status

from config.settings import settings
from app.core.logger import logger


def _allowed_keys() -> list[str]:
    raw = (settings.API_KEYS or "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI 依赖：验证 X-API-Key 请求头。

    返回值：
      - settings.ENABLE_AUTH == False 时返回 'auth_disabled'（不拦截）
      - 验证通过时返回该 key 本身

    报错：
      - 503：ENABLE_AUTH 开启但 API_KEYS 未配置（避免默默放行）
      - 401：缺少或不匹配的 X-API-Key
    """
    if not settings.ENABLE_AUTH:
        return "auth_disabled"

    allowed = _allowed_keys()
    if not allowed:
        logger.error("ENABLE_AUTH=true 但 API_KEYS 为空，拒绝请求以防止错误配置造成裸奔")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth enabled but no API keys configured",
        )

    if not x_api_key or x_api_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


__all__ = ["require_api_key"]
