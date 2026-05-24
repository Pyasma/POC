import os
import json
import hashlib
import hmac

from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from google import genai

import github_tools
from config import WEBSITE_ORG, WEBSITE_REPO, TARGET_FILE

load_dotenv()

app = FastAPI()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


# def run_ai_agent(
#     pr_title: str,
#     pr_body: str,
#     diff_text: str,
#     change_types: list[str],
#     changed_files: list[str],
#     source_repo: str,
# ) -> dict:
#     print(f"🤖 Handoff to Gemini Agent for PR: '{pr_title}'")

#     prompt = f"""You are a Hugo/Docsy documentation generator for the krkn-chaos project.

# A PR was merged in the upstream repository **{source_repo}**.
# Generate the corresponding Hugo markdown content for the documentation site at krkn-chaos.dev.

# **Detected change types**: {', '.join(change_types)}
# **Files changed in source PR**: {', '.join(changed_files)}

# ## Content structure rules
# - Use Hugo frontmatter: --- title: ... weight: ... ---
# - Parameter tables: use GitHub-flavored markdown pipe tables
# - Scenario pages: use {{< tabpane >}} / {{< tab >}} shortcodes
# - CLI references: list flags in a table (flag, shorthand, type, default, description)
# - Config references: list fields in a table (name, type, default, description)

# ## Output format
# Return ONLY valid JSON — no explanation, no code fences:

# {{
#   "commit_message": "short commit message",
#   "pr_title": "short PR title",
#   "pr_body": "what changed and why, 2-3 sentences",
#   "generated_content": "full Hugo markdown content to append to the docs"
# }}

# ORIGINAL PR TITLE: {pr_title}
# ORIGINAL PR DESCRIPTION: {pr_body or "No description provided."}
# CODE DIFF:
# {diff_text}
# """

#     try:
#         print("⏳ Calling Gemini...")
#         # response = client.models.generate_content(
#         #     model="gemini-2.5-flash-lite",
#         #     contents=prompt,
#         # )
#         # raw_text = response.text.strip()

#         # with open("agent.log", "w") as f:
#         #     f.write(raw_text)

#         # raw_text = raw_text.replace("```json", "").replace("```", "").strip()
#         # parsed = json.loads(raw_text)

#         # with open("parsed_agent.log", "w") as f:
#         #     f.write(json.dumps(parsed, indent=2))

#         print("✅ Gemini done")
#         return {
#             "commit_message": parsed.get("commit_message", f"docs: auto-update for {pr_title}"),
#             "pr_title": parsed.get("pr_title", f"docs: follow-up for {pr_title}"),
#             "pr_body": parsed.get("pr_body", "Auto-generated documentation update."),
#             "generated_content": parsed.get("generated_content", ""),
#         }

#     except Exception as e:
#         print(f"❌ Gemini Agent Error: {e}")
#         return {
#             "commit_message": f"docs: auto-update for {pr_title}",
#             "pr_title": f"docs: follow-up for {pr_title}",
#             "pr_body": f"Agent failed.\n\nError: {str(e)}",
#             "generated_content": "",
#         }


# def refine_with_agent(current_content: str, instruction: str) -> str:
#     prompt = f"""You are a Hugo/Docsy documentation editor for the krkn-chaos project.

# A reviewer has asked you to update the following documentation.

# **Instruction:** {instruction}

# **Current content:**
# {current_content}

# Return ONLY the updated file content.
# No explanation, no JSON, no code fences. Just raw Hugo markdown.
# """
#     response = client.models.generate_content(
#         model="gemini-2.5-flash-lite",
#         contents=prompt,
#     )
#     return response.text.strip()

