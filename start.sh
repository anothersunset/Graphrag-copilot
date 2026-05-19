#!/bin/bash
set -e
cd "$(dirname "$0")/backend"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 backend/.env，请填入 API Key 后重新执行 start.sh"
  exit 1
fi
mkdir -p data/raw data/processed data/vector_db data/graph_db
if ! python3 -c "import fastapi" 2>/dev/null; then
  pip3 install -r requirements.txt
fi
uvicorn main:app --reload --host 0.0.0.0 --port 8000
