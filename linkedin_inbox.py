import asyncio
import random
import sys
import time
import os
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
            history_lines = await self.page.evaluate(f'''() => {{
                const items = Array.from(document.querySelectorAll("li.msg-s-message-list__item, div.msg-s-message-group"));
                const result = [];
                let currentSender = "{partner_name}";
                items.forEach(item => {{
                    const nameEl = item.querySelector("span.msg-s-message-group__name, span.msg-s-message-group__profile-info");
                    if (nameEl && nameEl.innerText.trim()) {{
                        currentSender = nameEl.innerText.trim();
                    }} else if (item.innerHTML.includes('msg-s-message-group__profile-info--me') || item.innerHTML.includes('msg-s-message-group--me') || item.classList.contains('msg-s-message-group--me')) {{
                        currentSender = "Me";
                    }}
                    
                    const textEls = Array.from(item.querySelectorAll("p.msg-s-event-listitem__body, div.msg-s-event-listitem__message-bubble"));
                    textEls.forEach(el => {{
                        const txt = el.innerText.trim();
                        if (txt) {{
                            result.push(`${{currentSender}}: ${{txt}}`);
                        }}
                    }});
                }});
                return result;
            }}''')
            
            if history_lines:
                return "\n".join(history_lines[-15:])
            return f"{partner_name}: Conversation started."
        except Exception as e:
            print(f"⚠️ Inbox extraction error: {e}")
            return f"{partner_name}: Conversation started."

    async def process_top_20_messages(self) -> List[Dict[str, Any]]:
        print(f"\n💬 Navigating to LinkedIn Messaging...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/messaging/"):
            return []
        # Scroll to top so the first conversation is visible
        await self.page.evaluate("window.scrollTo(0, 0)")
        # Wait for messaging list DOM to populate
        await asyncio.sleep(3.0)

        # Robust conversation list selectors + thread view fallback
        conv_selectors = [
            "li.msg-conversation-card",
            "li.msg-conversation-listitem",
            "div.msg-conversation-card",
            "a.msg-conversation-listitem__link",
            "a[href*='/messaging/thread/']",
            "div.msg-conversation-listitem__link",
            "div.msg-selectable-entity"
        ]
        
        conv_cards = []
        best_sel = None
        for sel in conv_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(conv_cards):
                conv_cards = found
                best_sel = sel

        # Fallback: Detect if already inside an active thread
        if not conv_cards:
            thread_editor = await self.page.query_selector(
                "div.msg-form__contenteditable[contenteditable='true'], "
                "div[role='textbox'][aria-label*='message']"
            )
            if thread_editor:
                print("ℹ️ Already inside an active message thread. Replying to current conversation...")
                conv_cards = [None]  # Placeholder to trigger reply flow

        print(f"🔍 Found {len(conv_cards)} conversations in inbox list.")

        # Step 7.1 Verification: Screenshot of messaging conversations list
        await self.page.screenshot(path="step7_1_conversations_list.png")

        processed = []

        for idx, card in enumerate(conv_cards[:20], 1):

            try:
                # Guard against page context closing
                try:
                    _ = self.page.url
                except Exception:
                    print(f"⚠️ Inbox: page context closed unexpectedly. Stopping inbox loop.")
                    break

                if card is not None:
                    card_text = (await card.inner_text()).lower()
                    if "sponsored" in card_text:
                        print(f"⏩ [Inbox #{idx}] Skipping Sponsored / Ad thread.")
                        continue

                    name_el = await card.query_selector("h3, span.msg-conversation-card__participant-names")
                    partner = (await name_el.inner_text()).strip() if name_el else f"Connection #{idx}"
                    partner = partner.splitlines()[0] if partner else f"Connection #{idx}"
                    
                    await card.click()
                    await asyncio.sleep(random.uniform(1.8, 3.0))
                else:
                    partner = "Current Thread"

                # Check if message editor exists for this conversation (not locked/sponsored)
                editor = await self.page.query_selector(
                    "div.msg-form__contenteditable[contenteditable='true'], "
                    "div[role='textbox'][aria-label*='message']"
                )
                if not editor and card is not None:
                    print(f"⏩ [Inbox #{idx}] No active message editor for {partner}. Skipping.")
                    continue

                # Extract complete history
                history = await self.extract_full_chat_history(partner)
                
                # Step 7.2 Verification: Take screenshot of active chat extracted
                screenshot_path = f"temp_inbox_{idx}_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                await self.page.screenshot(path="step7_2_chat_extracted.png")
                await self.page.screenshot(path="debug_linkedin_inbox_extracted.png")
                print(f"📸 [Step 7.2] Extracted chat history for {partner}:\n{history[:150]}...")
                
                # Call Gemini with the screenshot & history for verification
                ai_reply = await self.ai.generate_inbox_reply(
                    history,
                    partner,
                    page=self.page,
                    image_path=screenshot_path
                )

                if self.preproduction:
                    print(f"[{len(processed)+1:02d}] 🧪 [PREPROD] Reply to {partner}: {ai_reply[:50] if ai_reply else 'NO REPLY'}...")
                    if ai_reply:
                        processed.append({"partner_name": partner, "reply": ai_reply, "screenshot": screenshot_path})
                else:
                    await self.page.bring_to_front()
                    await asyncio.sleep(0.5)

                    editor = await self.page.query_selector(
                        "div.msg-form__contenteditable[contenteditable='true'], "
                        "div[role='textbox'][aria-label*='message']"
                    )
                    if editor:
                        await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                        await PlaywrightResilience.random_thinking_pause()
                        
                        # Step 7.3 Verification: Screenshot reply typed into inbox editor
                        await self.page.screenshot(path="step7_3_reply_typed.png")
                        await self.page.screenshot(path="debug_linkedin_inbox_typed.png")

                        send_btn = await self.page.query_selector(
                            "button[aria-label='Send'], "
                            "button.msg-form__send-button"
                        )
                        if send_btn:
                            await send_btn.click()
                            await asyncio.sleep(random.uniform(3.5, 6.0))

                            # Step 7.3 Verification: Screenshot message sent in thread history
                            await self.page.screenshot(path="step7_3_reply_sent.png")
                            print(f"[{len(processed)+1:02d}] ✅ Reply sent to {partner}")
                            processed.append({"partner_name": partner, "reply": ai_reply})

            except Exception as e:
                print(f"⚠️ Inbox #{idx} error: {e}")
                continue

        print(f"✅ Inbox processed: {len(processed)}")
        return processed
