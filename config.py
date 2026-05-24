import os
from dotenv import load_dotenv

load_dotenv()

ORG = "Pyasma"
REPO = "krkn"

WEBSITE_ORG = "Pyasma"
WEBSITE_REPO = "website"  # your fork of krkn-chaos/website

# hardcoded target file for POC
TARGET_FILE = "content/en/docs/chaos-testing-guide/_index.md"

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = "poc-krkn.2026-05-21.private-key.pem"

if not APP_ID:
    raise ValueError("GITHUB_APP_ID is missing from environment variables")
if not os.path.exists(PRIVATE_KEY_PATH):
    raise ValueError(f"Private key file not found at {PRIVATE_KEY_PATH}")

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()