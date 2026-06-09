"""GraphRAG Copilot 评测脚手架 v3.2.

职责: 加载 benchmark → 调用被测系统 → 计算三层指标 → LLM judge → 输出 JSON 报告。
红线: confidence 只记录不进指标; 结果表留空待回填; 不造满分。
"""
__version__ = "3.2.0"