def run_ai_agent(
    pr_title: str,
    pr_body: str,
    diff_text: str,
    change_types: list[str],
    changed_files: list[str],
    source_repo: str,
) -> dict:
    print(f"🤖 Handoff to Gemini Agent for PR: '{pr_title}'")

    # ── AGENT COMMENTED OUT — using cached agent.log output ──
    # prompt = f"""..."""
    # response = client.models.generate_content(...)
    # raw_text = response.text.strip()
    # raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    # parsed = json.loads(raw_text)

    print("⏳ Loading from agent.log...")

    with open("parsed_agent.log", "r") as f:
        parsed = json.load(f)

    print("✅ Loaded cached agent output")

    return {
        "commit_message": parsed.get("commit_message", f"docs: auto-update for {pr_title}"),
        "pr_title": parsed.get("pr_title", f"docs: follow-up for {pr_title}"),
        "pr_body": parsed.get("pr_body", "Auto-generated documentation update."),
        "generated_content": parsed.get("generated_content", ""),
    }

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
    changed_files = github_tools.fetch_pr_files(token, repo_owner, repo_name, pr_number)
    change_types = github_tools.classify_change(changed_files)

    print(f"🔍 Change types: {change_types}")

    result = run_ai_agent(
        pr_title, pr_body, diff_text,
        change_types, changed_files, source_repo
    )

    generated_content = result.get("generated_content", "")
    if not generated_content:
        print("⚠️ Agent returned no content — skipping PR")
        return {"ok": True, "handled": False, "reason": "no_content_generated"}

    # get current content of hardcoded target file
    current_content, _ = github_tools.get_file_content(
        token, WEBSITE_ORG, WEBSITE_REPO, TARGET_FILE, "main"
    )

    # append agent output to existing file
    updated_content = current_content + f"""

---

## Auto-generated update — krkn#{pr_number}

> Source: [{source_repo}#{pr_number}](https://github.com/{source_repo}/pull/{pr_number}) — {pr_title}
> Change types: {', '.join(change_types)}

{generated_content}
"""

    # create branch on website fork
    branch = f"auto-docs/pr-{pr_number}"
    main_sha = github_tools.get_ref_sha(
        token, WEBSITE_ORG, WEBSITE_REPO, "heads/main"
    )
    github_tools.create_branch(
        token, WEBSITE_ORG, WEBSITE_REPO, branch, main_sha
    )

    # push updated file to branch
    github_tools.push_file(
        token, WEBSITE_ORG, WEBSITE_REPO,
        TARGET_FILE,
        updated_content,
        branch,
        result["commit_message"]
    )

    # open draft PR
    github_tools.open_new_pull_request(
        token, WEBSITE_ORG, WEBSITE_REPO,
        title=result["pr_title"],
        body=f"""## Auto-generated documentation update

**Source repo:** {source_repo}
**Source PR:** #{pr_number} — {pr_title}
**Change types detected:** {', '.join(change_types)}
**Target file:** `{TARGET_FILE}`

---

{result['pr_body']}

---
> Auto-generated by krkn doc sync bot.
> To refine, comment `/doc-update <your instruction>`
""",
        head_branch=branch,
        base_branch="main"
    )

    return {"ok": True, "handled": True, "branch": branch}


async def handle_comment(payload: dict):
    # only handle PR comments, not issue comments
    if "pull_request" not in payload.get("issue", {}).get("html_url", ""):
        return {"ok": True, "handled": False, "reason": "not_a_pr_comment"}

    comment_body = payload["comment"]["body"].strip()
    if not comment_body.startswith("/doc-update"):
        return {"ok": True, "handled": False, "reason": "not_a_command"}

    instruction = comment_body.replace("/doc-update", "").strip()
    pr_number = payload["issue"]["number"]
    installation_id = payload["installation"]["id"]

    token = github_tools.get_installation_access_token(installation_id)

    # acknowledge immediately
    github_tools.post_pr_comment(
        token, WEBSITE_ORG, WEBSITE_REPO, pr_number,
        f"🤖 Refining docs with instruction: `{instruction}`"
    )

    # get branch from PR
    pr_data = github_tools.get_pr(token, WEBSITE_ORG, WEBSITE_REPO, pr_number)
    branch = pr_data["head"]["ref"]

    print(f"💬 /doc-update on PR #{pr_number}, branch '{branch}': {instruction}")

    # get current file content from that branch
    current_content, _ = github_tools.get_file_content(
        token, WEBSITE_ORG, WEBSITE_REPO, TARGET_FILE, branch
    )

    # call agent with instruction
    updated_content = refine_with_agent(current_content, instruction)

    # push updated content to same branch — PR updates automatically
    github_tools.push_file(
        token, WEBSITE_ORG, WEBSITE_REPO,
        TARGET_FILE,
        updated_content,
        branch,
        f"docs: refine per review — {instruction[:60]}"
    )

    # confirm done
    github_tools.post_pr_comment(
        token, WEBSITE_ORG, WEBSITE_REPO, pr_number,
        f"✅ Done — pushed updated docs based on: `{instruction}`"
    )

    return {"ok": True, "handled": True}