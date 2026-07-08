# core-logger 模块文档

## 概述

`logger` 模块是 GraphRAG Copilot 的集中式日志服务，基于 `loguru` 库实现，提供统一的日志格式和文件轮转。模块位于 `backend/app/core/logger.py`，通过 `from app.core.logger import logger` 引用，替代项目中的 `print()` 和 `traceback.print_exc()`。

## 日志级别

通过环境变量 `LOG_LEVEL` 控制（默认 `"INFO"`），读取后转为大写。支持标准级别：DEBUG、INFO、WARNING、ERROR、CRITICAL。

## 输出目标

### 控制台输出（stderr）

- 输出到 `sys.stderr`
- 格式：`<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>`
- 启用彩色输出（`colorize=True`）
- 关闭 backtrace 和 diagnose（避免控制台信息过载）

### 文件输出

- 路径：`{LOG_DIR}/app.log`，其中 `LOG_DIR` 优先取环境变量，否则默认为 `backend/data/logs/`
- **轮转策略**: 文件大小达到 **10 MB** 时轮转（`rotation="10 MB"`）
- **保留策略**: 保留最近 **14 天** 的日志（`retention="14 days"`）
- 编码：UTF-8
- 异步写入：`enqueue=True`，避免日志 I/O 阻塞主线程
- 启用 backtrace（文件中保留完整堆栈），关闭 diagnose
- 格式：`{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}`（无颜色标记）

## 初始化流程

1. 读取 `LOG_LEVEL` 环境变量
2. 确定日志目录（`LOG_DIR` 环境变量 > 默认 `data/logs/`）
3. 尝试创建日志目录，失败则将 `_LOG_DIR` 设为 `None`（不阻断应用启动）
4. 调用 `_logger.remove()` 移除 loguru 默认处理器
5. 添加 stderr 处理器
6. 若日志目录可用，添加文件处理器

## 日志目录容错

日志目录创建失败时（权限不足等），文件处理器不会添加，但应用正常启动。仅控制台日志可用。

## 使用方式

```python
from app.core.logger import logger

logger.info("Processing file: {}", file_name)
logger.error("Failed to connect: {}", error)
logger.exception("Unexpected error")  # 自动附带异常堆栈
```

loguru 的 `{}` 占位符语法替代 `%s` 或 f-string，在日志未输出时避免字符串格式化开销。
