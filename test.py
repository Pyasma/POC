import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def get_pr_url() -> str:
    """Return PR URL from argv or env."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    pr_url = os.getenv("PR_URL")
    if pr_url:
        return pr_url

    raise SystemExit("Provide PR URL as argv[1] or set PR_URL")


def fetch_specific_diff() -> str | None:
    pr_url = get_pr_url()
    diff_url = f"{pr_url}.diff"
    token = os.getenv("PA_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }

    print(f"Fetching diff from: {diff_url}")
    try:
        response = requests.get(diff_url, headers=headers, timeout=30)

        if response.status_code == 200:
            raw_diff = response.text
            print("--- DIFF CAPTURED SUCCESSFULLY ---")
            print(raw_diff[:1000])

            output_path = os.getenv("DIFF_OUTPUT", "sample.diff")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(raw_diff)

            print(f"\nSaved total diff to '{output_path}'")
            return raw_diff

        print(f"Failed to fetch diff. Status code: {response.status_code}")
        print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")

    return None


if __name__ == "__main__":
    fetch_specific_diff()
