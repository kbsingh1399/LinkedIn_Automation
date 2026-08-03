import argparse
import asyncio
import os
import subprocess
from pathlib import Path
from config import settings
from x_curator import XCurator
from linkedin_rewriter import LinkedInRewriter
from post_exporter import PostExporter

async def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post Automation from X.com")
    parser.add_argument("--topics", type=str, help="Comma-separated topics (e.g., 'AI,Python,Automation')")
    parser.add_argument("--count", type=int, default=4, help="Total number of posts to process daily")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--push-git", action="store_true", help="Automatically commit and push generated posts to GitHub")
    args = parser.parse_args()

    topics = [t.strip() for t in args.topics.split(",")] if args.topics else settings.topics
    total_count = args.count

    print(f"🚀 Starting LinkedIn Post Automation")
    print(f"📌 Target Topics: {topics}")
    print(f"📊 Target Post Count: {total_count}")

    curator = XCurator(headless=args.headless)
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
        print("\n🐙 Pushing updates to GitHub repository...")
        try:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Auto-generate LinkedIn posts"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ GitHub push completed successfully!")
        except Exception as e:
            print(f"⚠️ Git push encountered an error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
