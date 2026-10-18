# Notion 同步快照

`notion_generated.json` 是原 `src/notion_generated.py` 的原始数据快照，当前内容为 JSON `null`。
按数据文件保存，避免被误认为 Python 业务模块。

仓库没有随此快照提供可执行的同步任务。外部同步器若仍配置旧输出路径，
需将输出目标改为 `integrations/notion/notion_generated.json`。
