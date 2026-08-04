import argparse
import asyncio
import sys
import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from linkedin_publisher import LinkedInPublisher
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine
from git_sync import GitSync

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def run_autonomous_agent(mode: str, max_feed: int, headless: bool, preproduction: bool, loop: bool = False, interval: int = 300):
    print("\n=====================================================")
    print("      LinkedIn Autonomous AI Multi-Agent Engine      ")
    print("=====================================================")
    print(f"⚙️ Execution Mode: {mode.upper()}")
    print(f"🛡️ Preproduction Safety: {'ENABLED (Preproduction Safe Staging)' if preproduction else 'DISABLED (LIVE EXECUTION)'}")
    print(f"🔄 Continuous Loop Mode: {'ENABLED (Interval: ' + str(interval) + 's)' if loop else 'SINGLE PASS'}")
    print(f"🖥️ Browser Mode: {'Headless' if headless else 'Visible Browser'}\n")

    publisher = LinkedInPublisher(headless=headless)

    cycle_count = 0
    while True:
        cycle_count += 1
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=====================================================")
        print(f"   Autonomous Agent Cycle #{cycle_count} Start: {now_str}   ")
        print(f"=====================================================")

        # Auto-sync latest code changes from GitHub / Arena.ai before running cycle
        GitSync.pull_latest()

        # Safely clear stale locks for our isolated profile without affecting other Chrome processes
        lock_file = publisher.user_data_dir / "SingletonLock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

        async with async_playwright() as p:
            print("🌐 Launching Real Google Chrome persistent context (Isolated Port 9223)...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(publisher.user_data_dir),
                channel="chrome",
                headless=headless,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--remote-debugging-port=9223", "--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

            # Step 1: Ensure LinkedIn Session Logged In
            logged_in = await publisher.ensure_logged_in(page)
            if not logged_in:
                print("❌ Failed to verify LinkedIn authentication session. Aborting cycle.")
                await context.close()
                if not loop:
                    break
                await asyncio.sleep(interval)
                continue

            # Sub-Engine 1: Feed Engagement
            if mode in ["feed", "all"]:
                feed_engine = LinkedInFeedEngine(page=page, preproduction=preproduction)
                await feed_engine.process_feed_posts(max_posts=max_feed)

            # Sub-Engine 2: Notifications & Reply Audit
            if mode in ["notifications", "all"]:
                notif_engine = LinkedInNotificationsEngine(page=page, preproduction=preproduction)
                await notif_engine.process_top_20_notifications()

            # Sub-Engine 3: Messaging Inbox Audit
            if mode in ["inbox", "all"]:
                inbox_engine = LinkedInInboxEngine(page=page, preproduction=preproduction)
                await inbox_engine.process_top_20_messages()

            print(f"\n🎉 Autonomous Agent Cycle #{cycle_count} Completed Successfully!")
            await context.close()

        if not loop:
            break

        print(f"\n⏳ Continuous Loop Mode Active: Resting for {interval}s before Cycle #{cycle_count + 1}...")
        await asyncio.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Autonomous AI Multi-Agent Engine")
    parser.add_argument("--mode", type=str, choices=["feed", "notifications", "inbox", "publish", "all"], default="all", help="Execution mode")
    parser.add_argument("--max-feed", type=int, default=3, help="Number of feed posts to dwell & engage with per cycle")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--live", action="store_true", help="Execute live actions on LinkedIn (Default: Preproduction mode)")
    parser.add_argument("--loop", action="store_true", help="Run continuously in an infinite loop across all activities")
    parser.add_argument("--interval", type=int, default=300, help="Pause interval in seconds between continuous loop cycles (default: 300s)")

    args = parser.parse_args()
    preproduction = not args.live

    asyncio.run(run_autonomous_agent(
        mode=args.mode,
        max_feed=args.max_feed,
        headless=args.headless,
        preproduction=preproduction,
        loop=args.loop,
        interval=args.interval
    ))

if __name__ == "__main__":
    main()
