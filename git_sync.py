import subprocess

class GitSync:
    @staticmethod
    def pull_latest():
        try:
            print("🐙 Pulling latest changes from origin main...")
            subprocess.run(["git", "pull", "origin", "main"], check=True, capture_output=True, text=True)
            print("✅ Git pull complete.")
        except Exception as e:
            print(f"⚠️ Git pull notice: {e}")

    @staticmethod
    def sync_and_push(commit_message: str = "Auto-dump post packages"):
        try:
            print("🐙 Staging and committing post packages...")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("🚀 Successfully pushed to origin main!")
        except Exception as e:
            print(f"⚠️ Git push notice: {e}")
