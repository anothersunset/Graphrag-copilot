# GraphRAG Copilot — 项目结构

```
Graphrag-copilot/
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions CI：pytest + ruff lint + frontend build
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── orchestrator.py        # Multi-Agent 编排：Query → Retrieval → Reasoning → Verification → Generation
│   │   ├── api/
│   │   │   ├── routes.py              # FastAPI 路由：upload / query / graph / vector / system
│   │   │   └── schemas.py             # Pydantic 请求/响应模型
│   │   ├── core/
│   │   │   └── constants.py           # 全局常量：文件类型、实体/关系白名单
│   │   ├── services/
│   │   │   ├── bm25_store.py          # BM25 关键词检索 (jieba + rank-bm25)
│   │   │   ├── document_parser.py     # 多模态文档解析 (PDF/DOCX/PPTX/图片/音视频)
│   │   │   ├── evidence_fusion.py     # 多路证据融合 & 去重排序
│   │   │   ├── kg_service.py          # Neo4j 知识图谱服务 (CRUD / 邻居查询 / 路径查找)
│   │   │   ├── llm_service.py         # LLM 调用封装 (智谱 GLM-4-Flash / OpenAI 兼容)
│   │   │   └── vector_store.py        # FAISS 向量存储 + SentenceTransformer Embedding
│   │   └── utils/
│   │       └── json_utils.py          # LLM JSON 回复容错解析
│   ├── config/
│   │   └── settings.py                # Pydantic Settings：全部环境配置
│   ├── data/
│   │   ├── raw/                       # 原始上传文件 (.gitkeep)
│   │   ├── processed/                 # 已处理文档 (.gitkeep)
│   │   ├── vector_db/                 # FAISS 索引持久化 (.gitkeep)
│   │   └── graph_db/                  # 图谱导出 (.gitkeep)
│   ├── tests/
│   │   ├── test_bm25_store.py         # BM25 检索单测
│   │   ├── test_evidence_fusion.py    # 证据融合单测
│   │   ├── test_fallback.py           # Neo4j 降级单测
│   │   └── test_orchestrator_trace.py # Multi-Agent 全链路 mock 测试
│   ├── .env.example                   # 环境变量模板
│   ├── Dockerfile                     # 后端 Docker 镜像
│   ├── main.py                        # FastAPI 入口（lifespan / CORS / router）
│   └── requirements.txt              # Python 依赖
├── demo_docs/
│   ├── company_ai_strategy.md         # 演示文档：公司 AI 战略
│   ├── product_architecture.md        # 演示文档：产品架构
│   └── risk_review.md                 # 演示文档：风险评审
├── eval/
│   ├── questions.json                 # 评估题库 (5 题 × 4 类型)
│   ├── run_eval.py                    # 关键词命中率评估脚本
│   └── results/                       # 评估结果输出 (.gitkeep)
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── chat/
│   │       │   └── page.tsx           # 智能问答页 (流式交互)
│   │       ├── graph/
│   │       │   └── page.tsx           # 知识图谱可视化页
│   │       ├── status/
│   │       │   └── page.tsx           # 系统状态监控页
│   │       ├── upload/
│   │       │   └── page.tsx           # 文档上传页 (拖拽上传)
│   │       ├── globals.css            # Tailwind + 自定义动画
│   │       ├── layout.tsx             # 全局布局 & 导航栏
│   │       └── page.tsx               # 首页 (Hero + 功能卡片 + 架构流程)
│   ├── Dockerfile                     # 前端 Docker 镜像
│   ├── eslint.config.mjs              # ESLint 配置
│   ├── next-env.d.ts                  # Next.js TypeScript 声明
│   ├── next.config.ts                 # Next.js 配置
│   ├── package.json                   # Node 依赖 (Next.js 16 / React 19 / Tailwind CSS 4)
│   ├── postcss.config.mjs             # PostCSS 配置
│   └── tsconfig.json                  # TypeScript 配置
├── .gitignore                         # Git 忽略规则
├── docker-compose.yml                 # 三容器编排 (Neo4j + Backend + Frontend)
├── PROJECT_STRUCTURE.md               # 本文件
├── README.md                          # 项目文档 + Badges
├── start.sh                           # 一键启动脚本
└── test_api.py                        # API 集成测试脚本
```

## 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **LLM** | 智谱 GLM-4-Flash | — | 对话生成 / 实体抽取 / 答案验证 |
| **Embedding** | BAAI/bge-small-zh-v1.5 | dim 512 | 文本向量化 |
| **向量库** | FAISS | 1.8.0 | IndexFlatIP 内积检索 |
| **图数据库** | Neo4j | 5.x | 知识图谱存储 / 邻居查询 / 路径查找 |
| **关键词检索** | rank-bm25 + jieba | — | BM25 中文分词检索 |
| **后端框架** | FastAPI | 0.115.0 | REST API + CORS + 文件上传 |
| **前端框架** | Next.js | 16 | React 19 + Tailwind CSS 4 |
| **容器化** | Docker Compose | 3.8 | Neo4j + Backend + Frontend |
| **CI** | GitHub Actions | — | pytest + ruff + frontend build |
| **Python** | Python | 3.11+ | 后端运行时 |

## 核心数据流

```
用户查询 → QueryUnderstandingAgent (意图/实体识别)
         → RetrievalAgent (并行: FAISS + BM25 + Neo4j)
         → EvidenceFusionService (去重/加权/压缩)
         → ReasoningAgent (多跳推理 + 来源标注)
         → VerificationAgent (事实校验 / 幻觉检测)
         → GenerationAgent (最终回答 + 置信度 + 引用)
```

## 优雅降级策略

| 故障组件 | 降级行为 |
|----------|----------|
| **Neo4j** | FAISS + BM25 双路继续，图谱返回 `disconnected` |
| **LLM** | 返回原始检索证据 + 错误提示，不编造 |
| **Embedding** | md5 hash 备选向量，向量检索仍可用（精度降低） |
| **FAISS** | BM25 关键词检索独立工作 |
