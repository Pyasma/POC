import os
from dotenv import load_dotenv

load_dotenv()

ORG = "Pyasma"
REPO = "kyverno"

WEBSITE_ORG = "Pyasma"
WEBSITE_REPO = "website"  # your fork of the docs repo

# hardcoded target file for POC
TARGET_FILE = "content/en/docs/chaos-testing-guide/_index.md"

# Daytona sandbox defaults for agent flow
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api")
DAYTONA_TARGET = os.getenv("DAYTONA_TARGET", "us")
DAYTONA_SNAPSHOT = os.getenv("DAYTONA_SNAPSHOT", "daytona-small")
DAYTONA_REPO_NAME = os.getenv("DAYTONA_REPO_NAME", "workspace")
DAYTONA_DIFF_PATH = os.getenv("DAYTONA_DIFF_PATH", "diff.patch")
DAYTONA_AGENT_COMMAND = os.getenv("DAYTONA_AGENT_COMMAND", "hermes install")
DAYTONA_AGENT_TIMEOUT = int(os.getenv("DAYTONA_AGENT_TIMEOUT", "300"))
DAYTONA_BOOTSTRAP_COMMANDS = os.getenv("DAYTONA_BOOTSTRAP_COMMANDS", "")

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv(
    "GITHUB_APP_PRIVATE_KEY_PATH",
    "cognee-code-memory.2026-08-08.private-key.pem",
)

if not APP_ID:
    raise ValueError("GITHUB_APP_ID is missing from environment variables")
if not os.path.exists(PRIVATE_KEY_PATH):
    raise ValueError(f"Private key file not found at {PRIVATE_KEY_PATH}")

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()
