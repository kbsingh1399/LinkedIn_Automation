import asyncio
import random
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from gemini_ai import GeminiAIClient

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInInboxEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def extract_full_chat_history(self, partner_name: str) -> str:
        try:
            items = await self.page.query_selector_all("li.msg-s-message-list__item, div.msg-s-event-listitem")
            history = []
            for item in items[-7:]:
                text_el = await item.query_selector("p.msg-s-event-listitem__body")
                if text_el:
                    history.append(await text_el.inner_text())
            return "\n".join(history) if history else f"{partner_name}: Started conversation."
        except:
            return f"{partner_name}: Conversation started."

    async def process_top_20_messages(self) -> List[Dict[str, Any]]:
        print(f"\n💬 Navigating to LinkedIn Messaging...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/messaging/"):
            return []

        cards = await self.page.query_selector_all(",".join(PlaywrightResilience.get("message_card")))
        processed = []

        for idx, card in enumerate(cards[:20], 1):
            try:
                name_el = await card.query_selector("h3, span.msg-conversation-card__participant-names")
                partner = await name_el.inner_text() if name_el else f"Connection #{idx}"

                await card.click()
                await asyncio.sleep(random.uniform(1.8, 3.0))

                history = await self.extract_full_chat_history(partner)
                ai_reply = await self.ai.generate_inbox_reply(history, partner, page=self.page)

                if self.preproduction:
                    print(f"[{idx:02d}] 🧪 [PREPROD] Reply to {partner}: {ai_reply[:50]}...")
                    processed.append({"partner": partner, "reply": ai_reply})
                else:
                    editor = await self.page.query_selector("div.msg-form__contenteditable[contenteditable='true'], div[role='textbox']")
                    if editor:
                        await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                        await PlaywrightResilience.random_thinking_pause()

                        send_btn = await self.page.query_selector("button[aria-label*='Send'], button.msg-form__send-button")
                        if send_btn:
                            await send_btn.click()
                            await asyncio.sleep(random.uniform(3.5, 6.0))
                            print(f"[{idx:02d}] ✅ Message sent to {partner}")
                            processed.append({"partner": partner, "reply": ai_reply})

            except Exception as e:
                print(f"⚠️ Inbox #{idx} error: {e}")
                continue

        print(f"✅ Inbox processed: {len(processed)}")
        return processed
