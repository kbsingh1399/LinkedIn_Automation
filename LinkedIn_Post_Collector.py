import argparse
import asyncio
import sys
from pathlib import Path
from config import settings
from x_curator import XCurator
from linkedin_rewriter import LinkedInRewriter
from post_exporter import PostExporter
from git_sync import GitSync

# Ensure UTF-8 stdout line buffering for Windows CMD/PowerShell
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def run_pipeline(topics: list[str], count_per_topic: int, headless: bool, login: bool, push_git: bool):
    print("\n🚀 Starting LinkedIn Post Automation")
    print(f"📌 Target Topics ({len(topics)}): {topics}")
    print(f"📊 Target Options Per Topic: {count_per_topic} (Total Posts: {len(topics) * count_per_topic})\n")

    curator = XCurator(headless=headless)

    if login:
        await curator.perform_automated_x_login(None)

    all_topic_results = {}
    rewriter = LinkedInRewriter()
    exporter = PostExporter()

    total_exported = 0

    for topic in topics:
        print(f"🔍 Searching X.com for topic: '{topic}'...")
        posts = await curator.search_and_curate_posts(topic, max_posts=count_per_topic)
        print(f"✅ Found {len(posts)} options with images for '{topic}'\n")

        print(f"✍️ Rewriting & exporting {len(posts)} options for topic '{topic}'...")
        for opt_idx, post_data in enumerate(posts, start=1):
            rewritten = rewriter.rewrite_for_linkedin(post_data)
            out_dir = exporter.export_post(topic, opt_idx, post_data, rewritten)
            total_exported += 1
            print(f"  └── [Option {opt_idx:02d}] Exported to: {out_dir}")
            print(f"      Source URL: {post_data.get('url', '')}")

    print(f"\n🎉 Successfully processed and exported {total_exported} post options across {len(topics)} topics!")
    print(f"📁 Output Directory: {settings.output_dir.resolve()}\n")

    if push_git:
        print("🐙 Syncing post output dumps with GitHub main branch...")
        GitSync.sync_and_push(commit_message=f"Auto-dump {total_exported} LinkedIn post options for topics: {', '.join(topics)}")

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post Automation Collector")
    parser.add_argument("--topics", type=str, default="AI, Python", help="Comma-separated topics to search")
    parser.add_argument("--count-per-topic", type=int, default=3, help="Number of post options to curate per topic (default: 3)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser visibly")
    parser.add_argument("--login", action="store_true", help="Automate X.com login step first")
    parser.add_argument("--no-pull", action="store_true", help="Skip git pull before running")
    parser.add_argument("--push-git", action="store_true", help="Automatically commit and push output to origin main")

    args = parser.parse_args()

    # Pre-pull unless disabled
    if not args.no_pull:
        GitSync.pull_latest()

    topic_list = [t.strip() for t in args.topics.split(",") if t.strip()]

    asyncio.run(run_pipeline(
        topics=topic_list,
        count_per_topic=args.count_per_topic,
        headless=args.headless,
        login=args.login,
        push_git=args.push_git
    ))

if __name__ == "__main__":
    main()
