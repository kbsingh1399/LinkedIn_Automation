import asyncio
import urllib.parse
from pathlib import Path
from typing import Dict, List, Any
import requests
from PIL import Image, ImageEnhance
from playwright.async_api import async_playwright
from config import settings

class XCurator:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.user_data_dir = settings.user_data_dir

    async def perform_automated_x_login(self, page) -> bool:
        """Automated X.com login sequence using credentials from .env."""
        username = settings.x_username
        password = settings.x_password
        if not username or not password:
            print("⚠️ X.com credentials missing in .env")
            return False

        print(f"🔑 Performing automated login for user: @{username} ...")
        try:
            await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # Step 1: Fill Username
            user_input = await page.wait_for_selector("input[autocomplete='username'], input[name='text']", timeout=12000)
            if user_input:
                await user_input.fill(username)
                await page.wait_for_timeout(1000)
                next_btn = await page.query_selector("button:has-text('Next'), div[role='button']:has-text('Next')")
                if next_btn:
                    await next_btn.click()
                else:
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(4000)

            # Step 2: Verification check if requested
            pass_input = await page.query_selector("input[name='password']")
            if not pass_input:
                verify_input = await page.query_selector("input[data-testid='ocfEnterTextTextInput'], input[name='text']")
                if verify_input:
                    await verify_input.fill(username)
                    await page.wait_for_timeout(1000)
                    next_btn = await page.query_selector("button:has-text('Next'), div[role='button']:has-text('Next')")
                    if next_btn:
                        await next_btn.click()
                    else:
                        await page.keyboard.press("Enter")
                    await page.wait_for_timeout(4000)

            # Step 3: Password
            pass_input = await page.wait_for_selector("input[name='password']", timeout=12000)
            if pass_input:
                await pass_input.fill(password)
                await page.wait_for_timeout(1000)
                login_btn = await page.query_selector("button:has-text('Log in'), div[role='button']:has-text('Log in')")
                if login_btn:
                    await login_btn.click()
                else:
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(6000)

            return "home" in page.url or page.url.strip("/") == "https://x.com"
        except Exception as e:
            print(f"⚠️ Automated login notice: {e}")
            return False

    async def search_and_curate_posts(self, topic: str, max_posts: int = 4) -> List[Dict[str, Any]]:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        posts = []

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 850},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

            # Ensure logged in
            try:
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(3000)
            except Exception:
                pass

            if "login" in page.url or "onboarding" in page.url or page.url.strip("/") == "https://x.com":
                await self.perform_automated_x_login(page)

            # Search topic using mapped high-precision query or fallback
            search_query = settings.topic_search_map.get(topic, topic)
            search_url = f"https://x.com/search?q={urllib.parse.quote(search_query)}&f=top"
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)
            except Exception as e:
                print(f"⚠️ Navigation warning for topic '{topic}': {e}")

            # Scroll feed
            for _ in range(6):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)

            tweet_elements = await page.query_selector_all("article")
            candidates = []

            for t_el in tweet_elements:
                try:
                    text_el = await t_el.query_selector("div[data-testid='tweetText']")
                    text = await text_el.inner_text() if text_el else ""
                    if not text or len(text) < 20:
                        continue

                    # Extract native attached Image, Video, and GIF URLs
                    media_urls = []
                    
                    # 1. Images & GIF previews
                    img_els = await t_el.query_selector_all("div[data-testid='tweetPhoto'] img, img[src*='media'], div[data-testid='videoPlayer'] img")
                    for img in img_els:
                        src = await img.get_attribute("src")
                        if src and "media" in src and "profile_images" not in src and "svg" not in src:
                            media_urls.append(src)

                    # 2. Video & GIF MP4 sources
                    video_els = await t_el.query_selector_all("video, video source")
                    for v in video_els:
                        src = await v.get_attribute("src")
                        if src and ("video.twimg.com" in src or ".mp4" in src or "blob:" not in src):
                            media_urls.append(src)

                    # Deduplicate media URLs
                    media_urls = list(dict.fromkeys(media_urls))

                    # STRICT REQUIREMENT: Skip post if no media attached
                    if not media_urls:
                        continue

                    time_el = await t_el.query_selector("time")
                    link_el = await time_el.evaluate_handle("el => el.closest('a')") if time_el else None
                    tweet_url = ""
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href and "/status/" in href:
                            tweet_url = f"https://x.com{href}"

                    if not tweet_url:
                        continue

                    user_el = await t_el.query_selector("div[data-testid='User-Name']")
                    user_info = await user_el.inner_text() if user_el else "Unknown"

                    likes = 0
                    retweets = 0
                    try:
                        like_el = await t_el.query_selector("[data-testid='like'] span")
                        if like_el:
                            likes_text = await like_el.inner_text()
                            likes = self._parse_engagement_count(likes_text)
                        rt_el = await t_el.query_selector("[data-testid='retweet'] span")
                        if rt_el:
                            rt_text = await rt_el.inner_text()
                            retweets = self._parse_engagement_count(rt_text)
                    except:
                        pass

                    score = likes + (retweets * 2)

                    candidates.append({
                        "topic": topic,
                        "user": user_info.replace("\n", " "),
                        "url": tweet_url,
                        "raw_text": text,
                        "media_urls": media_urls,
                        "likes": likes,
                        "retweets": retweets,
                        "engagement_score": score
                    })
                except Exception:
                    continue

            candidates.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            posts = candidates[:max_posts]
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
            return int(float(text))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def enhance_image(file_path: Path):
        """Enhances image quality, sharpness, contrast, and clarity using Pillow."""
        try:
            with Image.open(file_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # 1. Enhance Sharpness (+35%)
                sharp_enhancer = ImageEnhance.Sharpness(img)
                img = sharp_enhancer.enhance(1.35)

                # 2. Enhance Contrast (+8%)
                contrast_enhancer = ImageEnhance.Contrast(img)
                img = contrast_enhancer.enhance(1.08)

                # 3. Enhance Color Vibrancy (+5%)
                color_enhancer = ImageEnhance.Color(img)
                img = color_enhancer.enhance(1.05)

                # Save back with high-quality optimization
                img.save(file_path, quality=95, optimize=True)
                print(f"✨ Enhanced image quality: {file_path.name}")
        except Exception as e:
            print(f"⚠️ Image enhancement notice for {file_path.name}: {e}")

    @classmethod
    def download_media(cls, media_urls: List[str], save_dir: Path) -> List[Path]:
        save_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for idx, url in enumerate(media_urls, start=1):
            try:
                # 1. Automatically Upgrade X Image URL to Maximum Resolution ('name=orig')
                high_res_url = url
                if "pbs.twimg.com" in url:
                    for size_param in ["name=small", "name=medium", "name=900x900", "name=360x360", "name=240x240"]:
                        high_res_url = high_res_url.replace(size_param, "name=orig")
                    if "name=" not in high_res_url:
                        high_res_url += "&name=orig" if "?" in high_res_url else "?name=orig"

                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                res = requests.get(high_res_url, headers=headers, timeout=15)
                
                # Fallback to standard URL if high_res_url returns non-200
                if res.status_code != 200:
                    res = requests.get(url, headers=headers, timeout=15)

                if res.status_code == 200:
                    content_type = res.headers.get("content-type", "").lower()
                    if "video" in content_type or ".mp4" in url or "video.twimg" in url:
                        file_path = save_dir / f"video_{idx}.mp4"
                        file_path.write_bytes(res.content)
                    elif "gif" in content_type or ".gif" in url or "tweet_video" in url:
                        file_path = save_dir / f"animation_{idx}.gif"
                        file_path.write_bytes(res.content)
                    else:
                        ext = "png" if "format=png" in url or ".png" in url else "jpg"
                        file_path = save_dir / f"image_{idx}.{ext}"
                        file_path.write_bytes(res.content)
                        # Apply PIL Image Quality & Sharpness Enhancement
                        cls.enhance_image(file_path)

                    downloaded.append(file_path)
            except Exception as e:
                print(f"[XCurator] Failed to download/enhance media {url}: {e}")
        return downloaded
