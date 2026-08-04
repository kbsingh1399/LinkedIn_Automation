import argparse
import asyncio
import sys
import datetime
import random
import signal
from playwright.async_api import async_playwright
from config import settings
from linkedin_publisher import LinkedInPublisher
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine
from utils.playwright_utils import PlaywrightResilience

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInAutoAgent:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        print("\n🛑 Graceful shutdown initiated...")
        self.running = False

    async def _simulate_distraction(self, context):
        if random.random() > 0.28:
            return
        print("\n🧠 [Human Behavior] Taking a short distraction break...")
        try:
            distraction_page = await context.new_page()
            await distraction_page.goto(random.choice([
                "https://www.google.com",
                "https://news.ycombinator.com",
                "https://www.linkedin.com/search/results/all/"
            ]), timeout=20000)
            await asyncio.sleep(random.uniform(2, 4))

            distraction_duration = random.randint(25, 55)
            end_time = asyncio.get_event_loop().time() + distraction_duration
            while asyncio.get_event_loop().time() < end_time:
                await distraction_page.mouse.wheel(0, random.randint(400, 900))
                await asyncio.sleep(random.uniform(1.5, 4.0))
                if random.random() < 0.3:
                    await distraction_page.mouse.wheel(0, random.randint(-400, -150))
            await distraction_page.close()
            print("🧠 [Human Behavior] Distraction finished.\n")
        except:
            pass

    async def run_cycle(self, mode: str, max_feed: int, headless: bool, preproduction: bool):
        print(f"\n=== Cycle Start: {datetime.datetime.now().isoformat()} ===")

        publisher = LinkedInPublisher(headless=headless)

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(publisher.user_data_dir),
                headless=headless,
                viewport={"width": 1280, "height": 850},
            )
            page = context.pages[0] if context.pages else await context.new_page()

            logged_in = await publisher.ensure_logged_in(page)
            if not logged_in:
                print("❌ Login failed. Skipping cycle.")
                await context.close()
                return

            # Occasional viewport resize
            await PlaywrightResilience.random_viewport_resize(page, context)

            if mode in ["feed", "all"]:
                feed = LinkedInFeedEngine(page=page, preproduction=preproduction)
                await feed.process_feed_posts(max_feed)

            if mode in ["notifications", "all"]:
                notif = LinkedInNotificationsEngine(page=page, preproduction=preproduction)
                await notif.process_top_20_notifications()

            if mode in ["inbox", "all"]:
                inbox = LinkedInInboxEngine(page=page, preproduction=preproduction)
                await inbox.process_top_20_messages()

            # Occasional page refresh
            await PlaywrightResilience.occasional_page_refresh(page, 0.18)

            # Distraction simulation
            await self._simulate_distraction(context)

            await context.close()
        print("✅ Cycle completed.")

    async def run_forever(self, mode: str, max_feed: int, headless: bool, preproduction: bool, interval: int):
        print(f"🚀 Starting continuous loop (base interval: {interval}s)")
        cycle = 0

        while self.running:
            cycle += 1
            try:
                await self.run_cycle(mode, max_feed, headless, preproduction)
            except Exception as e:
                print(f"⚠️ Cycle error: {e}")

            if not self.running:
                break

            if random.random() < 0.35:
                long_break_minutes = random.randint(8, 25)
                print(f"\n☕ Taking a human break for ~{long_break_minutes} minutes...")
                await asyncio.sleep(long_break_minutes * 60)
            else:
                jitter = interval + random.uniform(-60, 90)
                print(f"⏳ Sleeping for {jitter:.0f}s before next cycle...")
                await asyncio.sleep(jitter)

        print("Agent stopped cleanly.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="all", choices=["feed", "notifications", "inbox", "all"])
    parser.add_argument("--max-feed", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    preproduction = not args.live
    agent = LinkedInAutoAgent()

    if args.loop:
        asyncio.run(agent.run_forever(args.mode, args.max_feed, args.headless, preproduction, args.interval))
    else:
        asyncio.run(agent.run_cycle(args.mode, args.max_feed, args.headless, preproduction))

if __name__ == "__main__":
    main()
