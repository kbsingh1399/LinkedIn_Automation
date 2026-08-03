import asyncio
import urllib.parse
from playwright.async_api import async_playwright
from config import settings

async def main():
    state_file = settings.user_data_dir / "storage_state.json"
    print("Storage state exists:", state_file.exists())

    async with async_playwright() as p:
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        if state_file.exists():
            context_kwargs["storage_state"] = str(state_file)

        # Launch Chromium with args to avoid connection resets
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--ignore-certificate-errors"]
        )
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        search_url = "https://x.com/search?q=Python%20filter%3Aimages&f=top"
        print(f"Navigating to {search_url} ...")

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            print("Page title:", await page.title())
            print("Current URL:", page.url)

            # Scroll down
            for i in range(4):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)

            tweets = await page.query_selector_all("article[data-testid='tweet']")
            print(f"\nFound {len(tweets)} live tweet elements on X.com!\n")

            valid_posts = []
            for t in tweets:
                try:
                    text_el = await t.query_selector("div[data-testid='tweetText']")
                    text = await text_el.inner_text() if text_el else ""

                    img_els = await t.query_selector_all("div[data-testid='tweetPhoto'] img")
                    media_urls = []
                    for img in img_els:
                        src = await img.get_attribute("src")
                        if src and "media" in src:
                            media_urls.append(src)

                    time_el = await t.query_selector("time")
                    link_el = await time_el.evaluate_handle("el => el.closest('a')") if time_el else None
                    tweet_url = ""
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            tweet_url = f"https://x.com{href}"

                    user_el = await t.query_selector("div[data-testid='User-Name']")
                    user_info = await user_el.inner_text() if user_el else "Unknown"

                    if text and media_urls and tweet_url:
                        valid_posts.append({
                            "user": user_info.replace("\n", " "),
                            "url": tweet_url,
                            "text": text[:100] + "...",
                            "media_urls": media_urls
                        })
                except Exception as e:
                    print("Error parsing tweet:", e)

            print(f"✅ Extracted {len(valid_posts)} LIVE X posts with REAL URLs and images:")
            for idx, p_item in enumerate(valid_posts, start=1):
                print(f"\n[{idx}] {p_item['user']}")
                print(f"    URL: {p_item['url']}")
                print(f"    Text: {p_item['text']}")
                print(f"    Images: {p_item['media_urls']}")

        except Exception as e:
            print("Execution error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
