import asyncio
import time
import json
from playwright.async_api import async_playwright
from linkedin_publisher import LinkedInPublisher

async def debug_notifications():
    publisher = LinkedInPublisher(headless=False)
    
    async with async_playwright() as p:
        from utils.stealth_chrome import launch_stealth_chrome
        print("🌐 Launching Chrome in visible mode for DOM Analysis on Notifications...")
        context, page = await launch_stealth_chrome(
            p, profile="linkedin", user_data_dir=publisher.user_data_dir
        )
        await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        
        print(f"📌 Current URL: {page.url}")
        await page.screenshot(path="notif_debug_0_list.png")
        print("📸 Captured notif_debug_0_list.png")

        # Find notification cards
        card_selectors = [
            "article.nt-card",
            "div.nt-card-v2",
            "div[data-litms-control-urn*='notification']",
            "a.nt-card__left-rail",
            "div.notifications-item"
        ]

        cards = []
        chosen_selector = ""
        for sel in card_selectors:
            found = await page.query_selector_all(sel)
            if found:
                cards = found
                chosen_selector = sel
                break

        print(f"🔍 Found {len(cards)} cards using selector: '{chosen_selector}'")

        for idx in range(min(5, len(cards))):
            print(f"\n--- Analyzing Notification Card #{idx+1} ---")
            # Re-query cards to avoid stale handles
            cards = await page.query_selector_all(chosen_selector)
            if idx >= len(cards):
                break
            card = cards[idx]

            card_text = (await card.inner_text()).strip()
            preview = card_text[:120].replace("\n", " ")
            print(f"📝 Text preview: {preview}")

            # Extract links inside card
            links = await card.query_selector_all("a")
            link_urls = []
            for l in links:
                href = await l.get_attribute("href")
                if href:
                    link_urls.append(href)
            print(f"🔗 Links inside card ({len(link_urls)}): {link_urls[:3]}")

            # Click card
            print(f"👆 Clicking Card #{idx+1}...")
            await card.click()
            await asyncio.sleep(3.5)

            shot_name = f"notif_debug_{idx+1}_opened.png"
            await page.screenshot(path=shot_name)
            print(f"📸 Captured {shot_name} (Current URL: {page.url})")

            # DOM Analysis on opened target
            dom_info = await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll("div[contenteditable='true'], div[role='textbox'], textarea, input"));
                const buttons = Array.from(document.querySelectorAll("button, [role='button']"));
                
                return {
                    editors: inputs.map(el => ({
                        tag: el.tagName,
                        class: el.className,
                        role: el.getAttribute('role'),
                        contenteditable: el.getAttribute('contenteditable'),
                        placeholder: el.getAttribute('placeholder') || el.getAttribute('aria-label'),
                        visible: el.offsetWidth > 0 && el.offsetHeight > 0
                    })),
                    buttons: buttons.map(el => ({
                        tag: el.tagName,
                        class: el.className,
                        text: (el.innerText || '').trim(),
                        aria: el.getAttribute('aria-label'),
                        visible: el.offsetWidth > 0 && el.offsetHeight > 0
                    })).filter(b => b.visible && (b.text || b.aria))
                };
            }""")

            print(f"✏️ Text Editors Found ({len(dom_info['editors'])}): {json.dumps(dom_info['editors'], indent=2)}")
            print(f"🔘 Visible Action Buttons ({len(dom_info['buttons'])}):")
            for b in dom_info['buttons'][:10]:
                print(f"   - [{b['tag']}] text='{b['text']}' | aria='{b['aria']}' | class='{b['class'][:40]}'")

            # Navigate back to notifications if moved away
            if "notifications" not in page.url:
                await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")
                await asyncio.sleep(2.5)

        print("\n✅ DOM Analysis script completed. Chrome browser kept open.")

if __name__ == "__main__":
    asyncio.run(debug_notifications())
