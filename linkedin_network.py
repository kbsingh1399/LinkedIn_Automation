import asyncio
import random
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from engagement_tracker import already_engaged, mark_engaged, check_daily_limit

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInNetworkEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction

    async def process_connection_requests(self, max_requests: int = 15) -> List[Dict[str, Any]]:
        print(f"\n🤝 Navigating to LinkedIn MyNetwork (Target: {max_requests} connection requests)...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/mynetwork/"):
            return []

        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1.0)
        await PlaywrightResilience.human_scroll(self.page, random.randint(400, 700))
        await asyncio.sleep(2.0)

        # Rate Limit Guard: Cap at 20 connection requests per day for safety
        if check_daily_limit("connection_request", 20):
            print("🛑 [Rate Limit] Reached 20 connection requests today. Skipping network module.")
            return []

        card_selectors = [
            "div.discover-person-card",
            "li.discover-item",
            "div.member-card",
            "section.discover-cohort",
            "div[data-view-name*='pymk']"
        ]

        cards = []
        for sel in card_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(cards):
                cards = found
                break

        if not cards:
            cards = await self.page.query_selector_all("button[aria-label*='Connect']")

        print(f"🔍 Found {len(cards)} recommendation cards on MyNetwork page.")
        processed = []

        target_keywords = ["engineer", "developer", "ai", "data", "python", "product", "manager", "lead", "founder", "supply chain", "pmp"]

        for idx, card in enumerate(cards):
            if len(processed) >= max_requests or check_daily_limit("connection_request", 20):
                break
            try:
                # Scroll card into view
                try:
                    await card.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass

                # Extract Name and Headline
                name_el = await card.query_selector("span.discover-person-card__name, div.artdeco-entity-lockup__title, span[class*='name']")
                name = (await name_el.inner_text()).strip() if name_el else f"Connection #{idx+1}"
                name = name.splitlines()[0] if name else f"Connection #{idx+1}"

                headline_el = await card.query_selector("span.discover-person-card__occupation, div.artdeco-entity-lockup__subtitle, span[class*='occupation']")
                headline = (await headline_el.inner_text()).strip() if headline_el else ""

                headline_lower = headline.lower()
                matches_keyword = any(kw in headline_lower for kw in target_keywords) if headline else True

                if not matches_keyword:
                    print(f"  [SKIP] {name} ({headline[:40]}) does not match target industry keywords.")
                    continue

                if already_engaged("connection_request", name):
                    print(f"  [SKIP] Already sent connection request to {name} within cooldown. Skipping.")
                    continue

                # Find Connect Button
                connect_btn = await card.query_selector("button[aria-label*='Connect'], button[aria-label*='Invite'], button:has-text('Connect')")
                if not connect_btn:
                    print(f"  [SKIP] No Connect button found for {name}.")
                    continue

                print(f"🤝 [Connection Request #{len(processed)+1}] Sending invite to {name} ({headline[:40]})...")

                if self.preproduction:
                    print(f"[{len(processed)+1:02d}] 🧪 [PREPROD] Would click Connect for {name}")
                    processed.append({"name": name, "headline": headline, "status": "simulated"})
                else:
                    await connect_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    await connect_btn.click(force=True)
                    await asyncio.sleep(random.uniform(2.0, 3.5))

                    # Check for "Send without a note" modal popup if presented
                    send_without_note_btn = await self.page.query_selector(
                        "button[aria-label*='Send without a note'], "
                        "button:has-text('Send without a note'), "
                        "button.artdeco-button--primary:has-text('Send')"
                    )
                    if send_without_note_btn and await send_without_note_btn.is_visible():
                        await send_without_note_btn.click(force=True)
                        await asyncio.sleep(random.uniform(1.5, 3.0))

                    mark_engaged("connection_request", name)
                    print(f"[{len(processed)+1:02d}] ✅ Connection request sent to {name}")
                    processed.append({"name": name, "headline": headline, "status": "sent"})

            except Exception as e:
                print(f"⚠️ Connection card #{idx+1} error: {e}")
                continue

        print(f"✅ MyNetwork processing complete. Sent {len(processed)} connection requests.")
        return processed
