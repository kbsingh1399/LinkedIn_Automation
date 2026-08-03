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

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def perform_automated_x_login(page, username: str, password: str) -> bool:
    """Bulletproof automated X.com login sequence."""
    print(f"🔑 Performing automated login for user: @{username} ...")
    try:
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        # Step 1: Fill Username
        print("  ├── Filling username...")
        user_selector = "input[autocomplete='username'], input[name='text'], input[type='text']"
        user_input = await page.wait_for_selector(user_selector, timeout=15000)
        if user_input:
            await user_input.fill(username)
            await page.wait_for_timeout(1000)
            
            # Click 'Next' button or press Enter
            next_btn = await page.query_selector("button:has-text('Next'), div[role='button']:has-text('Next')")
            if next_btn:
                await next_btn.click()
            else:
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)

        # Step 2: Handle unusual activity / phone / email prompt if present
        pass_input = await page.query_selector("input[name='password']")
        if not pass_input:
            verify_input = await page.query_selector("input[data-testid='ocfEnterTextTextInput'], input[name='text']")
            if verify_input:
                print("  ├── Verification step detected, filling username...")
                await verify_input.fill(username)
                await page.wait_for_timeout(1000)
                next_btn = await page.query_selector("button:has-text('Next'), div[role='button']:has-text('Next')")
                if next_btn:
                    await next_btn.click()
                else:
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(4000)

        # Step 3: Fill Password
        print("  ├── Filling password...")
        pass_input = await page.wait_for_selector("input[name='password']", timeout=15000)
        if pass_input:
            await pass_input.fill(password)
            await page.wait_for_timeout(1000)

            # Click 'Log in' button or press Enter
            login_btn = await page.query_selector("button:has-text('Log in'), div[role='button']:has-text('Log in')")
            if login_btn:
                await login_btn.click()
            else:
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(6000)

        print("  └── Login form submitted! Checking home feed...")
        return "home" in page.url or page.url.strip("/") == "https://x.com"

    except Exception as e:
        print(f"⚠️ Login sequence notice: {e}")
        return False

async def curate_with_persistent_chrome(topics: list[str], total_count: int = 4, headless: bool = False):
    user_data_dir = settings.user_data_dir
    user_data_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Launching Persistent Chrome Session (Profile: {user_data_dir.resolve()})...")
    print(f"📌 Target Topics: {topics}")
    print(f"📊 Target Count: {total_count}\n")

    curated_posts = []
    posts_per_topic = max(1, total_count // len(topics))

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # Step 1: Verify Login
        print("🔍 Checking X.com home page...")
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print("Notice navigating to home:", e)

        print("Current URL:", page.url)

        # Check if logged in
        if "login" in page.url or "onboarding" in page.url or page.url.strip("/") == "https://x.com":
            username = settings.x_username
            password = settings.x_password
            if username and password:
                await perform_automated_x_login(page, username, password)

            await page.wait_for_timeout(3000)
            print("Current URL after login attempt:", page.url)
            print("✅ X.com persistent session ready!\n")

        # Step 2: Search topics live
        for topic in topics:
            print(f"🔎 Searching X.com live for topic: '{topic}'...")
            search_url = f"https://x.com/search?q={urllib.parse.quote(topic)}&f=top"

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Notice navigating to search '{topic}':", e)

            # Scroll feed live to load tweets
            for scroll_idx in range(6):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(2000)

            tweet_elements = await page.query_selector_all("article")
            print(f"   Found {len(tweet_elements)} raw tweet articles on X.com for '{topic}'")

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

        await context.close()

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
    asyncio.run(curate_with_persistent_chrome(topics=topics, total_count=4, headless=False))
