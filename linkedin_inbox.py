import asyncio
import random
import sys
import time
import os
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from gemini_ai import GeminiAIClient
from engagement_tracker import already_engaged, mark_engaged

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
                const items = Array.from(document.querySelectorAll("ul.msg-s-message-list-content li, li.msg-s-message-list__event, li.msg-s-message-list__item, li.msg-s-message-list-item, div.msg-s-message-group, div.msg-s-event-listitem"));
                const result = [];
                let currentSender = "{partner_name}";
                items.forEach(item => {{
                    const nameEl = item.querySelector("span.msg-s-message-group__name, span.msg-s-message-group__profile-info, span.msg-s-message-group__meta, span.msg-s-message-list__meta");
                    if (nameEl && nameEl.innerText.trim()) {{
                        currentSender = nameEl.innerText.trim().split('\\n')[0];
                    }} else if (item.innerHTML.includes('msg-s-message-group__profile-info--me') || item.innerHTML.includes('msg-s-message-group--me') || item.classList.contains('msg-s-message-group--me')) {{
                        currentSender = "Me";
                    }}
                    
                    const textEls = Array.from(item.querySelectorAll("p.msg-s-event-listitem__body, div.msg-s-event-listitem__message-bubble, div.msg-s-message-group__message-bubble"));
                    let seenTexts = new Set();
                    textEls.forEach(el => {{
                        const txt = el.innerText.trim();
                        if (txt && !seenTexts.has(txt)) {{
                            seenTexts.add(txt);
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
        # Scroll to top then human-scroll to ensure conversation list is visible
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
        await PlaywrightResilience.human_scroll(self.page, random.randint(300, 500))
        # Wait for messaging list DOM to populate
        await asyncio.sleep(3.0)

        # Robust conversation list selectors + thread view fallback
        conv_selectors = [
            "div.msg-conversations-container__convo-item-link",
            "div.msg-conversation-listitem__link",
            "li.msg-conversation-card",
            "li.msg-conversation-listitem",
            "div.msg-conversation-card",
            "a.msg-conversation-listitem__link",
            "a[href*='/messaging/thread/']",
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
                    from engagement_tracker import check_daily_limit
                    if check_daily_limit("inbox_reply", 25):
                        print("🛑 [Rate Limit] Reached 25 inbox replies today. Skipping inbox module.")
                        break

                    card_text = (await card.inner_text()).lower()
                    if "sponsored" in card_text:
                        print(f"⏩ [Inbox #{idx}] Skipping Sponsored / Ad thread.")
                        continue

                    name_el = await card.query_selector("h3, span.msg-conversation-card__participant-names")
                    partner = (await name_el.inner_text()).strip() if name_el else f"Connection #{idx}"
                    partner = partner.splitlines()[0] if partner else f"Connection #{idx}"
                    
                    # Quick check: if the snippet says "You:", we sent the last message.
                    last_line = card_text.splitlines()[-1].strip() if card_text.splitlines() else ""
                    if "\\nyou:" in card_text or last_line.startswith("you:") or "you: " in last_line:
                        print(f"⏩ [Inbox #{idx}] Last message to {partner} was sent by us ('You:'). Skipping.")
                        continue
                        
                    await card.click()
                    await asyncio.sleep(random.uniform(1.8, 3.0))
                else:
                    partner = "Current Thread"

                # Check if message editor exists for this conversation (not locked/sponsored)
                editor = await self.page.query_selector(
                    "div.msg-form__contenteditable[contenteditable='true'], "
                    "div[role='textbox'][aria-label*='message']"
                )
                
                # Open Thread Verification Gate: Check for locked / out-of-network / disabled messaging banners
                locked_banner = await self.page.query_selector(
                    "div[class*='msg-thread--locked'], "
                    "p:has-text('You can no longer message this member'), "
                    "span:has-text('InMail'), "
                    "div:has-text('Messaging disabled')"
                )
                if (not editor or locked_banner) and card is not None:
                    await self.page.screenshot(path=f"debug_locked_thread_{idx}.png")
                    print(f"⏩ [Inbox #{idx}] Closed or locked DM thread with {partner}. Skipping (not marking as engaged).")                    
                    continue

                # Extract complete history
                history = await self.extract_full_chat_history(partner)
                
                history_lines = [line for line in history.split('\n') if line.strip()]
                my_names = ["me:", "karanbir", "karanbir singh:"]
                last_msg_lower = history_lines[-1].lower() if history_lines else ""
                if any(last_msg_lower.startswith(n) for n in my_names):
                    print(f"⏩ [Inbox #{idx}] Last message in thread with {partner} was sent by us. Waiting for their reply. Skipping.")
                    continue

                # Dedup check based on partner's latest message content so multi-turn replies work when they respond
                latest_partner_msg_key = f"{partner}:{history_lines[-1][:150]}" if history_lines else partner
                if already_engaged("inbox_reply", latest_partner_msg_key):
                    print(f"  [SKIP] Already replied to latest message from {partner} within 24h. Skipping.")
                    continue

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
                        "div[aria-label*='Write a message' i], "
                        "div[role='textbox'][aria-label*='message' i]"
                    )
                    if editor:
                        await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_reply)
                        await PlaywrightResilience.random_thinking_pause()
                        
                        # Step 7.3 Verification: Screenshot reply typed into inbox editor
                        await self.page.screenshot(path="step7_3_reply_typed.png")
                        await self.page.screenshot(path="debug_linkedin_inbox_typed.png")

                        send_btn = await self.page.query_selector(
                            "button.msg-form__send-button, "
                            "button[aria-label='Send'], "
                            "button[type='submit'][class*='msg-form']"
                        )
                        if send_btn:
                            is_vis = await send_btn.is_visible()
                            is_dis = await send_btn.get_attribute("disabled")
                            btn_text = (await send_btn.inner_text()).strip()[:20]
                            aria = await send_btn.get_attribute("aria-label") or ""
                            print(f"  [DOM] Send btn: text={btn_text!r} aria={aria!r} visible={is_vis} disabled={is_dis}")
                            if is_vis and is_dis is None:
                                try:
                                    await send_btn.click(force=True, timeout=4000)
                                except Exception:
                                    await send_btn.evaluate("b => b.click()")
                                await asyncio.sleep(random.uniform(3.5, 6.0))

                                # Step 7.3 Verification: Screenshot message sent in thread history
                                await self.page.screenshot(path="step7_3_reply_sent.png")
                                print(f"[{len(processed)+1:02d}] ✅ Reply sent to {partner}")
                                processed.append({"partner_name": partner, "reply": ai_reply})
                                mark_engaged("inbox_reply", latest_partner_msg_key)
                            else:
                                print(f"⚠️ Send btn not ready (visible={is_vis}, disabled={is_dis}) — skipping")

            except Exception as e:
                print(f"⚠️ Inbox #{idx} error: {e}")
                continue

        print(f"✅ Inbox processed: {len(processed)}")
        return processed
