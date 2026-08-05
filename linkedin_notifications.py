import asyncio
import random
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from gemini_ai import GeminiAIClient

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
            "div.notification-item",
            "li.nt-card",
            "div[data-urn]",
            "section.nt-card",
            "[class*='notification-card']",
            "main li",
            "main article",
        ]

        # Scroll down to load more notification cards if available
        for _ in range(3):
            await self.page.mouse.wheel(0, 800)
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
        skip_keywords = ["view jobs", "opportunities in", "viewed your profile", "birthday", "work anniversary", "hiring for"]

        # Get initial count for up to 50 notification cards
        card_count = len(cards) if cards else 0
        max_idx = min(card_count, 50)
        
        for idx in range(max_idx):
            try:
                # Re-query elements if we have a best_selector, since navigation destroys old handles
                if best_selector:
                    current_cards = await self.page.query_selector_all(best_selector)
                    if idx >= len(current_cards):
                        continue
                    card = current_cards[idx]
                else:
                    card = cards[idx]

                text = (await card.inner_text()).strip()
                if not text:
                    continue

                text_lower = text.lower()
                is_actionable = any(kw in text_lower for kw in actionable_keywords) and not any(sk in text_lower for sk in skip_keywords)

                if not is_actionable:
                    continue

                print(f"🔔 [Actionable Notification #{idx+1}] {text[:80].replace(chr(10), ' ')}...")
                ai_reply = await self.ai.generate_notification_reply(text[:200], page=self.page)

                if self.preproduction:
                    print(f"[{idx+1:02d}] 🧪 [PREPROD] Reply: {ai_reply[:50]}...")
                    processed.append({"index": idx+1, "reply": ai_reply})
                else:
                        # Step 6.2 Verification: Click thread/card & screenshot thread opened
                        await card.click()
                        await asyncio.sleep(random.uniform(2.0, 3.5))

                        await self.page.bring_to_front()
                        await asyncio.sleep(0.5)

                        await self.page.screenshot(path="step6_2_thread_opened.png")

                        editor = await self.page.query_selector("div.comments-comment-box__content-inline div[contenteditable='true'], div.comments-comment-box div[contenteditable='true'], div[contenteditable='true'][role='textbox'], div[contenteditable='true']")
                        if not editor:
                            # 1. Try clicking Comment button on the post card to expand comment section
                            comment_trigger = await self.page.query_selector("button:has-text('Comment'), button[aria-label*='Comment' i], button.comment-button")
                            if comment_trigger:
                                try:
                                    if await comment_trigger.is_visible():
                                        await comment_trigger.scroll_into_view_if_needed()
                                        await comment_trigger.click(force=True)
                                        print("💬 Clicked Comment button on post...")
                                        await asyncio.sleep(1.5)
                                        editor = await self.page.query_selector("div[contenteditable='true'][role='textbox'], div[contenteditable='true']")
                                except Exception as c_err:
                                    print(f"⚠️ Notice clicking comment trigger: {c_err}")

                        if not editor:
                            # 2. Try clicking Reply button under comment thread
                            reply_trigger = await self.page.query_selector(
                                "button.comments-comment-social-bar__action-tab, "
                                "button.comments-comment-item__reply-button, "
                                "button[aria-label*='Reply to' i], "
                                "button[aria-label*='Reply' i], "
                                "button:has-text('Reply')"
                            )
                            if reply_trigger:
                                try:
                                    if await reply_trigger.is_visible():
                                        await reply_trigger.scroll_into_view_if_needed()
                                        await reply_trigger.click(force=True)
                                        print("💬 Clicked Reply button under comment thread!")
                                        await asyncio.sleep(1.5)
                                        editor = await self.page.query_selector("div[contenteditable='true'][role='textbox'], div[contenteditable='true']")
                                except Exception as trig_err:
                                    print(f"⚠️ Notice clicking reply trigger: {trig_err}")

                        if editor:
                            await editor.scroll_into_view_if_needed()
                            await editor.click(force=True)
                            await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                            await PlaywrightResilience.random_thinking_pause()

                            # Step 6.3 Verification: Screenshot reply typed
                            await self.page.screenshot(path="step6_3_reply_typed.png")

                            # Match submit button strictly by aria-label='Reply', text, or primary class
                            submit_btn = await self.page.query_selector(
                                "button[aria-label='Reply' i], "
                                "button[aria-label*='Reply' i], "
                                "button[aria-label*='Post comment' i], "
                                "button[aria-label*='Post' i], "
                                "button.comments-comment-box__submit-button, "
                                "button:has-text('Reply'), "
                                "button:has-text('Post'), "
                                "button.artdeco-button--primary"
                            )
                            if submit_btn:
                                try:
                                    await submit_btn.click(force=True, timeout=4000)
                                except Exception:
                                    await submit_btn.evaluate("b => b.click()")
                                print("🚀 Clicked Reply / Post submit button!")
                                await asyncio.sleep(random.uniform(3.5, 6.0))

                                # Step 6.3 Verification: Screenshot reply posted
                                await self.page.screenshot(path="step6_3_reply_posted.png")
                                print(f"[{idx+1:02d}] ✅ Reply posted")
                                processed.append({"index": idx+1, "reply": ai_reply})
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
