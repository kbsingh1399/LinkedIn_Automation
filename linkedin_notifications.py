import asyncio
import random
import sys
import re
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from gemini_ai import GeminiAIClient
from engagement_tracker import already_engaged, mark_engaged

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInNotificationsEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def process_top_20_notifications(self) -> List[Dict[str, Any]]:
        print(f"\n🔔 Navigating to LinkedIn Notifications...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/notifications/"):
            return []

        # Reset viewport to top before scrolling cards into view
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(3)

        # LinkedIn's notification DOM uses multiple possible container structures.
        # Iterate in priority order; stop as soon as we get real element nodes.
        card_selectors = [
            "article.nt-card",
            "div[class*='nt-card__container']",
            "div[class*='nt-card']",
            "div.notification-item",
            "li.nt-card",
            "div[data-urn]",
            "section.nt-card",
            "[class*='notification-card']",
            "main li",
            "main article",
        ]

        # Human scroll to trigger lazy-loading of notification cards
        for _ in range(3):
            await PlaywrightResilience.human_scroll(self.page, random.randint(600, 900))
            await asyncio.sleep(1.0)

        best_selector = None
        cards = []
        for sel in card_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(cards):
                cards = found
                best_selector = sel
                print(f"✅ [Notifications] Found {len(found)} cards via: {sel}")
            if len(cards) >= 15:
                break

        # Step 6.1 Verification: Screenshot of parsed notifications list
        await self.page.screenshot(path="step6_1_notifications_list.png")

        processed = []
        actionable_keywords = ["replied", "commented", "mentioned", "tagged", "response to your"]
        skip_keywords = ["view jobs", "opportunities in", "viewed your profile", "say happy birthday", "congratulate", "hiring for"]

        # Get initial count for up to 50 notification cards
        card_count = len(cards) if cards else 0
        max_idx = min(card_count, 50)
        
        from engagement_tracker import check_daily_limit
        if check_daily_limit("notification_reply", 20):
            print("🛑 [Rate Limit] Reached 20 notification replies today. Skipping notification module.")
            return []

        for idx in range(max_idx):
            if check_daily_limit("notification_reply", 20):
                break
            try:
                # Re-query elements if we have a best_selector, since navigation destroys old handles
                if best_selector:
                    current_cards = await self.page.query_selector_all(best_selector)
                    if idx >= len(current_cards):
                        continue
                    card = current_cards[idx]
                else:
                    card = cards[idx]

                if not await PlaywrightResilience.is_html_element_card(card):
                    continue

                # Extract notification headline text (e.g. "Manish Kumar, PMP mentioned you in a comment")
                headline_el = await card.query_selector("a.nt-card__headline, [class*='nt-card__headline']")
                text = (await headline_el.inner_text()).strip() if headline_el else (await card.inner_text()).strip()
                if not text:
                    continue

                text_lower = text.lower()
                is_actionable = any(kw in text_lower for kw in actionable_keywords) and not any(sk in text_lower for sk in skip_keywords)

                if not is_actionable:
                    continue

                # Dedup: skip if already replied to this notification within 3 days
                if already_engaged("notification_reply", text[:200]):
                    print(f"  [SKIP] Already replied to notification #{idx+1}. Skipping.")
                    continue

                print(f"\U0001f514 [Actionable Notification #{idx+1}] {text[:80].replace(chr(10), ' ')}...")

                if self.preproduction:
                    ai_reply = await self.ai.generate_notification_reply(text[:200], page=self.page)
                    print(f"[{idx+1:02d}] \U0001f9ea [PREPROD] Reply: {ai_reply[:50]}...")
                    processed.append({"index": idx+1, "reply": ai_reply})
                else:
                        # Step 6.2 Verification: Click thread/card & screenshot thread opened
                        await card.click()
                        await asyncio.sleep(random.uniform(2.0, 3.5))

                        await self.page.bring_to_front()
                        await asyncio.sleep(0.5)

                        # Closed Thread Verification Check: Detect if comments are disabled or thread is closed at our end
                        closed_banner = await self.page.query_selector(
                            "div[class*='comments-disabled'], "
                            "span:has-text('Comments on this post have been turned off'), "
                            "div:has-text('Comments are disabled'), "
                            "p:has-text('Comments turned off')"
                        )
                        if closed_banner:
                            print(f"⏩ [Notification #{idx+1}] Closed thread / comments turned off by author. Navigating back.")
                            mark_engaged("notification_reply", text[:200])
                            await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/notifications/")
                            await self.page.evaluate("window.scrollTo(0, 0)")
                            await asyncio.sleep(2.0)
                            continue

                        # Extract context from the opened page before replying
                        post_context = ""
                        parent_comment = ""
                        post_container = None
                        try:
                            # Try to get the specific post container first
                            post_els = await self.page.query_selector_all("div.feed-shared-update-v2, article")
                            if not post_els:
                                # Fallback to main content area
                                post_els = await self.page.query_selector_all("main, div.core-rail")
                                
                            if post_els:
                                post_container = post_els[0]
                                post_texts = [(await el.inner_text()).strip() for el in post_els]
                                post_texts = [t for t in post_texts if len(t) > 50]
                                if post_texts:
                                    # Increase to 4000 to ensure we capture the actual post even if there is sidebar junk
                                    post_context = post_texts[0][:4000]
                                    
                            # Attempt to grab the specific comment thread explicitly
                            comment_els = await self.page.query_selector_all("div[data-testid*='commentList'], article.comments-comment-item, div.comments-comments-list")
                            if comment_els:
                                parent_comment = (await comment_els[0].inner_text()).strip()[:2000]
                        except Exception as e:
                            print(f"⚠️ Could not extract full context: {e}")
                            
                        # Take high quality targeted screenshot of the post/thread, not the entire page
                        if post_container:
                            try:
                                await post_container.scroll_into_view_if_needed()
                                await post_container.screenshot(path="step6_2_thread_opened.png")
                            except Exception:
                                await self.page.screenshot(path="step6_2_thread_opened.png")
                        else:
                            await self.page.screenshot(path="step6_2_thread_opened.png")
                            
                        # Generate the reply using the full context AND the screenshot!
                        print("🧠 [GEMINI] Generating context-aware reply using text and Vision...")
                        ai_reply = await self.ai.generate_notification_reply(
                            notification_text=text[:200], 
                            post_context=post_context,
                            parent_comment=parent_comment,
                            page=self.page,
                            image_path="step6_2_thread_opened.png"
                        )

                        # 1. First try to find and click a "Reply" button, since we are usually replying to a comment in Notifications
                        reply_clicked = False
                        try:
                            # Prefer "Reply" button inside a highlighted comment block if present
                            highlighted = self.page.locator("article.highlighted, div.highlighted")
                            if await highlighted.count() > 0:
                                reply_locators = highlighted.get_by_role("button", name=re.compile(r"^Reply", re.IGNORECASE))
                            else:
                                reply_locators = self.page.get_by_role("button", name=re.compile(r"^Reply", re.IGNORECASE))
                                
                            if await reply_locators.count() > 0:
                                for i in range(await reply_locators.count()):
                                    btn = reply_locators.nth(i)
                                    if await btn.is_visible():
                                        await btn.scroll_into_view_if_needed()
                                        await btn.click(force=True)
                                        print("💬 Clicked Reply button!")
                                        reply_clicked = True
                                        await asyncio.sleep(1.5)
                                        break
                        except Exception as e:
                            print(f"⚠️ Error clicking Reply via get_by_role: {e}")
                            
                        # Fallback if get_by_role fails
                        if not reply_clicked:
                            try:
                                reply_trigger = await self.page.query_selector(
                                    "button[aria-label='Reply'], "
                                    "button[aria-label*='Reply' i], "
                                    "button.comments-comment-item__reply-button, "
                                    "button[aria-label*='Reply to' i], "
                                    "button:has-text('Reply')"
                                )
                                if reply_trigger and await reply_trigger.is_visible():
                                    await reply_trigger.scroll_into_view_if_needed()
                                    await reply_trigger.click(force=True)
                                    print("💬 Clicked Reply button via query_selector!")
                                    reply_clicked = True
                                    await asyncio.sleep(1.5)
                            except Exception:
                                pass

                        # 2. If we couldn't find a Reply button, maybe it's a top-level post mention. Try clicking "Comment"
                        if not reply_clicked:
                            try:
                                comment_locators = self.page.get_by_role("button", name=re.compile(r"^Comment", re.IGNORECASE))
                                if await comment_locators.count() > 0:
                                    for i in range(await comment_locators.count()):
                                        btn = comment_locators.nth(i)
                                        if await btn.is_visible():
                                            await btn.scroll_into_view_if_needed()
                                            await btn.click(force=True)
                                            print("💬 Clicked Comment button via get_by_role...")
                                            await asyncio.sleep(1.5)
                                            break
                            except Exception:
                                pass
                                
                        # 3. Body-level last-visible editor (never scoped to the notification card)
                        editor = await PlaywrightResilience.find_last_visible_editor(self.page)

                        if editor:
                            await editor.scroll_into_view_if_needed()
                            await editor.click(force=True)
                            await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                            await PlaywrightResilience.random_thinking_pause()

                            # Step 6.3 Verification: Screenshot reply typed
                            await self.page.screenshot(path="step6_3_reply_typed.png")

                            # Strict selectors for the Reply/Post submit button
                            # We get the LAST visible submit button to ensure it matches the nested reply box we just opened
                            submit_locators = self.page.locator(
                                "button[componentkey*='commentButtonSection' i], "
                                "button.comments-comment-box__submit-button, "
                                "button:has-text('Reply'), "
                                "button:has-text('Post'), "
                                "button.artdeco-button--primary[type='submit']"
                            )
                            submit_btn = None
                            count = await submit_locators.count()
                            for i in range(count - 1, -1, -1):
                                el = submit_locators.nth(i)
                                if await el.is_visible():
                                    submit_btn = await el.element_handle()
                                    break
                            
                            if submit_btn:
                                # Verify the button is visible + enabled before clicking
                                is_vis = await submit_btn.is_visible()
                                is_dis = await submit_btn.get_attribute("disabled")
                                btn_text = (await submit_btn.inner_text()).strip()[:30]
                                print(f"  [DOM] Submit btn found: text={btn_text!r} visible={is_vis} disabled={is_dis}")
                                if is_vis and is_dis is None:
                                    try:
                                        await submit_btn.click(force=True, timeout=4000)
                                    except Exception:
                                        await submit_btn.evaluate("b => b.click()")
                                    print("\U0001f680 Reply submitted!")
                                    await asyncio.sleep(random.uniform(3.5, 6.0))

                                    # Step 6.3 Verification: Screenshot reply posted
                                    await self.page.screenshot(path="step6_3_reply_posted.png")
                                    print(f"[{idx+1:02d}] \u2705 Reply posted")
                                    processed.append({"index": idx+1, "reply": ai_reply})
                                    mark_engaged("notification_reply", text[:200])
                                else:
                                    print(f"\u26a0\ufe0f Submit btn disabled/hidden — skipping click (visible={is_vis}, disabled={is_dis})")
                            else:
                                print(f"⚠️ Could not find Reply/Post submit button for Notification #{idx+1}")
                        else:
                            print(f"⏩ [Notification #{idx+1}] No reply box on clicked page (e.g. company/school profile). Navigating back.")

                        await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/notifications/")
                        await self.page.evaluate("window.scrollTo(0, 0)")
                        await self.page.bring_to_front()
                        # Extended sleep to ensure page DOM re-renders before re-querying cards
                        await asyncio.sleep(2.5)

            except Exception as e:
                print(f"⚠️ Notification #{idx+1} error: {e}")
                continue

        print(f"✅ Notifications processed: {len(processed)} (from {len(cards)} cards found)")
        return processed
