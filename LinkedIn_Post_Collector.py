import argparse
import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from config import settings
from x_curator import XCurator
from linkedin_rewriter import LinkedInRewriter
from post_exporter import PostExporter

def sync_git_pull():
    print("🔄 Pulling latest changes from GitHub (main branch)...")
    try:
        subprocess.run(["git", "pull", "origin", "main"], check=True)
        print("✅ Local repository is up-to-date with main!")
    except Exception as e:
        print(f"⚠️ Git pull warning: {e}")

def sync_git_push():
    print("🐙 Pushing updates to GitHub (main branch)...")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-generate LinkedIn posts"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ GitHub push to main completed successfully!")
    except Exception as e:
        print(f"⚠️ Git push warning: {e}")

async def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post Automation from X.com")
    parser.add_argument("--login", action="store_true", help="Open browser window to log into X.com once and save session")
    parser.add_argument("--topics", type=str, help="Comma-separated topics (e.g., 'AI,Python,Automation')")
    parser.add_argument("--count", type=int, default=4, help="Total number of posts to process daily")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--no-pull", action="store_true", help="Skip pulling latest changes before running")
    parser.add_argument("--push-git", action="store_true", help="Automatically commit and push generated posts to main branch")
    args = parser.parse_args()

    curator = XCurator(headless=args.headless)

    # Handle login mode
    if args.login:
        success = await curator.auto_login()
        if not success:
            await curator.open_interactive_login()
        return

    # Always fetch latest changes from main branch before running unless --no-pull is specified
    if not args.no_pull:
        sync_git_pull()

    topics = [t.strip() for t in args.topics.split(",")] if args.topics else settings.topics
    total_count = args.count

    print(f"\n🚀 Starting LinkedIn Post Automation")
    print(f"📌 Target Topics: {topics}")
    print(f"📊 Target Post Count: {total_count}")

    rewriter = LinkedInRewriter()
    exporter = PostExporter()

    all_raw_posts = []
    posts_per_topic = max(1, total_count // len(topics))

    for topic in topics:
        print(f"\n🔍 Searching X.com for topic: '{topic}'...")
        posts = await curator.search_and_curate_posts(topic=topic, max_posts=posts_per_topic)
        print(f"✅ Found {len(posts)} posts for '{topic}'")
        all_raw_posts.extend(posts)
        if len(all_raw_posts) >= total_count:
            break

    all_raw_posts = all_raw_posts[:total_count]

    print(f"\n✍️ Rewriting {len(all_raw_posts)} posts for LinkedIn & exporting...")
    saved_dirs = []
    for idx, raw_post in enumerate(all_raw_posts, start=1):
        rewritten = rewriter.rewrite_for_linkedin(raw_post)
        out_dir = exporter.export_post(idx, raw_post, rewritten)
        saved_dirs.append(out_dir)
        print(f"  └── [{idx}/{len(all_raw_posts)}] Exported to: {out_dir}")

    print(f"\n🎉 Successfully processed {len(saved_dirs)} posts!")
    print(f"📁 Output Directory: {settings.output_dir.resolve()}")

    if args.push_git:
        sync_git_push()

if __name__ == "__main__":
    asyncio.run(main())
