# GraphRAG Copilot

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/qsm68p75m6-arch/Graphrag-copilot?style=flat-square)](https://github.com/qsm68p75m6-arch/Graphrag-copilot/stargazers)
[![GitHub license](https://img.shields.io/github/license/qsm68p75m6-arch/Graphrag-copilot?style=flat-square)](https://github.com/qsm68p75m6-arch/Graphrag-copilot/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)
[![CI](https://img.shields.io/github/actions/workflow/status/qsm68p75m6-arch/Graphrag-copilot/ci.yml?style=flat-square&label=CI)](https://github.com/qsm68p75m6-arch/Graphrag-copilot/actions)
[![Release](https://img.shields.io/github/v/release/qsm68p75m6-arch/Graphrag-copilot?style=flat-square)](https://github.com/qsm68p75m6-arch/Graphrag-copilot/releases)

</div>

> 面向企业知识库的多模态 GraphRAG + Multi-Agent 检索增强生成系统

## 核心特性
- 多模态文档解析：PDF / DOCX / PPTX / 图片 OCR / 音视频 ASR
- 混合检索：FAISS 向量 + BM25 关键词 + Neo4j 知识图谱
- Multi-Agent 编排：查询理解 -> 检索 -> 推理 -> 验证 -> 生成
- 可解释 & 抗幻觉：附带来源引用、置信度、推理路径
- 优雅降级：Neo4j / LLM / Embedding 单点故障不会拖垮系统
- 工程化完备：Docker Compose、pytest、eval 脚本、前端演示闭环

## 技术栈
- 后端：Python 3.11+ / FastAPI 0.115 / Uvicorn
- LLM：智谱 GLM-4-Flash（OpenAI 兼容 SDK）
- 向量库：FAISS (IndexFlatIP)
- 图数据库：Neo4j 5.x (APOC)
- 嵌入：BAAI/bge-small-zh-v1.5 (dim 512)
- 检索：jieba + rank-bm25
- 前端：Next.js 16 / React 19 / Tailwind CSS 4
- 容器：Docker + Docker Compose

## 快速启动（本地）
```

cd backend

cp .env.example .env   # 填入 ZHIPU_API_KEY

pip install -r requirements.txt

uvicorn main:app --reload --port 8000

```

## 快速启动（Docker）
```

cp backend/.env.example backend/.env

docker-compose up -d

```

## 测试
```

cd backend && pytest -q

python eval/run_eval.py

```

## API
启动后访问 http://localhost:8000/docs 。

## License
MIT
