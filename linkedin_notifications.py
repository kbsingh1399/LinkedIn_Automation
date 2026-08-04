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

        cards = await self.page.query_selector_all(",".join(PlaywrightResilience.get("notification_card")))
        processed = []

        for idx, card in enumerate(cards[:20], 1):
            try:
                text = await card.inner_text()
                is_actionable = any(kw in text.lower() for kw in ["replied", "commented", "mentioned"])

                if is_actionable:
                    ai_reply = await self.ai.generate_notification_reply(text[:200], page=self.page)

                    if self.preproduction:
                        print(f"[{idx:02d}] 🧪 [PREPROD] Reply: {ai_reply[:50]}...")
                        processed.append({"index": idx, "reply": ai_reply})
                    else:
                        await card.click()
                        await asyncio.sleep(random.uniform(2.0, 3.5))

                        editor = await self.page.query_selector("div[contenteditable='true'], div[role='textbox']")
                        if editor:
                            await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                            await PlaywrightResilience.random_thinking_pause()

                            submit_btn = await self.page.query_selector("button[aria-label*='Post comment'], button.comments-comment-box__submit-button")
                            if submit_btn:
                                await submit_btn.click()
                                await asyncio.sleep(random.uniform(3.5, 6.0))
                                print(f"[{idx:02d}] ✅ Reply posted")

                        await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/notifications/")
                        await asyncio.sleep(1.5)

            except Exception as e:
                print(f"⚠️ Notification #{idx} error: {e}")
                continue

        print(f"✅ Notifications processed: {len(processed)}")
        return processed
