import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def main():
    state_file = settings.user_data_dir / "storage_state.json"
    print("Storage state file exists:", state_file.exists())

    async with async_playwright() as p:
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 850}
        }
        if state_file.exists():
            context_kwargs["storage_state"] = str(state_file)

        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        print("Navigating to https://x.com/home ...")
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        print("Current URL:", page.url)
        print("Page Title:", await page.title())

        print("Navigating to https://x.com/search?q=Python ...")
        await page.goto("https://x.com/search?q=Python", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        print("Search Page URL:", page.url)
        print("Search Page Title:", await page.title())

        # Check for articles / cells / tweet elements
        articles = await page.query_selector_all("article")
        cells = await page.query_selector_all("[data-testid='cellInner']")
        tweet_texts = await page.query_selector_all("[data-testid='tweetText']")
        imgs = await page.query_selector_all("img")

        print(f"\n--- DOM Inspection Results ---")
        print(f"Articles count: {len(articles)}")
        print(f"CellInner count: {len(cells)}")
        print(f"TweetText count: {len(tweet_texts)}")
        print(f"Total Imgs count: {len(imgs)}")

        if len(tweet_texts) > 0:
            sample = await tweet_texts[0].inner_text()
            print("\nSample tweet text:\n", sample[:150])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
