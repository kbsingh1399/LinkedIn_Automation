import argparse
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from linkedin_publisher import LinkedInPublisher
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def run_autonomous_agent(mode: str, max_feed: int, headless: bool, preproduction: bool):
    print("\n=====================================================")
    print("      LinkedIn Autonomous AI Multi-Agent Engine      ")
    print("=====================================================")
    print(f"⚙️ Execution Mode: {mode.upper()}")
    print(f"🛡️ Preproduction Safety: {'ENABLED (Preproduction Safe Staging)' if preproduction else 'DISABLED (LIVE EXECUTION)'}")
    print(f"🖥️ Browser Mode: {'Headless' if headless else 'Visible Browser'}\n")

    publisher = LinkedInPublisher(headless=headless)

    async with async_playwright() as p:
        print("🌐 Launching Playwright Chromium persistent context...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(publisher.user_data_dir),
            headless=headless,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # Step 1: Ensure LinkedIn Session Logged In
        logged_in = await publisher.ensure_logged_in(page)
        if not logged_in:
            print("❌ Failed to verify LinkedIn authentication session. Aborting.")
            await context.close()
            return

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

        print("\n🎉 Autonomous Agent Cycle Completed Successfully!")
        await context.close()

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Autonomous AI Multi-Agent Engine")
    parser.add_argument("--mode", type=str, choices=["feed", "notifications", "inbox", "publish", "all"], default="all", help="Execution mode")
    parser.add_argument("--max-feed", type=int, default=5, help="Number of feed posts to dwell & engage with")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--live", action="store_true", help="Execute live actions on LinkedIn (Default: Preproduction mode)")

    args = parser.parse_args()
    preproduction = not args.live

    asyncio.run(run_autonomous_agent(
        mode=args.mode,
        max_feed=args.max_feed,
        headless=args.headless,
        preproduction=preproduction
    ))

if __name__ == "__main__":
    main()
