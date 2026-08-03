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
        self.user_data_dir = settings.user_data_dir

    async def open_interactive_login(self):
        """Launches a visible browser window for the user to log into X.com once."""
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        print("\n🔑 Opening browser for X.com login...")
        print("👉 Please log into your X.com account in the opened browser window.")
        print("   Once logged in, close the browser window to save your session.\n")

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            await page.goto("https://x.com/login", wait_until="domcontentloaded")
            
            # Wait for user to close browser or login
            try:
                while len(context.pages) > 0:
                    await asyncio.sleep(1)
            except Exception:
                pass
            
            print("✅ X.com login session saved successfully!")

    async def search_and_curate_posts(self, topic: str, max_posts: int = 4) -> List[Dict[str, Any]]:
        posts = []
        encoded_topic = urllib.parse.quote(topic)
        filters = settings.x_search_filters
        search_url = f"https://x.com/search?q={encoded_topic}%20{urllib.parse.quote(filters)}&f=top"

        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            # Use persistent context to reuse logged-in session cookies
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                await page.goto(search_url, timeout=settings.browser_timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)

                # Check if redirected to login
                if "login" in page.url or "i/flow/login" in page.url:
                    print(f"⚠️ Notice: X.com requires login to view search results.")
                    print(f"👉 Please run: python LinkedIn_Post_Collector.py --login")

                # Enhanced scrolling to load tweets
                for _ in range(settings.max_scrolls):
                    await page.evaluate("window.scrollBy(0, 1200)")
                    await page.wait_for_timeout(1800)

                tweet_elements = await page.query_selector_all("article[data-testid='tweet']")
                candidates = []

                for element in tweet_elements[:max_posts * 5]:
                    try:
                        text_el = await element.query_selector("div[data-testid='tweetText']")
                        text = await text_el.inner_text() if text_el else ""
                        if not text or len(text) < 30:
                            continue

                        user_el = await element.query_selector("div[data-testid='User-Name']")
                        user_info = await user_el.inner_text() if user_el else "Unknown"

                        likes = 0
                        retweets = 0
                        try:
                            like_el = await element.query_selector("[data-testid='like'] span")
                            if like_el:
                                likes_text = await like_el.inner_text()
                                likes = self._parse_engagement_count(likes_text)
                            rt_el = await element.query_selector("[data-testid='retweet'] span")
                            if rt_el:
                                rt_text = await rt_el.inner_text()
                                retweets = self._parse_engagement_count(rt_text)
                        except:
                            pass

                        engagement_score = likes + (retweets * 2)

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

                        candidates.append({
                            "topic": topic,
                            "user": user_info.replace("\n", " "),
                            "url": tweet_url,
                            "raw_text": text,
                            "media_urls": media_urls,
                            "likes": likes,
                            "retweets": retweets,
                            "engagement_score": engagement_score
                        })

                    except Exception:
                        continue

                # Rank candidates by engagement_score (fallback to top extracted if threshold yields few)
                candidates.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
                filtered = [c for c in candidates if c["likes"] >= settings.min_likes or c["retweets"] >= settings.min_retweets]
                posts = filtered[:max_posts] if filtered else candidates[:max_posts]

            except Exception as e:
                print(f"[XCurator] Warning during search for '{topic}': {e}")
            finally:
                await context.close()

        return posts

    @staticmethod
    def _parse_engagement_count(text: str) -> int:
        if not text:
            return 0
        text = text.strip().upper()
        try:
            if 'K' in text:
                return int(float(text.replace('K', '')) * 1000)
            elif 'M' in text:
                return int(float(text.replace('M', '')) * 1000000)
            elif 'B' in text:
                return int(float(text.replace('B', '')) * 1000000000)
            return int(float(text))
        except (ValueError, TypeError):
            return 0

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
