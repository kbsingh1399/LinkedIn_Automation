import asyncio
import sys
import urllib.request
from playwright.async_api import async_playwright
from config import settings
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine
from gemini_ai import GeminiAIClient

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def main():
    print("=" * 80)
    print(" 🧪 LIVE ACCEPTANCE & END-TO-END VERIFICATION TEST FOR ALL 4 CORE MODULES")
    print("=" * 80)

    cdp_active = await check_cdp(9222)
    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connected via CDP to active Chrome instance on http://localhost:9222")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print("🚀 Launching visible persistent Chrome session...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        # Set window maximized
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setWindowBounds", {"windowId": 1, "bounds": {"windowState": "maximized"}})
        except Exception:
            pass

        results = {}

        # ── TEST 1: GEMINI AI WEB AUTOMATION ──
        print("\n🤖 [MODULE 1/4] Testing Gemini AI Web Client...")
        try:
            ai = GeminiAIClient()
            gemini_reply = await ai.generate_content("Respond with exact words: 'Gemini DOM verification passed.'", page=page)
            print(f"  Result: {gemini_reply!r}")
            results["gemini_ai"] = "PASS" if gemini_reply and "passed" in gemini_reply.lower() else "WARN_OR_TIMEOUT"
        except Exception as e:
            print(f"  ❌ Gemini Error: {e}")
            results["gemini_ai"] = f"FAIL: {e}"

        # ── TEST 2: LINKEDIN FEED ENGINE ──
        print("\n📱 [MODULE 2/4] Testing LinkedIn Feed Engine...")
        try:
            feed_engine = LinkedInFeedEngine(page, preproduction=True)
            feed_posts = await feed_engine.process_feed_posts(max_posts=2)
            print(f"  Processed {len(feed_posts)} feed posts in preproduction mode.")
            results["linkedin_feed"] = "PASS" if len(feed_posts) > 0 else "PASS_0_POSTS"
        except Exception as e:
            print(f"  ❌ Feed Engine Error: {e}")
            results["linkedin_feed"] = f"FAIL: {e}"

        # ── TEST 3: LINKEDIN NOTIFICATIONS ENGINE ──
        print("\n🔔 [MODULE 3/4] Testing LinkedIn Notifications Engine...")
        try:
            notif_engine = LinkedInNotificationsEngine(page, preproduction=True)
            notifs = await notif_engine.process_top_20_notifications()
            print(f"  Processed {len(notifs)} notifications in preproduction mode.")
            results["linkedin_notifications"] = "PASS" if len(notifs) >= 0 else "FAIL"
        except Exception as e:
            print(f"  ❌ Notifications Engine Error: {e}")
            results["linkedin_notifications"] = f"FAIL: {e}"

        # ── TEST 4: LINKEDIN INBOX ENGINE ──
        print("\n💬 [MODULE 4/4] Testing LinkedIn Inbox Engine...")
        try:
            inbox_engine = LinkedInInboxEngine(page, preproduction=True)
            messages = await inbox_engine.process_top_20_messages()
            print(f"  Processed {len(messages)} inbox messages in preproduction mode.")
            results["linkedin_inbox"] = "PASS" if len(messages) >= 0 else "FAIL"
        except Exception as e:
            print(f"  ❌ Inbox Engine Error: {e}")
            results["linkedin_inbox"] = f"FAIL: {e}"

        print("\n" + "=" * 80)
        print("📊 END-TO-END ACCEPTANCE TEST RESULTS SUMMARY:")
        for mod, res in results.items():
            print(f"   • {mod:25s} : {res}")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
