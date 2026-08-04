import subprocess
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

def sync_from_remote():
    print("🔄 Checking and Syncing GitHub / Arena.ai Remote Changes...")
    base_dir = Path(__file__).parent.resolve()

    try:
        # 1. Fetch latest changes from remote main
        fetch_res = subprocess.run(["git", "fetch", "origin", "main"], cwd=base_dir, capture_output=True, text=True)
        
        # 2. Check if local main is behind remote main
        status_res = subprocess.run(["git", "status", "-uno"], cwd=base_dir, capture_output=True, text=True)
        print(f"📊 Git Status Summary:\n{status_res.stdout.strip()}")

        # 3. Pull and rebase changes cleanly
        pull_res = subprocess.run(["git", "pull", "origin", "main", "--rebase"], cwd=base_dir, capture_output=True, text=True)
        print(f"✨ Git Pull Output:\n{pull_res.stdout.strip()}")

        # 4. Show recent 3 commits
        log_res = subprocess.run(["git", "log", "--oneline", "-n", "3"], cwd=base_dir, capture_output=True, text=True)
        print(f"\n📜 Latest Commits on Local Workspace:\n{log_res.stdout.strip()}\n")

    except Exception as e:
        print(f"⚠️ Error during git sync: {e}")

if __name__ == "__main__":
    sync_from_remote()
