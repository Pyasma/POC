# Kyverno Maintainer Assistant POC

> **CNCF Mentorship POC**: *AI Maintainer Assistant for Kyverno (2026 Term 3)*

## Video Demo


## Problem

Kyverno maintainers spend real time on repetitive PR work: review comments, triage, rebase checks, and follow-up nudges. That work is necessary, but it steals time from code review and design.

## Solution

**GitHub App + FastAPI + Daytona** that listens for PR events, classifies change types, runs commands inside a sandbox, and posts a maintainer-style review on the source PR.

## Architecture

<img width="978" height="760" alt="image" src="https://github.com/user-attachments/assets/53fb7f3e-e1c1-4350-a4eb-4f2b8eb7ed3d" />


## Workflow

1. PR opened or synchronized on source repo
2. Webhook received, diff fetched, files classified
3. Diff + prompt uploaded to Daytona sandbox
4. Sandbox runs `hermes install` or your configured command
5. Review text posted back on source PR

## Classification

| Pattern | Type | Impact |
|---|---|---|
| `config.yaml`, `settings.json` | config_fields | Parameter tables |
| `scenarios/` | new_scenario | Scenario page |
| `cmd/`, `cli/`, `flag` | cli_flags | Flag reference |
| `README.md`, `docs/` | doc_update | Sync to website |
| `*.go` | code_change | May need review |
| `api/`, `proto/`, `openapi` | api_change | API reference update |

## Setup

```bash
uv sync
# Required for GitHub webhook auth:
#   GITHUB_APP_ID, WEBHOOK_SECRET
#
# Required for Daytona mode:
#   DAYTONA_API_KEY, DAYTONA_TARGET, DAYTONA_AGENT_COMMAND
#
# Optional:
#   DAYTONA_API_URL, DAYTONA_SNAPSHOT, DAYTONA_REPO_NAME,
#   DAYTONA_BOOTSTRAP_COMMANDS, DAYTONA_DIFF_PATH,
#   DAYTONA_AGENT_TIMEOUT
uv run uvicorn main:app --reload --port 8080
# Expose: gh webhook forward --port=8080  or  smee -u https://smee.io/your-channel -P http://localhost:8080/webhook
```

## Run

1. Install dependencies:

```bash
uv sync
```

2. Set environment variables in `.env` or shell.

Example `.env`:

```bash
GITHUB_APP_ID=123456
WEBHOOK_SECRET=your-webhook-secret

DAYTONA_API_KEY=your-daytona-key
DAYTONA_API_URL=https://app.daytona.io/api
DAYTONA_TARGET=us
DAYTONA_SNAPSHOT=daytona-small
DAYTONA_AGENT_COMMAND=hermes install
DAYTONA_BOOTSTRAP_COMMANDS=
```

3. Start server:

```bash
uv run uvicorn main:app --reload --port 8080
```

4. Forward GitHub webhooks to `/webhook`.

```bash
gh webhook forward --port 8080
```

5. Send PR event for any PR in the target repo.

6. Watch bot post review comment on source PR.

## Notes

- If `DAYTONA_API_KEY` is missing, app still runs and posts deterministic fallback review text.
- Default review target comes from webhook payload.

## Daytona Flow

- `main.py` fetches PR diff and changed files
- `daytona_tools.py` creates sandbox, uploads `diff.patch`, `task.json`, and `prompt.txt`
- Sandbox runs bootstrap commands first, then `DAYTONA_AGENT_COMMAND`
- Output becomes PR review text
- If `DAYTONA_API_KEY` is missing, code falls back to a local deterministic review note

## Key Decisions

- **GitHub App, not Actions**: Cross-repo write access and better webhook handling
- **FastAPI, not serverless**: Easier to debug during the POC
- **Review comments first**: Main flow posts review notes on source PR

## POC Status

**Working**: Webhook events, diff fetching, change classification, source-PR review comments, HMAC verification

**Simplifications**: Only `opened` and `synchronize` events, fallback review text when Daytona is unavailable

**For Production**: Sandboxed agent runtime, inline diff comments, dynamic file targeting, multi-repo support, smarter content merging, preview deploys

## Project Structure

```text
POC/
├── main.py              # FastAPI server
├── github_tools.py      # GitHub API wrapper
├── config.py            # App config
├── test.py              # Test script
├── pyproject.toml       # Dependencies
├── .env                 # Secrets
├── sample.diff          # Sample diff
├── agent.log / parsed_agent.log  # Cached AI output
├── daytona_tools.py     # Daytona sandbox runner
└── POC.mp4              # Demo video
```

## License

Apache License 2.0 - part of the CNCF Mentorship program.
