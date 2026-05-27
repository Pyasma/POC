# 🤖 Krkn Chaos — Automated Documentation Sync Bot (POC)

> **Proof of Concept** for the CNCF Mentorship project: *krkn-chaos: Automated Documentation Sync Bot for Krkn-Chaos Projects (2026 Term 2)*

This is a **working POC** showing the end-to-end approach. 
for the Automation Documenting the krkn 

---

## The Problem

The [krkn-chaos/website](https://github.com/krkn-chaos/website) repository hosts unified documentation for the entire krkn-chaos ecosystem (krkn, krkn-hub, krknctl, krkn-ai, krkn-operator, cerberus, etc.) as a Hugo/Docsy site deployed at [krkn-chaos.dev](https://krkn-chaos.dev).

Right now, when a developer:
- Adds a new chaos scenario
- Modifies CLI flags
- Changes config fields or defaults
- Updates APIs or protobuf definitions
- Fixes a bug that changes behavior

...someone has to **manually open a PR** against the website repo to update the corresponding documentation. This is:
- **Tedious** — repetitive manual work
- **Easy to forget** — docs drift silently out of sync
- **Error-prone** — details get lost in translation

## The Solution

A **GitHub App + FastAPI webhook server** that:

1. **Listens** for PR events on upstream krkn repos
2. **Analyzes** the diff and classifies the change type (config, CLI, scenario, API, etc.)
3. **Generates** Hugo/Docsy markdown content using an LLM (Gemini) based on the diff
4. **Creates** a draft PR on the website repo with the auto-generated documentation
5. **Refines** the PR interactively via `/doc-update` commands in PR comments

---

## Architecture


![alt text](image.png)


## Workflow (Step by Step)

### A. Automatic PR Generation

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐    ┌──────────────┐
│  Upstream │    │   Webhook    │    │   FastAPI     │    │  Gemini   │    │   Website    │
│  PR       │───>│  (GitHub)    │───>│   Server      │───>│  Agent    │───>│   Draft PR   │
│  Merged   │    │              │    │               │    │           │    │              │
└──────────┘    └──────────────┘    │ 1. Parse PR    │    │ Gen Hugo  │    │  (auto-docs/ │
                                    │ 2. Fetch diff  │    │ markdown  │    │   pr-{n})    │
                                    │ 3. Classify    │    └───────────┘    └──────────────┘
                                    │ 4. Call agent  │
                                    │ 5. Create       │
                                    │    branch+file  │
                                    │ 6. Open draft PR│
                                    └──────────────┘
```

### B. Interactive Refinement

Once the draft PR is open, anyone can refine it by commenting:

```
/doc-update Add a note about the new --timeout flag defaulting to 60s
```

The bot:
1. Acknowledges the instruction
2. Reads the current file content from the PR branch
3. Calls Gemini to refine the content
4. Pushes the update to the same branch (PR updates automatically)
5. Comments when done

```
/doc-update Add a note about the new --timeout flag defaulting to 60s
                │
                ▼
┌──────────────────────────────┐
│  FastAPI Server              │
│                              │
│  1. Parse /doc-update cmd    │
│  2. Get current file content │
│  3. Call Gemini with         │
│     instruction                │
│  4. Push updated content     │
│  5. Comment "✅ Done"        │
└──────────────────────────────┘
```

---

## Change Classification

The bot classifies documentation-impacting changes by analyzing file paths in the PR:

| Pattern | Detected Type | Documentation Impact |
|---|---|---|
| `config.yaml`, `settings.json`, `defaults.toml` | `config_fields` | New/updated configuration fields → parameter tables |
| `scenarios/`, `/scenario` | `new_scenario` | New chaos scenario → scenario page with tabbed layout |
| `cmd/`, `cli/`, `flag`, `viper` | `cli_flags` | CLI flag changes → flag reference table |
| `README.md`, `docs/` | `doc_update` | Existing docs changed → sync to website |
| `*.go` | `code_change` | General code changes → may need doc review |
| `api/`, `proto/`, `openapi` | `api_change` | API definition changes → API reference update |

---

## POC Status & Scope

This is a **minimum-viable POC** demonstrating the concept. Here's what's working and what's intentionally limited:

### ✅ Working
- Webhook receives `pull_request` events (opened + synchronize)
- Fetches PR diffs and changed file lists
- Classifies change types
- Creates branches on the website fork
- Pushes generated content as a new file commit
- Opens **draft PRs** on the website fork
- Interactive `/doc-update` refinement via PR comments
- Webhook signature verification (HMAC-SHA256)

### ⚠️ POC Simplifications
- **Target file is hardcoded** to `content/en/docs/chaos-testing-guide/_index.md` — in production, the bot would pick the right file based on the change type
- **AI agent is cached** — the Gemini call is commented out in favor of loading from `parsed_agent.log` (the POC ran it once and cached the result so you don't need API keys to test the flow)
- **Only handles `opened` / `synchronize`** — production would also handle `closed` (merge) events to trigger generation
- **Writes to a fork** (Pyasma/website) instead of the actual krkn-chaos/website — same logic, different org

### 🔜 For Production
- Trigger on **PR merge** (`pull_request.closed` with `merged: true`) instead of open/sync
- **Dynamic file targeting** — map changed source files to the correct Hugo content path
- Support for **all upstream repos** (krkn-hub, krknctl, krkn-ai, etc.)
- **Smarter content merging** — insert into the right section instead of appending
- **Handle PR review comments** — CodeRabbit-style threaded refinement
- **Configurable watch list** — which repos/branches trigger the bot
- **Preview deployment** — link to a deploy preview in the draft PR

---

## Project Structure

```
POC/
├── main.py              # FastAPI webhook server (event handlers + AI agent)
├── github_tools.py      # GitHub API wrapper (auth, diff, branches, PRs, files)
├── config.py            # App config: org, repo, target file, GitHub App creds
├── test.py              # Standalone script to fetch a PR diff for testing
├── pyproject.toml       # Python project definition + dependencies
├── .env                 # GITHUB_APP_ID, WEBHOOK_SECRET, GEMINI_API_KEY, PA_TOKEN
├── krkn_pr_1261.diff    # Sample PR diff (krkn#1261) cached for testing
├── agent.log            # Raw Gemini response (cached)
├── parsed_agent.log     # Parsed JSON output from Gemini (cached)
└── README.md            # This file
```

---

## Setup & Run

```bash
# 1. Install dependencies
uv sync

# 2. Create a GitHub App:
#    - Permissions: Pull requests (read+write), Contents (read+write), Webhooks
#    - Subscribe to: pull_request, issue_comment
#    - Install the app on your upstream repo + website fork

# 3. Set environment variables (see .env.example):
#    GITHUB_APP_ID=<your-app-id>
#    WEBHOOK_SECRET=<webhook-secret>
#    GEMINI_API_KEY=<gemini-api-key>
#    PA_TOKEN=<personal-access-token-for-testing>

# 4. Run the server — exposes /webhook endpoint
uv run uvicorn main:app --reload --port 8080

# 5. Expose to GitHub (use smee.io, ngrok, or a public server):
#    gh webhook forward --port=8080
#    # or
#    smee -u https://smee.io/your-channel -P http://localhost:8080/webhook
```

---

## Key Design Decisions

### Why a GitHub App (not Actions)?

A **GitHub App** can write cross-repo — it creates branches and PRs on the website repo when triggered from an upstream repo. A **GitHub Action** is scoped to the repo it runs in, which would require setting up the action in every upstream repo and giving it cross-repo write access (more complex).

### Why FastAPI (not a serverless function)?

During a mentorship POC, it's easier to debug, iterate, and observe a long-running server than a serverless function. The same logic can be trivially ported to a Cloud Function / Lambda for production.

### Why Gemini for content generation?

The Hugo/Docsy site uses consistent patterns (tabbed scenario layouts, parameter tables, frontmatter). An LLM is well-suited to produce structured markdown that follows these conventions, and the `/doc-update` workflow enables human-in-the-loop refinement.

---

## License

This project is part of the CNCF Mentorship program. Licensed under the Apache License 2.0.
