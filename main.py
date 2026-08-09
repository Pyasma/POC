import os
import json
import hashlib
import hmac

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

import github_tools
from daytona_tools import (
    daytona_enabled,
    render_daytona_prompt,
    run_with_daytona,
)
from config import ORG, REPO, WEBSITE_ORG, WEBSITE_REPO

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


def build_basic_review_result(
    *,
    pr_number: int,
    pr_title: str,
    pr_body: str,
    diff_text: str,
    change_types: list[str],
    changed_files: list[str],
    source_repo: str,
) -> dict:
    """Deterministic fallback when Daytona is unavailable."""
    file_list = "\n".join(f"- `{path}`" for path in changed_files[:20]) or "- `No files detected`"
    diff_preview = diff_text.strip().splitlines()[:20]
    preview_text = "\n".join(diff_preview) if diff_preview else "No diff preview"
    review_body = f"""Review fallback for `{source_repo}#{pr_number}`.

**Title:** {pr_title}
**Change types:** {", ".join(change_types)}
**Files:**
{file_list}

**PR body:**
{pr_body or "No description provided."}

**Quick read:**
Diff present. Needs human review on behavior, tests, and rollout risk.

**Diff preview:**
```diff
{preview_text}
```"""
    return {
        "review_body": review_body,
        "pr_body": review_body,
        "generated_content": review_body,
        "commit_message": f"chore: review {source_repo}#{pr_number}",
        "backend": "fallback",
    }


def parse_agent_output(stdout: str) -> dict:
    """Normalize sandbox output into review text."""
    text = stdout.strip()
    if not text:
        return {}

    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if parsed:
            review_body = (
                parsed.get("review_body")
                or parsed.get("comment")
                or parsed.get("body")
                or parsed.get("pr_body")
                or text
            )
            return {
                "review_body": review_body,
                "pr_body": parsed.get("pr_body", review_body),
                "generated_content": parsed.get("generated_content", review_body),
                "commit_message": parsed.get("commit_message", "chore: sandbox review"),
                "backend": parsed.get("backend", "daytona"),
            }

    return {
        "review_body": text,
        "pr_body": text,
        "generated_content": text,
        "commit_message": "chore: sandbox review",
        "backend": "daytona",
    }


def run_review_agent(
    *,
    pr_number: int,
    pr_title: str,
    pr_body: str,
    diff_text: str,
    change_types: list[str],
    changed_files: list[str],
    source_repo: str,
    pr_payload: dict,
) -> dict:
    """Run Daytona first. Fall back to cached local agent."""
    prompt_text = render_daytona_prompt(
        pr_number=pr_number,
        source_repo=source_repo,
        pr_title=pr_title,
        pr_body=pr_body,
        change_types=change_types,
        changed_files=changed_files,
        diff_text=diff_text,
    )

    if daytona_enabled():
        try:
            sandbox_result = run_with_daytona(
                diff_text=diff_text,
                pr_payload=pr_payload,
                prompt_text=prompt_text,
            )
            parsed = parse_agent_output(sandbox_result.stdout)
            if parsed:
                parsed["sandbox_exit_code"] = sandbox_result.exit_code
                return parsed
            print("⚠️ Daytona returned no usable output — falling back")
        except Exception as exc:
            print(f"⚠️ Daytona agent failed — falling back: {exc}")

    return build_basic_review_result(
        pr_number=pr_number,
        pr_title=pr_title,
        pr_body=pr_body,
        diff_text=diff_text,
        change_types=change_types,
        changed_files=changed_files,
        source_repo=source_repo,
    )


def build_review_comment(
    pr_number: int,
    pr_title: str,
    pr_body: str,
    diff_text: str,
    change_types: list[str],
    changed_files: list[str],
    source_repo: str,
    result: dict,
) -> str:
    file_list = "\n".join(f"- `{path}`" for path in changed_files[:20]) or "- `No files detected`"
    summary = result.get("review_body") or result.get("pr_body") or "Auto-generated review note."
    notes = result.get("generated_content") or ""
    diff_preview = diff_text.strip()[:1500]
    backend = result.get("backend", "unknown")
    exit_code = result.get("sandbox_exit_code")

    body = f"""🤖 Maintainer review for `{source_repo}#{pr_number}`

**Title:** {pr_title}
**Backend:** {backend}
**Change types:** {", ".join(change_types)}
**Changed files:**
{file_list}

**PR body:**
{pr_body or "No description provided."}

**Review note:**
{summary}
"""

    if exit_code is not None:
        body += f"\n**Sandbox exit code:** `{exit_code}`\n"

    if notes:
        body += f"""

**Extra context:**
{notes[:2000]}
"""

    if diff_preview:
        body += f"""

**Diff preview:**
```diff
{diff_preview}
```
"""

    return body

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    event = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256")

    if WEBHOOK_SECRET and signature:
        expected = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(403, "Invalid signature")

    payload = json.loads(body)

    if event == "issue_comment":
        return await handle_comment(payload)

    if event == "pull_request":
        return await handle_pull_request(payload)

    return {"ok": True, "event": event, "handled": False}


