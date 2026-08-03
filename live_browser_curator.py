import asyncio
import os
import sys
import json
import urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from linkedin_rewriter import LinkedInRewriter
from post_exporter import PostExporter

# Ensure UTF-8 stdout encoding for Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def safe_goto(page, url: str, retries: int = 3):
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            return True
        except Exception as e:
            print(f"⚠️ Navigation attempt {attempt}/{retries} notice for '{url}': {e}")
            await asyncio.sleep(2)
    return False

async def curate_live_x_posts(topics: list[str], total_count: int = 4):
    state_file = settings.user_data_dir / "storage_state.json"
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Opening Visible Browser to search X.com live...")
    print(f"📌 Target Topics: {topics}")
    print(f"📊 Target Count: {total_count}\n")

    curated_posts = []
    posts_per_topic = max(1, total_count // len(topics))

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

        # Step 1: Check login status on X.com
        print("🔍 Checking X.com login session...")
        await safe_goto(page, "https://x.com/home")
        await page.wait_for_timeout(3000)

        if "login" in page.url or "onboarding" in page.url:
            print("\n🔑 Login required! Navigating to X.com login page...")
            await safe_goto(page, "https://x.com/i/flow/login")
            
            username = settings.x_username
            password = settings.x_password
            if username and password:
                print(f"🔑 Auto-filling login for '@{username}'...")
                try:
                    user_input = await page.wait_for_selector("input[autocomplete='username'], input[name='text']", timeout=10000)
                    if user_input:
                        await user_input.fill(username)
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(3000)

                    pass_input = await page.query_selector("input[name='password']")
                    if not pass_input:
                        extra_input = await page.query_selector("input[data-testid='ocfEnterTextTextInput'], input[name='text']")
                        if extra_input:
                            await extra_input.fill(username)
                            await page.keyboard.press("Enter")
                            await page.wait_for_timeout(3000)

                    pass_input = await page.wait_for_selector("input[name='password']", timeout=10000)
                    if pass_input:
                        await pass_input.fill(password)
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"⚠️ Auto-fill login notice: {e}")

            if "login" in page.url or "onboarding" in page.url:
                print("\n👉 Please complete your login on the opened browser window!")
                print("   The script will automatically detect when you are logged in...\n")
                while "login" in page.url or "onboarding" in page.url:
                    await asyncio.sleep(2)

            await context.storage_state(path=str(state_file))
            print("✅ X.com login session verified and saved!\n")

        # Step 2: Search topics and extract REAL live posts
        for topic in topics:
            print(f"🔎 Searching X.com live for topic: '{topic}'...")
            encoded_topic = urllib.parse.quote(topic)
            search_url = f"https://x.com/search?q={encoded_topic}&f=top"

            await safe_goto(page, search_url)
            await page.wait_for_timeout(4000)

            # Scroll feed to load live tweets
            for scroll_idx in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)

            # Query all tweet containers
            tweet_elements = await page.query_selector_all("article, [data-testid='cellInner']")
            print(f"   Found {len(tweet_elements)} raw tweet elements on X.com for '{topic}'")

            topic_posts = []
            for t_el in tweet_elements:
                try:
                    text_el = await t_el.query_selector("div[data-testid='tweetText']")
                    text = await text_el.inner_text() if text_el else ""
                    if not text or len(text) < 20:
                        continue

                    # Extract image URLs
                    img_els = await t_el.query_selector_all("div[data-testid='tweetPhoto'] img, img[src*='media']")
                    media_urls = []
                    for img in img_els:
                        src = await img.get_attribute("src")
                        if src and "media" in src and "profile_images" not in src and "svg" not in src:
                            media_urls.append(src)

                    # STRICT REQUIREMENT: Only posts with images
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
                            likes = int(float(await like_el.inner_text().replace('K', '000').replace('M', '000000')))
                        rt_el = await t_el.query_selector("[data-testid='retweet'] span")
                        if rt_el:
                            retweets = int(float(await rt_el.inner_text().replace('K', '000').replace('M', '000000')))
                    except:
                        pass

                    score = likes + (retweets * 2)

                    topic_posts.append({
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

            topic_posts.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
            curated_topic = topic_posts[:posts_per_topic]
            print(f"✅ Selected {len(curated_topic)} REAL X posts with images for '{topic}'")
            curated_posts.extend(curated_topic)

        await browser.close()

    print(f"\n✍️ Rewriting {len(curated_posts)} REAL X posts for LinkedIn & exporting...")
    rewriter = LinkedInRewriter()
    exporter = PostExporter()

    for idx, post_data in enumerate(curated_posts, start=1):
        rewritten = rewriter.rewrite_for_linkedin(post_data)
        out_dir = exporter.export_post(idx, post_data, rewritten)
        print(f"  └── [{idx}/{len(curated_posts)}] Exported to: {out_dir}")
        print(f"      Source URL: {post_data['url']}")

    print(f"\n🎉 Successfully processed {len(curated_posts)} REAL X posts!")
    print(f"📁 Output Directory: {settings.output_dir.resolve()}")

if __name__ == "__main__":
    topics = ["AI", "Python"]
    asyncio.run(curate_live_x_posts(topics=topics, total_count=4))
