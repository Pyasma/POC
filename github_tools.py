import re
import time
import base64
import jwt
import requests as httprequests
from config import APP_ID, PRIVATE_KEY

def generate_jwt():
    """Generates a short-lived JWT to authenticate as the GitHub App."""
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": APP_ID
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def get_installation_access_token(installation_id: int) -> str:
    """Exchanges the App JWT for a temporary installation token."""
    app_jwt = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt}"
    }
    response = httprequests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()["token"]


def fetch_pr_diff(diff_url: str, token: str) -> str:
    """Downloads the text diff patch of the opened pull request."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = httprequests.get(diff_url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def fetch_pr_files(token: str, repo_owner: str, repo_name: str, pr_number: int) -> list[str]:
    """Returns list of filenames changed in a PR."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(url, headers=headers)
    response.raise_for_status()
    return [f["filename"] for f in response.json()]


def fetch_pr_file_metadata(token: str, repo_owner: str, repo_name: str, pr_number: int) -> list[dict]:
    """Returns PR file metadata, including patch text when GitHub provides it."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def list_open_pull_requests(token: str, repo_owner: str, repo_name: str, per_page: int = 10) -> list[dict]:
    """Lists open pull requests for a repo."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(
        url,
        headers=headers,
        params={"state": "open", "per_page": per_page, "sort": "updated", "direction": "desc"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def classify_change(files: list[str]) -> list[str]:
    """Classifies change type from file paths for Hugo docs generation."""
    types = []
    for f in files:
        if re.search(r'(config|defaults|settings)\.(yaml|yml|json|toml|env)', f):
            types.append("config_fields")
        if re.search(r'(scenarios?/|/scenario)', f):
            types.append("new_scenario")
        if re.search(r'(cmd/|cli|flag|viper|pflag)', f):
            types.append("cli_flags")
        if re.search(r'README\.md|docs?/', f):
            types.append("doc_update")
        if re.search(r'\.go$', f):
            types.append("code_change")
        if re.search(r'(api|proto|openapi|swagger)', f):
            types.append("api_change")
    return list(set(types)) if types else ["unknown"]


def get_ref_sha(token: str, repo_owner: str, repo_name: str, ref: str = "heads/main") -> str:
    """Gets the SHA of a git ref (branch)."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["object"]["sha"]


def create_branch(token: str, repo_owner: str, repo_name: str, branch_name: str, sha: str):
    """Creates a new branch from the given commit SHA."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.post(url, headers=headers, json={
        "ref": f"refs/heads/{branch_name}",
        "sha": sha
    })
    if response.status_code == 201:
        print(f"🌿 Created branch '{branch_name}'")
    else:
        print(f"❌ Failed to create branch: {response.text}")


def open_new_pull_request(token: str, repo_owner: str, repo_name: str,
                          title: str, body: str, head_branch: str,
                          base_branch: str = "main", draft: bool = True):
    """Opens a pull request on the target repo (draft by default)."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch,
        "draft": draft,
    }
    response = httprequests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(f"🚀 Opened PR: {response.json().get('html_url')}")
    else:
        print(f"❌ Failed to open PR: {response.text}")


def push_file(token: str, repo_owner: str, repo_name: str, path: str,
              content: str, branch: str, message: str) -> bool:
    """Creates or updates a file on a branch via GitHub Contents API."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    encoded = base64.b64encode(content.encode()).decode()
    data = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    # Check if file already exists to get its SHA
    existing = httprequests.get(url, headers=headers, params={"ref": branch})
    if existing.status_code == 200:
        data["sha"] = existing.json()["sha"]

    response = httprequests.put(url, headers=headers, json=data)
    if response.status_code in (201, 200):
        print(f"📄 {'Updated' if existing.status_code == 200 else 'Created'} {path}")
        return True
    else:
        print(f"❌ Failed to push {path}: {response.text}")
        return False

def get_pr(token: str, repo_owner: str, repo_name: str, pr_number: int) -> dict:
    """Gets PR metadata including head branch name."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_file_content(token: str, repo_owner: str, repo_name: str,
                     path: str, ref: str) -> tuple[str, str]:
    """Returns (decoded_content, sha). sha is needed when updating existing files."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.get(url, headers=headers, params={"ref": ref})
    response.raise_for_status()
    data = response.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def post_pr_comment(token: str, repo_owner: str, repo_name: str,
                    pr_number: int, body: str):
    """Posts a comment on a PR."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.post(url, headers=headers, json={"body": body})
    if response.status_code == 201:
        print(f"💬 Posted comment on PR #{pr_number}")
    else:
        print(f"❌ Failed to post comment: {response.text}")


def post_pr_review(token: str, repo_owner: str, repo_name: str,
                   pr_number: int, body: str, event: str = "COMMENT"):
    """Posts a PR review. COMMENT creates a review comment on the diff."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}"
    }
    response = httprequests.post(url, headers=headers, json={
        "body": body,
        "event": event,
    })
    if response.status_code in (200, 201):
        print(f"🧾 Posted PR review on #{pr_number}")
    else:
        print(f"❌ Failed to post PR review: {response.text}")
