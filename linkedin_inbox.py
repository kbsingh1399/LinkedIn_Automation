import asyncio
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from gemini_ai import GeminiAIClient

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInInboxEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def process_top_20_messages(self) -> List[Dict[str, Any]]:
        print(f"\n💬 Navigating to LinkedIn Messaging (Scanning Top 20 Conversations, Preproduction Mode: {self.preproduction})...")
        try:
            await self.page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ Messaging load notice: {e}")

        # Query conversation list items
        conv_selectors = [
            "li.msg-conversation-listitem",
            "div.msg-conversation-card",
            "a.msg-conversation-card__link",
            "div.msg-conversation-listitem__link"
        ]

        conv_cards = []
        for sel in conv_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(conv_cards):
                conv_cards = found

        print(f"🔍 Found {len(conv_cards)} messaging conversations. Auditing top 20...")

        top_convs = conv_cards[:20]
        processed_conversations = []

        for idx, card in enumerate(top_convs, start=1):
            try:
                name_el = await card.query_selector("h3.msg-conversation-listitem__participant-names, span.msg-conversation-card__participant-names, span.msg-conversation-listitem__participant-names")
                partner_name = (await name_el.inner_text()).strip() if name_el else f"Connection #{idx}"

                unread_el = await card.query_selector("div.msg-conversation-card__unread-count, span.msg-conversation-card__unread-count")
                is_unread = unread_el is not None

                snippet_el = await card.query_selector("p.msg-conversation-card__message-snippet, span.msg-conversation-card__message-snippet")
                snippet = (await snippet_el.inner_text()).strip() if snippet_el else ""

                status_tag = "[UNREAD]" if is_unread else "[OPEN/READ]"
                print(f"  [{idx:02d}] {status_tag} {partner_name}: {snippet[:70]}...")

                await card.click()
                await asyncio.sleep(2)

                history_elems = await self.page.query_selector_all("li.msg-s-message-list__item, p.msg-s-event-listitem__body")
                recent_history = []
                for h_el in history_elems[-5:]:
                    txt = (await h_el.inner_text()).strip()
                    if txt:
                        recent_history.append(txt[:150])

                history_context = "\n".join(recent_history) if recent_history else snippet

                ai_reply = self.ai.generate_inbox_reply(chat_history=history_context, partner_name=partner_name)

                conv_data = {
                    "index": idx,
                    "partner_name": partner_name,
                    "unread": is_unread,
                    "context_snippet": history_context[:200],
                    "ai_reply": ai_reply,
                    "preproduction": self.preproduction
                }
                processed_conversations.append(conv_data)

                if self.preproduction:
                    print(f"      🧪 [PREPRODUCTION] Conversation context loaded. Staged Gemini Reply: \"{ai_reply}\"")
                else:
                    if is_unread:
                        print(f"      🚀 [LIVE] Entering reply into message editor for {partner_name}...")
                        editor = await self.page.query_selector("div.msg-form__contenteditable[contenteditable='true']")
                        if editor:
                            await editor.focus()
                            await editor.fill(ai_reply)
                            await asyncio.sleep(2)

                            send_btn = await self.page.query_selector("button.msg-form__send-button")
                            if send_btn:
                                await send_btn.click()
                                print(f"      🎉 [LIVE] Message sent to {partner_name}!")
                                await asyncio.sleep(3)

            except Exception as e:
                print(f"⚠️ Error processing conversation #{idx}: {e}")

        print(f"\n✅ Completed Inbox Audit: Processed top {len(processed_conversations)} messaging conversations.")
        return processed_conversations
