# 服务评测材料

本目录保留服务评测脚手架、历史数据集与结果；确定性评测库位于 `packages/eval/`。

| 路径 | 用途 |
| --- | --- |
| `run_eval.py`、`run_eval_once.py` | 服务评测入口，从仓库根目录以 `python -m eval.run_eval` 等方式运行 |
| `graphrag_client.py`、`metrics.py`、`judge.py`、`ablation.py`、`ragas_runner.py` | 客户端、指标、裁判与消融支持 |
| `datasets/`、`questions.json` | 评测数据与 gold 映射 |
| `prompts/` | 评测提示词 |
| `tests/` | 离线单测与历史在线评测脚本；在线脚本需先启动对应服务 |
| `results/` | 已入库的评测结果与基线，保留原内容 |

旧版索引随应用迁至 `legacy/backend/data/`。完整报告见
[评测报告](../docs/evaluation/eval-report.md)。

正式确定性质量门（无需外部服务）：

```bash
uv run --package graphrag-eval python -m graphrag_eval.bench --strict
```
