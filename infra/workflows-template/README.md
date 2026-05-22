# Workflow templates

This directory holds **template versions** of the repository's GitHub Actions workflows. They are activated by running [`scripts/install-workflows.sh`](../../scripts/install-workflows.sh) from a local clone and pushing from your own git account.

## Why this exists

Two unrelated constraints stack:

1. **The Notion GitHub MCP integration's underlying GitHub App does not declare `workflows:write` scope.** When the AI agent calls the GitHub API to write under `.github/workflows/*`, the response is a hard `403 Resource not accessible by integration` regardless of OAuth state. Verified across two integration reconnects and confirmed by reading the integration's permission spec.

2. **The agent's tool-call serialization layer corrupts double-curly-brace tokens** in any string it sends. The string `$  github.ref ` arrives at the API as `$ github.ref` (braces stripped). So even if the agent could write to `.github/workflows/`, the workflows would be broken GitHub Actions YAML.

## How the templates fix both problems

- **Constraint 1** (path scope): we store YAMLs under a path that doesn't trigger the GitHub App's workflow-write enforcement. `infra/workflows-template/*.yml.tmpl` is a regular file path; the agent has standard `contents:write` here.

- **Constraint 2** (expression corruption): expressions like `$  github.ref ` and `$  matrix.python ` are stored as **sentinel tokens** that pass cleanly through serialization:

  | In template | After `install-workflows.sh` |
  |---|---|
  | `__GHA_OPEN__ github.ref __GHA_CLOSE__` | `$  github.ref ` |
  | `__GHA_OPEN__ matrix.python __GHA_CLOSE__` | `$  matrix.python ` |

  The install script restores them via `sed`, building the literal `$ ` and `` characters via shell string concatenation so they also avoid the same corruption inside the script itself.

## Activation (one command, ~30 seconds)

From a local clone of the repo (your shell, your push credentials):

```bash
bash scripts/install-workflows.sh
git add .github/workflows/
git commit -m "ci: activate workflows from templates"
git push
```

After the push, all three workflows (Python / Frontend / Docs) run on every PR including the one that activated them.

## Future workflows

W2 docker-build, W5 ragas-eval, W8 release-please will land here too. The same `bash scripts/install-workflows.sh` step re-syncs all templates idempotently — it overwrites existing files in `.github/workflows/`, so running it after adding a new template just installs the new one (plus any existing ones, identically).

## Editing a workflow

Edit the `.tmpl` (canonical source), then re-run `bash scripts/install-workflows.sh` and commit both files. Do not edit `.github/workflows/*.yml` directly — your edit will be lost the next time someone runs the install script.

## Why not just have me (the human) write workflows directly?

You can. But keeping them templated:
- Documents the AI-agent boundary explicitly, so the next person who tries to use the agent for CI changes won't waste an hour figuring out why their edits 403.
- Lets the agent propose workflow changes (by editing `.tmpl` files), which a human then validates + activates.
