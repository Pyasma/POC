import json
import os
import textwrap
from dataclasses import dataclass, field


@dataclass
class DaytonaRunResult:
    """Result from sandbox execution."""

    stdout: str = ""
    exit_code: int | None = None
    raw: object | None = None


@dataclass
class DaytonaTaskConfig:
    api_key: str | None
    api_url: str | None = None
    target: str | None = None
    snapshot: str = "daytona-small"
    repo_name: str = "workspace"
    diff_path: str = "diff.patch"
    bootstrap_commands: list[str] = field(default_factory=list)
    agent_command: str = "hermes install"
    agent_timeout: int = 300
    working_dir: str | None = None


def load_daytona_config() -> DaytonaTaskConfig:
    """Build Daytona settings from environment."""
    bootstrap = os.getenv("DAYTONA_BOOTSTRAP_COMMANDS", "").strip()
    commands = [cmd.strip() for cmd in bootstrap.splitlines() if cmd.strip()] if bootstrap else []

    return DaytonaTaskConfig(
        api_key=os.getenv("DAYTONA_API_KEY"),
        api_url=os.getenv("DAYTONA_API_URL"),
        target=os.getenv("DAYTONA_TARGET"),
        snapshot=os.getenv("DAYTONA_SNAPSHOT", "daytona-small"),
        repo_name=os.getenv("DAYTONA_REPO_NAME", "workspace"),
        diff_path=os.getenv("DAYTONA_DIFF_PATH", "diff.patch"),
        bootstrap_commands=commands,
        agent_command=os.getenv("DAYTONA_AGENT_COMMAND", "hermes install"),
        agent_timeout=int(os.getenv("DAYTONA_AGENT_TIMEOUT", "300")),
        working_dir=os.getenv("DAYTONA_WORKDIR"),
    )


def daytona_enabled() -> bool:
    """True when Daytona API key exists."""
    return bool(os.getenv("DAYTONA_API_KEY"))


def _serialize_payload(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def run_with_daytona(
    *,
    diff_text: str,
    pr_payload: dict,
    prompt_text: str,
) -> DaytonaRunResult:
    """Run sandbox flow in Daytona and return review text.

    The sandbox flow is intentionally command-driven:
    - write diff to file
    - run bootstrap commands
    - run agent command such as `hermes install`
    - emit review markdown or JSON to stdout
    """
    try:
        from daytona import (
            CreateSandboxFromSnapshotParams,
            Daytona,
            DaytonaConfig,
        )
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(f"Daytona SDK unavailable: {exc}") from exc

    config = load_daytona_config()
    sdk_config = DaytonaConfig(
        api_key=config.api_key,
        api_url=config.api_url,
        target=config.target,
    )
    daytona = Daytona(sdk_config)
    sandbox = daytona.create(
        CreateSandboxFromSnapshotParams(
            snapshot=config.snapshot,
            auto_stop_interval=0,
        )
    )

    repo_dir = config.working_dir or config.repo_name
    diff_path = f"{repo_dir}/{config.diff_path}"
    payload_path = f"{repo_dir}/task.json"
    prompt_path = f"{repo_dir}/prompt.txt"

    sandbox.fs.create_folder(repo_dir, "755")
    sandbox.fs.upload_file(diff_text.encode("utf-8"), diff_path)
    sandbox.fs.upload_file(_serialize_payload(pr_payload).encode("utf-8"), payload_path)
    sandbox.fs.upload_file(prompt_text.encode("utf-8"), prompt_path)

    for command in config.bootstrap_commands:
        sandbox.process.exec(command, cwd=repo_dir, timeout=config.agent_timeout)

    response = sandbox.process.exec(
        config.agent_command,
        cwd=repo_dir,
        env={
            "DIFF_PATH": diff_path,
            "TASK_JSON": payload_path,
            "PROMPT_FILE": prompt_path,
            "DAYTONA_REPO_DIR": repo_dir,
        },
        timeout=config.agent_timeout,
    )

    stdout = getattr(response, "result", "") or ""
    exit_code = getattr(response, "exit_code", None)
    return DaytonaRunResult(stdout=stdout, exit_code=exit_code, raw=response)


def render_daytona_prompt(
    *,
    pr_number: int,
    source_repo: str,
    pr_title: str,
    pr_body: str,
    change_types: list[str],
    changed_files: list[str],
    diff_text: str,
) -> str:
    """Prompt file for sandboxed agent."""
    files = "\n".join(f"- {path}" for path in changed_files[:50]) or "- none"
    diff_preview = "\n".join(diff_text.splitlines()[:80])
    return textwrap.dedent(
        f"""
        You are a maintainer assistant for {source_repo}.

        Goal:
        - Read diff from $DIFF_PATH
        - Inspect task JSON from $TASK_JSON
        - Produce a PR review comment in markdown

        PR:
        - Number: {pr_number}
        - Title: {pr_title}
        - Body: {pr_body or "No description provided."}

        Change types:
        {", ".join(change_types)}

        Changed files:
        {files}

        Diff preview:
        {diff_preview or "No diff preview"}

        Output rules:
        - Return markdown or JSON only
        - Mention concrete behavior risks
        - Keep it short
        """
    ).strip()
