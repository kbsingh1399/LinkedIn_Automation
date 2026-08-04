import asyncio
import random
import sys
from pathlib import Path
from typing import List, Dict, Any
from playwright.async_api import Page
from config import settings
from gemini_ai import GeminiAIClient

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInFeedEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def scroll_like_human(self, distance: int = 400):
        steps = random.randint(5, 10)
        step_distance = distance // steps
        for _ in range(steps):
            await self.page.mouse.wheel(0, step_distance)
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def dwell_read_post(self, duration_sec: int = 10):
        print(f"   [Stealth] Dwell reading feed post for {duration_sec}s...")
        end_time = asyncio.get_event_loop().time() + duration_sec
        while asyncio.get_event_loop().time() < end_time:
            x = random.randint(200, 800)
            y = random.randint(200, 600)
            await self.page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(1.5, 3.0))

    async def process_feed_posts(self, max_posts: int = 5) -> List[Dict[str, Any]]:
        print(f"\n📱 Navigating to LinkedIn Feed (Target Posts: {max_posts}, Preproduction Mode: {self.preproduction})...")
        try:
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ Feed load warning: {e}")

        # Scroll to load feed items
        await self.scroll_like_human(500)
        await asyncio.sleep(3)

        engaged_posts = []

        # Comprehensive post selectors
        post_selectors = [
            "div[data-view-name='feed-full-update']",
            "div.feed-shared-update-v2",
            "div[data-urn]",
            "div[data-id]",
            "div.occludable-update"
        ]

        post_cards = []
        for sel in post_selectors:
            cards = await self.page.query_selector_all(sel)
            if cards and len(cards) > len(post_cards):
                post_cards = cards

        print(f"🔍 Found {len(post_cards)} posts on feed viewport...")

        processed_count = 0
        for idx, card in enumerate(post_cards):
            if processed_count >= max_posts:
                break

            try:
                await card.scroll_into_view_if_needed()
                await self.scroll_like_human(200)
                await self.dwell_read_post(duration_sec=random.randint(6, 12))

                # Extract Author
                author_el = await card.query_selector("span.update-components-actor__name, span.feed-shared-actor__name, div.update-components-actor__title")
                author = (await author_el.inner_text()).strip() if author_el else "LinkedIn Creator"

                # Extract Post Text
                text_el = await card.query_selector("div.update-components-text, span.break-words, div.feed-shared-update-v2__description")
                post_text = (await text_el.inner_text()).strip() if text_el else ""

                if len(post_text) < 15:
                    continue

                processed_count += 1
                print(f"\n--- [Feed Post #{processed_count}] ---")
                print(f"👤 Author: {author}")
                print(f"📝 Content: {post_text[:120]}...")

                # Generate Gemini AI Comment
                ai_comment = self.ai.generate_feed_comment(post_text=post_text, author_name=author)
                print(f"🤖 Gemini AI Comment: \"{ai_comment}\"")

                post_info = {
                    "index": processed_count,
                    "author": author,
                    "post_text": post_text,
                    "ai_comment": ai_comment,
                    "preproduction": self.preproduction
                }

                if self.preproduction:
                    print("🧪 [PREPRODUCTION] Staged Like & Comment action safely.")
                else:
                    print("  ├── [LIVE] Clicking Like button...")
                    like_btn = await card.query_selector("button.react-button__trigger, button:has-text('Like')")
                    if like_btn:
                        await like_btn.click()
                        await asyncio.sleep(2)

                    print("  ├── [LIVE] Entering comment into post...")
                    comment_box_btn = await card.query_selector("button.comment-button, button:has-text('Comment')")
                    if comment_box_btn:
                        await comment_box_btn.click()
                        await asyncio.sleep(2)

                    comment_input = await card.query_selector("div.editor-content, div[contenteditable='true']")
                    if comment_input:
                        await comment_input.focus()
                        await comment_input.fill(ai_comment)
                        await asyncio.sleep(2)

                        submit_comment_btn = await card.query_selector("button.comments-comment-box__submit-button")
                        if submit_comment_btn:
                            await submit_comment_btn.click()
                            print("🎉 [LIVE] Comment posted successfully!")
                            await asyncio.sleep(3)

                engaged_posts.append(post_info)

            except Exception as e:
                print(f"⚠️ Error processing feed post #{idx+1}: {e}")

        print(f"\n✅ Completed Feed Engagement Cycle for {len(engaged_posts)} posts.")
        return engaged_posts
