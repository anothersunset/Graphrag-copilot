# GraphRAG Copilot - Windows PowerShell 启动脚本
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\backend

# 检查 .env
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "已生成 backend/.env，请填入 LLM_API_KEY（DeepSeek）后重新运行 start.ps1" -ForegroundColor Yellow
    exit 1
}

# 创建数据目录
New-Item -ItemType Directory -Force -Path data\raw, data\processed, data\vector_db, data\graph_db | Out-Null

# 检查依赖
try { python -c "import fastapi" 2>$null }
catch {
    Write-Host "安装依赖中..." -ForegroundColor Cyan
    pip install -r requirements.txt
}

# 启动服务
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
