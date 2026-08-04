import asyncio
import random
import sys
import math
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

    async def human_mouse_move(self, start_x: float, start_y: float, end_x: float, end_y: float, steps: int = 15):
        """Simulates smooth human-like mouse movement using cubic Bézier curve interpolation."""
        for i in range(1, steps + 1):
            t = i / steps
            jitter_x = random.uniform(-2, 2)
            jitter_y = random.uniform(-2, 2)
            cur_x = start_x + (end_x - start_x) * (3 * t * t - 2 * t * t * t) + jitter_x
            cur_y = start_y + (end_y - start_y) * (3 * t * t - 2 * t * t * t) + jitter_y
            await self.page.mouse.move(cur_x, cur_y)
            await asyncio.sleep(random.uniform(0.01, 0.03))

    async def scroll_like_human(self, distance: int = 450):
        """Scrolls feed smoothly with randomized micro-bursts and human pauses."""
        steps = random.randint(6, 12)
        step_distance = distance // steps
        for _ in range(steps):
            delta_y = step_distance + random.randint(-15, 15)
            await self.page.mouse.wheel(0, delta_y)
            await asyncio.sleep(random.uniform(0.12, 0.35))
        await asyncio.sleep(random.uniform(0.8, 1.5))

    async def dwell_read_post(self, duration_sec: int = 10):
        """Dwells over a feed post while subtly moving cursor across post elements to mimic reading."""
        print(f"   👁️ [Stealth] Dwell reading feed post for {duration_sec}s...")
        end_time = asyncio.get_event_loop().time() + duration_sec
        start_x, start_y = random.randint(300, 600), random.randint(250, 450)
        await self.page.mouse.move(start_x, start_y)

        while asyncio.get_event_loop().time() < end_time:
            target_x = random.randint(250, 750)
            target_y = random.randint(200, 650)
            await self.human_mouse_move(start_x, start_y, target_x, target_y, steps=random.randint(10, 20))
            start_x, start_y = target_x, target_y
            await asyncio.sleep(random.uniform(1.8, 3.5))

    async def human_type(self, element, text: str):
        """Focuses element and types text letter-by-letter with realistic human keystroke intervals."""
        await element.focus()
        for char in text:
            await self.page.keyboard.type(char, delay=random.randint(30, 85))
            if char in [".", ",", "!", "?"]:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def extract_media_details(self, card) -> str:
        """Extracts media context (image alt text, video titles, article descriptions)."""
        media_parts = []
        try:
            # Images
            imgs = await card.query_selector_all("img")
            for img in imgs:
                alt = await img.get_attribute("alt")
                if alt and len(alt.strip()) > 5 and "profile" not in alt.lower() and "icon" not in alt.lower() and "avatar" not in alt.lower():
                    media_parts.append(f"Image: {alt.strip()}")

            # Videos
            video = await card.query_selector("video, div[class*='video']")
            if video:
                vid_text = (await video.inner_text()).strip()
                if vid_text:
                    media_parts.append(f"Video Content: {vid_text[:100]}")
                else:
                    media_parts.append("Video Content: Embedded video demonstration")

            # Article or Link preview
            article = await card.query_selector("div[class*='article'], a[class*='article']")
            if article:
                art_text = (await article.inner_text()).strip()
                if art_text:
                    media_parts.append(f"Article Preview: {art_text[:120]}")

        except Exception:
            pass

        return " | ".join(media_parts[:2])

    async def find_post_cards(self) -> List[Any]:
        """Finds post cards using multi-layer selectors and DOM inspection fallback."""
        post_selectors = [
            "div[id^='expanded']",
            "div[id*='FeedType_MAIN_FEED_RELEVANCE']",
            "div[data-view-name='feed-full-update']",
            "div.feed-shared-update-v2",
            "div.occludable-update",
            "div[data-urn]"
        ]

        cards = []
        for sel in post_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(cards):
                cards = found

        if not cards:
            # Fallback: Query divs in main container that contain post content or buttons
            cards = await self.page.query_selector_all("main div.scaffold-layout__main div[class*='feed'], main div[class*='update']")

        return cards

    async def process_feed_posts(self, max_posts: int = 3) -> List[Dict[str, Any]]:
        print(f"\n📱 Navigating to LinkedIn Feed (Target Posts: {max_posts}, Preproduction Mode: {self.preproduction})...")
        try:
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ Feed load notice: {e}")

        # Scroll down like a human to load feed items
        await self.scroll_like_human(500)
        await asyncio.sleep(2)

        post_cards = await self.find_post_cards()
        print(f"🔍 Found {len(post_cards)} post cards on feed viewport...")

        engaged_posts = []
        processed_count = 0

        for idx, card in enumerate(post_cards):
            if processed_count >= max_posts:
                break

            try:
                # 1. Scroll post into view with human cursor movement
                try:
                    await card.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await self.scroll_like_human(200)

                # 2. Extract Text Content
                text_el = await card.query_selector("div.update-components-text, span.break-words, div[class*='description'], div[class*='update-components-text']")
                post_text = ""
                if text_el:
                    post_text = (await text_el.inner_text()).strip()
                else:
                    raw_text = (await card.inner_text()).strip()
                    lines = [l.strip() for l in raw_text.splitlines() if len(l.strip()) > 20]
                    post_text = "\n".join(lines[:3]) if lines else ""

                if len(post_text) < 15:
                    continue

                # 3. Dwell read post for realistic timing (8s-14s)
                await self.dwell_read_post(duration_sec=random.randint(8, 14))

                # 4. Extract Author Name
                author_el = await card.query_selector("span.update-components-actor__name, span.feed-shared-actor__name, div[class*='actor__title'], a[class*='actor']")
                author = (await author_el.inner_text()).strip() if author_el else "LinkedIn Creator"

                # 5. Extract Media & Visual Details (Images, Videos, Articles)
                media_desc = await self.extract_media_details(card)

                processed_count += 1
                print(f"\n--- [Feed Post #{processed_count}] ---")
                print(f"👤 Author: {author}")
                print(f"📝 Content: {post_text[:120]}...")
                if media_desc:
                    print(f"🖼️ Media Context: {media_desc}")

                # 6. Generate Curated Gemini AI Comment based on Text + Media
                ai_comment = self.ai.generate_feed_comment(post_text=post_text, author_name=author, media_desc=media_desc)
                print(f"🤖 Gemini AI Comment: \"{ai_comment}\"")

                post_info = {
                    "index": processed_count,
                    "author": author,
                    "post_text": post_text,
                    "media_desc": media_desc,
                    "ai_comment": ai_comment,
                    "preproduction": self.preproduction
                }

                if self.preproduction:
                    print("🧪 [PREPRODUCTION] Staged Like & Comment action safely.")
                else:
                    # Step A: Like the post
                    print("  ├── [LIVE] Liking post...")
                    like_btn = await card.query_selector("button.react-button__trigger, button:has-text('Like'), button[aria-label*='Like']")
                    if like_btn:
                        box = await like_btn.bounding_box()
                        if box:
                            await self.human_mouse_move(400, 400, box['x'] + box['width']/2, box['y'] + box['height']/2)
                        await like_btn.click()
                        await asyncio.sleep(random.uniform(1.5, 3.0))

                    # Step B: Hit Comment Section button
                    print("  ├── [LIVE] Opening comment section...")
                    comment_btn = await card.query_selector("button.comment-button, button:has-text('Comment'), button[aria-label*='Comment']")
                    if comment_btn:
                        box = await comment_btn.bounding_box()
                        if box:
                            await self.human_mouse_move(500, 500, box['x'] + box['width']/2, box['y'] + box['height']/2)
                        await comment_btn.click()
                        await asyncio.sleep(random.uniform(2.0, 3.5))

                    # Step C: Focus comment box & Human Type comment
                    comment_editor = await card.query_selector("div.editor-content, div[contenteditable='true'], div[role='textbox']")
                    if comment_editor:
                        print("  ├── [LIVE] Human typing comment...")
                        await self.human_type(comment_editor, ai_comment)
                        await asyncio.sleep(random.uniform(1.5, 3.0))

                        # Step D: Submit Comment
                        submit_btn = await card.query_selector("button.comments-comment-box__submit-button, button:has-text('Post')")
                        if submit_btn:
                            print("  ├── [LIVE] Submitting comment...")
                            await submit_btn.click()
                            print("🎉 [LIVE] Comment posted successfully!")
                            await asyncio.sleep(random.uniform(3.0, 5.0))

                engaged_posts.append(post_info)

            except Exception as e:
                print(f"⚠️ Error processing feed post #{idx+1}: {e}")

        print(f"\n✅ Completed Feed Engagement Cycle for {len(engaged_posts)} posts.")
        return engaged_posts
