#!/usr/bin/env bash
# Activate GitHub Actions workflows by rendering templates from
# infra/workflows-template/*.yml.tmpl into .github/workflows/*.yml.
#
# Why this script exists: see infra/workflows-template/README.md
# Short version: the AI agent cannot write to .github/workflows/*
# (the MCP integration's GitHub App lacks workflows:write scope),
# and the agent's tool-call serializer corrupts double-curly-brace
# tokens. Templates use __GHA_OPEN__/__GHA_CLOSE__ sentinels; this
# script restores them and you push the result from your own account.
#
# Usage:
#   bash scripts/install-workflows.sh
#   git add .github/workflows/
#   git commit -m 'ci: activate workflows from templates'
#   git push
#
# Idempotent: re-running overwrites .github/workflows/*.yml with the
# current template contents. Edit the .tmpl files, never the rendered
# yml directly.

set -euo pipefail

# Build the literal '$' '{' '{' and '}' '}' tokens via shell string
# concatenation. This avoids putting consecutive curly braces in any
# string that the AI agent might serialize, and also avoids accidental
# shell parameter expansion of $ {something} when rendering.
OPEN='$''{''{'
CLOSE='}''}'

TEMPLATE_DIR="infra/workflows-template"
TARGET_DIR=".github/workflows"

if [ ! -d "$TEMPLATE_DIR" ]; then
    printf 'error: %s not found (run from repo root)\n' "$TEMPLATE_DIR" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

shopt -s nullglob
templates=("$TEMPLATE_DIR"/*.yml.tmpl)
shopt -u nullglob

if [ ${#templates[@]} -eq 0 ]; then
    printf 'error: no templates found in %s\n' "$TEMPLATE_DIR" >&2
    exit 1
fi

count=0
for tmpl in "${templates[@]}"; do
    base=$(basename "$tmpl" .tmpl)
    out="$TARGET_DIR/$base"
    sed -e "s|__GHA_OPEN__|${OPEN}|g" -e "s|__GHA_CLOSE__|${CLOSE}|g" "$tmpl" > "$out"
    printf 'installed: %s\n' "$out"
    count=$((count + 1))
done

printf '\ndone: %d workflow(s) installed\n\n' "$count"
printf 'next steps:\n'
printf '  git add %s/\n' "$TARGET_DIR"
printf "  git commit -m 'ci: activate workflows from templates'\n"
printf '  git push\n'
