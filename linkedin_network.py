import asyncio
import random
import sys
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from engagement_tracker import already_engaged, mark_engaged, check_daily_limit, is_weekly_limit_reached

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInNetworkEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction

    async def process_connection_requests(self, max_requests: int = 3) -> List[Dict[str, Any]]:
        print(f"\n🤝 Navigating to LinkedIn MyNetwork (Target: {max_requests} micro-batch connection requests)...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/mynetwork/"):
            return []

        # Human scroll down to trigger lazy-loading of recommendation cards
        for _ in range(3):
            await PlaywrightResilience.human_scroll(self.page, random.randint(500, 800))
            await asyncio.sleep(random.uniform(1.2, 2.5))

        # Rate Limit Guard: Check daily limit (20/day) and weekly limit (80/week)
        if check_daily_limit("connection_request", 20):
            print("🛑 [Daily Rate Limit] Reached 20 connection requests today. Skipping network module.")
            return []

        if is_weekly_limit_reached("connection_request"):
            print("🛑 [Weekly Rate Limit] Reached 80 connection requests in last 7 days. Skipping network module.")
            return []

        if already_engaged("connection_request_weekly_limit", "system"):
            print("🛑 [Weekly Safety Hold] LinkedIn Weekly Limit was previously triggered. Holding network module.")
            return []

        card_selectors = [
            "div.discover-person-card",
            "li.discover-item",
            "div.member-card",
            "div.artdeco-card",
            "section.discover-cohort",
            "div[data-view-name*='pymk']",
            "div[data-view-name*='person']",
            "div.entity-result",
            "li.artdeco-list__item"
        ]

        cards = []
        for sel in card_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(cards):
                cards = found
                print(f"✅ [MyNetwork] Found {len(found)} cards via: {sel}")
                break

        # Fallback: Find cards by finding all visible Connect buttons and traversing to parent cards
        if not cards:
            connect_btns = await self.page.query_selector_all("button[aria-label*='Connect'], button[aria-label*='Invite'], button:has-text('Connect')")
            print(f"🔍 Found {len(connect_btns)} Connect buttons on MyNetwork viewport.")
            for btn in connect_btns:
                parent = btn
                for _ in range(4):
                    parent_handle = await parent.evaluate_handle("el => el.parentElement")
                    parent_el = parent_handle.as_element() if parent_handle else None
                    if parent_el:
                        parent = parent_el
                    else:
                        break
                if parent:
                    cards.append(parent)

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

                if PlaywrightResilience.is_company_name(name):
                    print(f"  [SKIP] '{name}' appears to be a company/brand. Skipping connection request.")
                    continue

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

                print(f"🤝 [Connection Request #{len(processed)+1}/{max_requests}] Target: {name} ({headline[:40]})...")

                # Human Behavior: Smooth mouse hover over prospect card & realistic reading pause
                box = await card.bounding_box()
                if box:
                    await PlaywrightResilience.smooth_mouse_move(self.page, 100, 100, int(box["x"] + box["width"]/2), int(box["y"] + box["height"]/2))
                    await asyncio.sleep(random.uniform(2.5, 5.0))

                if self.preproduction:
                    print(f"[{len(processed)+1:02d}] 🧪 [PREPROD] Would click Connect for {name}")
                    processed.append({"name": name, "headline": headline, "status": "simulated"})
                else:
                    await connect_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(1.2, 2.8))
                    await connect_btn.click(force=True)
                    await asyncio.sleep(random.uniform(2.0, 3.5))

                    # Safety Check 1: Detect LinkedIn Weekly Invitation Limit Modal Popup
                    body_text = (await self.page.inner_text("body")).lower()
                    if "reached your weekly invitation limit" in body_text or "weekly invitation limit" in body_text:
                        print("🛑 [CRITICAL SAFETY] LinkedIn Weekly Invitation Limit reached! Pausing network requests for 7 days.")
                        mark_engaged("connection_request_weekly_limit", "system")
                        # Close the modal dialog
                        dismiss_btn = await self.page.query_selector("button[aria-label*='Dismiss'], button[aria-label*='Got it'], button:has-text('Got it')")
                        if dismiss_btn:
                            await dismiss_btn.click()
                        break

                    # Safety Check 2: Handle "Send without a note" modal popup if presented
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

                # Human Inter-Request Pause: Wait 8 to 18 seconds between invites
                if len(processed) < max_requests:
                    inter_delay = random.uniform(8.0, 18.0)
                    print(f"  ☕ [Human Behavior] Pausing {inter_delay:.1f}s before next prospect...")
                    await asyncio.sleep(inter_delay)

            except Exception as e:
                print(f"⚠️ Connection card #{idx+1} error: {e}")
                continue

        print(f"✅ MyNetwork processing complete. Sent {len(processed)} connection requests.")
        return processed
