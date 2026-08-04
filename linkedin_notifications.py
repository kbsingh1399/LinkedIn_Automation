import asyncio
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from gemini_ai import GeminiAIClient

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInNotificationsEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def process_top_20_notifications(self) -> List[Dict[str, Any]]:
        print(f"\n🔔 Navigating to LinkedIn Notifications (Scanning Top 20, Preproduction Mode: {self.preproduction})...")
        try:
            await self.page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ Notifications load notice: {e}")

        # Query notification item cards
        notif_selectors = [
            "article.nt-card",
            "div.notification-item",
            "li.nt-card-list__item",
            "div[data-urn*='notification']",
            "a.nt-card__headline-link"
        ]

        cards = []
        for sel in notif_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(cards):
                cards = found

        print(f"🔍 Found {len(cards)} notification items. Auditing top 20...")

        top_cards = cards[:20]
        actionable_notifications = []

        for idx, card in enumerate(top_cards, start=1):
            try:
                card_text = (await card.inner_text()).strip()

                is_unread = await card.query_selector("div.nt-card--unread, span.nt-card__unread-indicator, div[aria-label*='unread']") is not None
                is_reply_or_mention = any(keyword in card_text.lower() for keyword in ["replied", "mentioned", "commented", "reacted"])

                status_label = "[UNREAD/ACTIONABLE]" if (is_unread or is_reply_or_mention) else "[READ/INFO]"
                print(f"  [{idx:02d}] {status_label} {card_text[:90]}...")

                if is_unread or is_reply_or_mention:
                    ai_reply = self.ai.generate_notification_reply(notification_text=card_text[:200])

                    item = {
                        "index": idx,
                        "unread": is_unread,
                        "summary": card_text[:150],
                        "ai_reply": ai_reply,
                        "preproduction": self.preproduction
                    }
                    actionable_notifications.append(item)

                    if self.preproduction:
                        print(f"      🧪 [PREPRODUCTION] Selected for reply. Staged Gemini Reply: \"{ai_reply}\"")
                    else:
                        print(f"      🚀 [LIVE] Opening notification thread...")
                        link = await card.query_selector("a.nt-card__headline-link, a")
                        if link:
                            await link.click()
                            await asyncio.sleep(4)

                            reply_box = await self.page.query_selector("div.comments-comment-box div[contenteditable='true']")
                            if reply_box:
                                await reply_box.focus()
                                await reply_box.fill(ai_reply)
                                await asyncio.sleep(2)
                                submit_btn = await self.page.query_selector("button.comments-comment-box__submit-button")
                                if submit_btn:
                                    await submit_btn.click()
                                    print("      🎉 [LIVE] Notification reply submitted successfully!")
                                    await asyncio.sleep(3)

                            await self.page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")
                            await asyncio.sleep(2)

            except Exception as e:
                print(f"⚠️ Error parsing notification #{idx}: {e}")

        print(f"\n✅ Completed Notification Audit: Processed {len(actionable_notifications)} actionable items out of top 20.")
        return actionable_notifications
