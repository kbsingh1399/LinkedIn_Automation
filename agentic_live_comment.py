import asyncio
import sys
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from gemini_ai import GeminiAIClient
from engagement_tracker import mark_engaged, already_engaged
from utils.stealth_chrome import launch_stealth_chrome, apply_stealth_window
from utils.playwright_utils import PlaywrightResilience

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def run_agentic_comment():
    print("=" * 70)
    print(" 🚀 AGENTIC CONTROL — LIVE LINKEDIN FEED COMMENT ENGAGEMENT")
    print("=" * 70)

    cdp_active = await check_cdp(9222)

    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connecting to user's debug Chrome instance at http://localhost:9222 via CDP...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            await apply_stealth_window(context, page)
        else:
            print("🚀 Launching visible persistent Chrome session...")
            context, page = await launch_stealth_chrome(p, profile="linkedin")

        if "linkedin.com/feed" not in page.url:
            print("🌐 Navigating to https://www.linkedin.com/feed/ ...")
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

        print(f"📌 Active Page: {page.url}")

        # Scroll viewport slightly to trigger post card loading
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(2)

        # Step 1: Locate top feed post card
        print("\n🔍 Locating target post card on feed...")
        cards = await page.query_selector_all(
            "div.feed-shared-update-v2, "
            "div[data-id], "
            "article, "
            "div.occludable-update, "
            "[role='article'], "
            "div.scaffold-finite-scroll__content > div"
        )
        print(f"   Found {len(cards)} candidate post container elements.")
        if not cards:
            print("❌ No feed post cards found.")
            return

        target_card = None
        post_text = ""
        author_name = "LinkedIn Creator"

        for card in cards:
            # Expand "...more" if present
            try:
                see_more = await card.query_selector("button:has-text('...more')")
                if see_more:
                    await see_more.click(force=True)
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Extract author and text
            author_el = await card.query_selector("span.update-components-actor__name, span.feed-shared-actor__name")
            if author_el:
                author_name = (await author_el.inner_text()).strip().splitlines()[0]

            text_el = await card.query_selector("div.update-components-update-activity__commentary, div.feed-shared-update-v2__description-text, span.break-words")
            if text_el:
                post_text = (await text_el.inner_text()).strip()

            if len(post_text) > 30:
                target_card = card
                break

        if not target_card:
            print("⚠️ Could not extract valid post text from feed.")
            return

        print(f"👤 Author: {author_name}")
        print(f"📝 Post Text Preview: {post_text[:120]!r}...")

        # Step 2: Generate Comment via Gemini AI
        print("\n🤖 Generating tailored comment via Gemini AI...")
        ai_client = GeminiAIClient()
        ai_comment = await ai_client.generate_feed_comment(post_text=post_text, author_name=author_name)

        if not ai_comment:
            ai_comment = f"Great perspective on this! The operational tradeoffs here really highlight how critical adaptability is in complex workflows."

        print(f"💬 Generated Comment: {ai_comment!r}")

        # Step 3: Scroll target post into view and Like post
        await target_card.scroll_into_view_if_needed()
        await asyncio.sleep(1)

        print("\n👍 Liking target post...")
        like_btn = await target_card.query_selector("button[aria-label*='React'], button[aria-label*='Like']")
        if like_btn:
            try:
                await like_btn.click()
                await page.screenshot(path="step1_post_liked.png")
                print("  ✅ Post liked successfully.")
            except Exception as e:
                print(f"  ℹ️ Like button click notice: {e}")

        # Step 4: Open Comment Editor
        print("\n💬 Opening Comment Editor...")
        comment_btn = await target_card.query_selector("button[aria-label*='Comment']")
        if comment_btn:
            await comment_btn.click()
            await asyncio.sleep(1.5)

        editor = await PlaywrightResilience.find_last_visible_editor(page)

        if not editor:
            print("❌ Could not locate TipTap comment editor box.")
            return

        # Step 5: Type Comment into Editor
        print("✍️ Typing comment into TipTap rich text editor...")
        await PlaywrightResilience.human_type_with_mistakes(page, editor, ai_comment)
        await asyncio.sleep(1.5)

        await page.screenshot(path="step4_comment_written.png")
        print("  ✅ Comment typed. Saved screenshot to step4_comment_written.png")

        # Step 6: Submit/Post Comment
        print("\n🚀 Submitting comment live on LinkedIn...")
        submit_btn = await target_card.query_selector(
            "button.comments-comment-box__submit-button, "
            "form.comments-comment-box__form button.artdeco-button--primary, "
            "div.comments-comment-box__submit button.artdeco-button--primary, "
            "button.artdeco-button--primary[type='submit']"
        )

        if submit_btn and await submit_btn.is_enabled():
            await submit_btn.click()
            await asyncio.sleep(3)
            print("  ✅ Clicked Submit button!")
        else:
            # Fallback: Press Control+Enter inside the editor
            print("  ℹ️ Using Control+Enter key shortcut to post comment...")
            await editor.focus()
            await page.keyboard.press("Control+Enter")
            await asyncio.sleep(3)

        await page.screenshot(path="step5_comment_posted.png")
        print("  ✅ Comment posted live! Saved screenshot to step5_comment_posted.png")

        # Log engagement to database
        mark_engaged("feed_comment", f"{author_name}::{post_text[:200]}")

        print("\n" + "=" * 70)
        print("🎉 AGENTIC COMMENT ENGAGEMENT SUCCESSFULLY COMPLETED!")
        print(f"👤 Author: {author_name}")
        print(f"💬 Posted Comment: {ai_comment}")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_agentic_comment())