@app.post("/scan-open-prs")
async def scan_open_prs():
    """Manual scan: find open PRs and comment on them with Hermes output."""
    token = github_tools.get_installation_access_token(_require_installation_id())
    open_prs = github_tools.list_open_pull_requests(token, ORG, REPO, per_page=10)

    results = []
    for pr in open_prs:
        pr_number = pr["number"]
        print(f"🔎 Scanning open PR #{pr_number} in {ORG}/{REPO}")
        results.append(await comment_on_pr(token, ORG, REPO, pr))

    return {"ok": True, "count": len(results), "results": results}


async def handle_pull_request(payload: dict):
    action = payload.get("action")

    if action not in ("opened", "synchronize"):
        return {"ok": True, "action": action, "handled": False}

    installation_id = payload["installation"]["id"]
    repo_owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]
    source_repo = f"{repo_owner}/{repo_name}"
    pr = payload["pull_request"]
    pr_number = pr["number"]
    pr_title = pr["title"]
    pr_body = pr["body"]
    diff_url = pr["diff_url"]

    if repo_name == WEBSITE_REPO:
        print(f"⏭️ Ignoring event from website repo — skipping")
        return {"ok": True, "handled": False, "reason": "website_repo_ignored"}

    print(f"📥 PR #{pr_number} {action} in {source_repo}: '{pr_title}'")

    token = github_tools.get_installation_access_token(installation_id)

    diff_text = github_tools.fetch_pr_diff(diff_url, token)
    file_meta = github_tools.fetch_pr_file_metadata(token, repo_owner, repo_name, pr_number)
    changed_files = [item["filename"] for item in file_meta]
    change_types = github_tools.classify_change(changed_files)

    print(f"🔍 Change types: {change_types}")

    result = run_review_agent(
        pr_number=pr_number,
        pr_title=pr_title,
        pr_body=pr_body,
        diff_text=diff_text,
        change_types=change_types,
        changed_files=changed_files,
        source_repo=source_repo,
        pr_payload=pr,
    )

    review_body = build_review_comment(
        pr_number=pr_number,
        pr_title=pr_title,
        pr_body=pr_body,
        diff_text=diff_text,
        change_types=change_types,
        changed_files=changed_files,
        source_repo=source_repo,
        result=result,
    )

    github_tools.post_pr_review(
        token, repo_owner, repo_name, pr_number, review_body, event="COMMENT"
    )

    return {"ok": True, "handled": True, "mode": "review_comment"}


def _require_installation_id() -> int:
    """Manual scan uses configured repo installation from env."""
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    if not installation_id:
        raise HTTPException(400, "GITHUB_INSTALLATION_ID is missing")
    return int(installation_id)


async def comment_on_pr(token: str, repo_owner: str, repo_name: str, pr: dict) -> dict:
    """Build review for one open PR and post it."""
    pr_number = pr["number"]
    pr_title = pr["title"]
    pr_body = pr.get("body") or ""
    diff_url = pr["diff_url"]

    diff_text = github_tools.fetch_pr_diff(diff_url, token)
    file_meta = github_tools.fetch_pr_file_metadata(token, repo_owner, repo_name, pr_number)
    changed_files = [item["filename"] for item in file_meta]
    change_types = github_tools.classify_change(changed_files)

    result = run_review_agent(
        pr_number=pr_number,
        pr_title=pr_title,
        pr_body=pr_body,
        diff_text=diff_text,
        change_types=change_types,
        changed_files=changed_files,
        source_repo=f"{repo_owner}/{repo_name}",
        pr_payload=pr,
    )

    review_body = build_review_comment(
        pr_number=pr_number,
        pr_title=pr_title,
        pr_body=pr_body,
        diff_text=diff_text,
        change_types=change_types,
        changed_files=changed_files,
        source_repo=f"{repo_owner}/{repo_name}",
        result=result,
    )

    github_tools.post_pr_review(token, repo_owner, repo_name, pr_number, review_body, event="COMMENT")
    return {"pr": pr_number, "mode": "review_comment"}


async def handle_comment(payload: dict):
    return {"ok": True, "handled": False, "reason": "comment_flow_disabled"}
