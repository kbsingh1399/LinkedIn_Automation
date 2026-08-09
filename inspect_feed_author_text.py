import asyncio
import sys
import json
import urllib.request
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def main():
    cdp_active = await check_cdp(9222)
    async with async_playwright() as p:
        if cdp_active:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        card = await page.query_selector("div[data-view-name='feed-full-update']")
        if card:
            # Dump inner HTML structure of actor & commentary section
            actor_html = await card.evaluate("""el => {
                const actor = el.querySelector('[class*="actor"]') || el.querySelector('a') || el;
                return actor ? actor.outerHTML : '';
            }""")
            print("--- ACTOR HTML PREVIEW ---")
            print(actor_html[:1500])

            commentary_html = await card.evaluate("""el => {
                const comm = el.querySelector('[class*="commentary"]') || el.querySelector('[class*="description"]') || el.querySelector('[class*="text"]');
                return comm ? comm.outerHTML : '';
            }""")
            print("\n--- COMMENTARY HTML PREVIEW ---")
            print(commentary_html[:1500])

if __name__ == "__main__":
    asyncio.run(main())
