import argparse
import asyncio
import os
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
from engagement_tracker import clear_old_records

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
        # Disabled extra tab creation to avoid opening random pages
        return

    async def run_cycle(self, mode: str, max_feed: int, headless: bool, preproduction: bool, cycle_num: int = 1):
        print(f"\n=== Cycle #{cycle_num} Start: {datetime.datetime.now().isoformat()} ===")

        publisher = LinkedInPublisher(headless=headless)

        from config import find_free_port
        debug_port = find_free_port(9222)
        print(f"🔌 [CDP] Using dynamic debug port: {debug_port}")

        context = None
        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(publisher.user_data_dir),
                    channel="chrome",
                    headless=headless,
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--test-type",
                        f"--remote-debugging-port={debug_port}",
                        "--remote-debugging-address=127.0.0.1",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                    ],
                )
                page = context.pages[0] if context.pages else await context.new_page()

                logged_in = await publisher.ensure_logged_in(page)
                if not logged_in:
                    print("❌ Login failed. Skipping cycle.")
                    return

                # P0-2: Purge stale engagement records to keep DB lean
                deleted = clear_old_records()
                if deleted:
                    print(f"🗑️ [DB Cleanup] Purged {deleted} stale engagement records.")

                # Security Checkpoint Gate: Pause execution if CAPTCHA or verification challenge appears
                if await PlaywrightResilience.verify_security_checkpoint(page):
                    print("🚨 Security checkpoint gate triggered. Pausing cycle to protect account.")
                    return

                # Overlay Dismissal Gate: Clear popups or cookie banners before proceeding
                await PlaywrightResilience.dismiss_blocking_overlays(page)

                # Auto-close any unwanted secondary tabs opened by external links
                for p_tab in context.pages[1:]:
                    if not p_tab.is_closed():
                        try:
                            print(f"🧹 [Tab Safety] Closing unwanted auxiliary tab: {p_tab.url}")
                            await p_tab.close()
                        except Exception:
                            pass
                await page.bring_to_front()

                # Occasional viewport resize
                await PlaywrightResilience.random_viewport_resize(page, context)

                if mode in ["feed", "all"]:
                    # Jitter ±15% of max_feed per cycle for anti-bot unpredictability.
                    std = max(0.5, max_feed * 0.15)
                    cycle_max_feed = max(max_feed, int(round(random.gauss(max_feed, std))))
                    print(f"📊 [Anti-Bot Stealth] Target for Cycle #{cycle_num}: {cycle_max_feed} feed posts (base setting: {max_feed})")
                    feed = LinkedInFeedEngine(page=page, preproduction=preproduction)
                    await feed.process_feed_posts(cycle_max_feed)

                # Close any unwanted tabs that opened during feed processing
                for p_tab in context.pages[1:]:
                    if not p_tab.is_closed():
                        try:
                            print(f"🧹 [Tab Safety] Closing unwanted auxiliary tab: {p_tab.url}")
                            await p_tab.close()
                        except Exception:
                            pass
                await page.bring_to_front()

                # P1-2: Mid-cycle security checkpoint gate
                await PlaywrightResilience.dismiss_blocking_overlays(page)
                if await PlaywrightResilience.verify_security_checkpoint(page):
                    print("🚨 [Mid-Cycle] Security checkpoint detected after Feed. Halting.")
                    return

                # Random reading pause between modules
                await asyncio.sleep(random.uniform(2.5, 6.0))

                if mode in ["notifications", "all"]:
                    notif = LinkedInNotificationsEngine(page=page, preproduction=preproduction)
                    await notif.process_top_20_notifications()

                # P1-2: Mid-cycle security checkpoint gate
                await PlaywrightResilience.dismiss_blocking_overlays(page)
                if await PlaywrightResilience.verify_security_checkpoint(page):
                    print("🚨 [Mid-Cycle] Security checkpoint detected after Notifications. Halting.")
                    return

                # Random reading pause between modules
                await asyncio.sleep(random.uniform(2.0, 5.0))

                if mode in ["inbox", "all"]:
                    inbox = LinkedInInboxEngine(page=page, preproduction=preproduction)
                    await inbox.process_top_20_messages()

                # Occasional page refresh & mouse scroll jitter
                await PlaywrightResilience.occasional_page_refresh(page, 0.22)
                await self._simulate_distraction(context)

                print("✅ Cycle completed cleanly.")

        except Exception as cycle_err:
            print(f"⚠️ [Cycle Error] Exception in cycle #{cycle_num}: {cycle_err}")
            print("   Attempting graceful recovery for next cycle...")

        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    async def run_forever(self, mode: str, max_feed: int, headless: bool, preproduction: bool, interval: int, max_cycles: int = 100):
        print(f"🚀 Starting continuous loop with humanized anti-bot randomness (base interval: {interval}s, max cycles: {max_cycles})")
        cycle = 0

        while self.running and cycle < max_cycles:
            cycle += 1
            try:
                await self.run_cycle(mode, max_feed, headless, preproduction, cycle_num=cycle)
            except Exception as e:
                print(f"⚠️ Top-level cycle failure recovery: {e}")

            if not self.running or cycle >= max_cycles:
                break

            # 35% chance of an extended human distraction break (e.g. coffee / tab switch)
            if random.random() < 0.35:
                long_break_minutes = random.randint(8, 25)
                print(f"\n☕ [Anti-Bot Stealth] Taking a human break for ~{long_break_minutes} minutes...")
                await asyncio.sleep(long_break_minutes * 60)
            else:
                # Heavy jitter: vary sleep by -30% to +50% so cycle start times are unpredictable
                jitter_interval = max(10, interval * random.uniform(0.7, 1.5) + random.uniform(-10, 30))
                print(f"⏳ [Anti-Bot Stealth] Sleeping for {jitter_interval:.0f}s before next cycle...")
                await asyncio.sleep(jitter_interval)

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

    try:
        if args.loop:
            asyncio.run(agent.run_forever(args.mode, args.max_feed, args.headless, preproduction, args.interval))
        else:
            asyncio.run(agent.run_cycle(args.mode, args.max_feed, args.headless, preproduction))
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Execution stopped via Ctrl+C. Chrome window and all tabs remain OPEN and UNTOUCHED!")
        os._exit(0)

if __name__ == "__main__":
    main()
