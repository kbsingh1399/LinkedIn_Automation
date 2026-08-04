import asyncio
import random
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

    async def human_type(self, element, text: str):
        """Types text letter-by-letter with realistic human keystroke timing."""
        await element.focus()
        for char in text:
            await self.page.keyboard.type(char, delay=random.randint(30, 80))
            if char in [".", ",", "!", "?"]:
                await asyncio.sleep(random.uniform(0.2, 0.4))

    async def extract_full_chat_history(self, partner_name: str) -> str:
        """Reads the entire visible conversation history in the active chat thread."""
        try:
            message_items = await self.page.query_selector_all("li.msg-s-message-list__item, div.msg-s-event-listitem")
            full_history = []

            for item in message_items:
                sender_el = await item.query_selector("span.msg-s-message-group__name, span.msg-s-message-group__profile-link")
                sender = (await sender_el.inner_text()).strip() if sender_el else "User"

                text_el = await item.query_selector("p.msg-s-event-listitem__body, div.msg-s-event-listitem__message-bubble")
                text = (await text_el.inner_text()).strip() if text_el else ""

                if text:
                    full_history.append(f"{sender}: {text}")

            if full_history:
                return "\n".join(full_history)
        except Exception as e:
            print(f"⚠️ Chat history extraction notice: {e}")

        return f"{partner_name}: Conversation started."

    async def process_top_20_messages(self) -> List[Dict[str, Any]]:
        print(f"\n💬 Navigating to LinkedIn Messaging (Scanning Top 20 Conversations, Preproduction Mode: {self.preproduction})...")
        try:
            await self.page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ Messaging load notice: {e}")

        # Query conversation cards
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
                print(f"\n  [{idx:02d}] {status_tag} Chat with {partner_name}")
                print(f"      Snippet: {snippet[:80]}...")

                # Click conversation card to open thread
                await card.click()
                await asyncio.sleep(random.uniform(2.0, 3.5))

                # Extract Entire Chat History
                full_history = await self.extract_full_chat_history(partner_name=partner_name)
                print(f"      📖 Read Entire Conversation History ({len(full_history.splitlines())} messages loaded)")

                # Generate Curated Gemini AI Reply based on Full Chat Thread
                ai_reply = await self.ai.generate_inbox_reply(chat_history=full_history, partner_name=partner_name, page=self.page)

                conv_data = {
                    "index": idx,
                    "partner_name": partner_name,
                    "unread": is_unread,
                    "chat_history": full_history,
                    "ai_reply": ai_reply,
                    "preproduction": self.preproduction
                }
                processed_conversations.append(conv_data)

                if self.preproduction:
                    print(f"      🧪 [PREPRODUCTION] Staged Gemini Reply: \"{ai_reply}\"")
                else:
                    if is_unread:
                        print(f"      🚀 [LIVE] Entering reply into message editor for {partner_name}...")
                        editor = await self.page.query_selector("div.msg-form__contenteditable[contenteditable='true'], div[role='textbox']")
                        if editor:
                            await self.human_type(editor, ai_reply)
                            await asyncio.sleep(random.uniform(1.5, 3.0))

                            send_btn = None
                            try:
                                # Find send button in the messaging form container
                                js_code = """(editor) => {
                                    let parent = editor.parentElement;
                                    while (parent && parent.tagName !== 'MAIN') {
                                        const btns = Array.from(parent.querySelectorAll('button'));
                                        const found = btns.find(btn => {
                                            const text = btn.innerText ? btn.innerText.trim() : '';
                                            return text === 'Send';
                                        });
                                        if (found) return found;
                                        parent = parent.parentElement;
                                    }
                                    return null;
                                }"""
                                js_handle = await editor.evaluate_handle(js_code)
                                send_btn = js_handle.as_element()

                                if not send_btn:
                                    send_btn = await self.page.query_selector("button.msg-form__send-button, button:has-text('Send')")
                            except Exception as e:
                                print(f"      ├── ⚠️ [DEBUG] Error finding messaging send button: {e}")

                            if send_btn:
                                await send_btn.click()
                                await asyncio.sleep(random.uniform(3.0, 5.0))
                                
                                # Verification
                                print("      ├── 🔍 [LIVE] Verifying message was sent...")
                                try:
                                    safe_text = ai_reply[:30].strip().replace('"', '').replace("'", "")
                                    sent_msg = await self.page.query_selector(f"text=\"{safe_text}\"")
                                    if sent_msg:
                                        print(f"      │   ✅ [LIVE VERIFIED] Successfully verified message is in the DOM for {partner_name}!")
                                    else:
                                        print(f"      │   ⚠️ [WARNING] Send button clicked, but could not visually verify the message in the DOM.")
                                except Exception as ve:
                                    print(f"      │   ⚠️ [WARNING] Verification error: {ve}")

            except Exception as e:
                print(f"⚠️ Error processing conversation #{idx}: {e}")

        print(f"\n✅ Completed Inbox Audit: Processed top {len(processed_conversations)} messaging conversations.")
        return processed_conversations
