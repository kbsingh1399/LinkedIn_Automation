import asyncio
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Any
import requests
from playwright.async_api import async_playwright
from config import settings

class XCurator:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def search_and_curate_posts(self, topic: str, max_posts: int = 4) -> List[Dict[str, Any]]:
        posts = []
        encoded_topic = urllib.parse.quote(topic)
        search_url = f"https://x.com/search?q={encoded_topic}&f=top"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(search_url, timeout=settings.browser_timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # Scroll down to load tweets
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 1000)")
                    await page.wait_for_timeout(1500)

                tweet_elements = await page.query_selector_all("article[data-testid='tweet']")
                for element in tweet_elements[:max_posts * 2]:
                    try:
                        text_el = await element.query_selector("div[data-testid='tweetText']")
                        text = await text_el.inner_text() if text_el else ""
                        if not text or len(text) < 30:
                            continue

                        user_el = await element.query_selector("div[data-testid='User-Name']")
                        user_info = await user_el.inner_text() if user_el else "Unknown"

                        media_urls = []
                        img_els = await element.query_selector_all("div[data-testid='tweetPhoto'] img")
                        for img in img_els:
                            src = await img.get_attribute("src")
                            if src and "media" in src:
                                media_urls.append(src)

                        time_el = await element.query_selector("time")
                        link_el = await time_el.evaluate_handle("el => el.closest('a')") if time_el else None
                        tweet_url = ""
                        if link_el:
                            href = await link_el.get_attribute("href")
                            if href:
                                tweet_url = f"https://x.com{href}"

                        posts.append({
                            "topic": topic,
                            "user": user_info.replace("\n", " "),
                            "url": tweet_url,
                            "raw_text": text,
                            "media_urls": media_urls
                        })

                        if len(posts) >= max_posts:
                            break
                    except Exception:
                        continue

            except Exception as e:
                print(f"[XCurator] Warning during search for '{topic}': {e}")
            finally:
                await browser.close()

        return posts

    @staticmethod
    def download_media(media_urls: List[str], save_dir: Path) -> List[Path]:
        save_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for idx, url in enumerate(media_urls, start=1):
            try:
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    ext = "jpg" if "format=jpg" in url or ".jpg" in url else "png"
                    file_path = save_dir / f"image_{idx}.{ext}"
                    file_path.write_bytes(res.content)
                    downloaded.append(file_path)
            except Exception as e:
                print(f"[XCurator] Failed to download media {url}: {e}")
        return downloaded
