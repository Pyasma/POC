import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Your specific PR URL
PR_URL = "https://github.com/krkn-chaos/krkn/pull/1261"

# Shortcut: Simply add '.diff' to the end of the web URL
DIFF_URL = f"{PR_URL}.diff"

# Setup your headers with the token we set up earlier
token = os.getenv("PA_TOKEN")
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}"
}

def fetch_specific_diff():
    print(f"Fetching diff from: {DIFF_URL}")
    try:
        response = requests.get(DIFF_URL, headers=headers)
        
        if response.status_code == 200:
            raw_diff = response.text
            
            # Print the first 1000 characters to verify it worked
            print("--- DIFF CAPTURED SUCCESSFULLY ---")
            print(raw_diff[:1000])
            
            # Save it locally so you can feed it to your AI agent later
            with open("krkn_pr_1261.diff", "w", encoding="utf-8") as f:
                f.write(raw_diff)
                
            print("\nSaved total diff to 'krkn_pr_1261.diff'")
            return raw_diff
        else:
            print(f"Failed to fetch diff. Status code: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_specific_diff()