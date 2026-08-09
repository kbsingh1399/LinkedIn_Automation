import asyncio
import sys
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def main():
    print("=" * 75)
    print(" 🚀 INTERACTIVE LIVE DOM DEEP-DIVE (FEED, NOTIFICATIONS & GEMINI)")
    print("=" * 75)

    cdp_active = await check_cdp(9222)
    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connecting via CDP...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print("🚀 Launching visible Chrome...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        # Maximize window
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setWindowBounds", {"windowId": 1, "bounds": {"windowState": "maximized"}})
        except Exception:
            pass

        # ── 1. LINKEDIN FEED INTERACTIVE INSPECTION ──
        print("\n--- [1] LINKEDIN FEED DEEP DIVE ---")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=40000)
        await page.bring_to_front()
        await asyncio.sleep(3)

        cards = await page.query_selector_all("div[data-view-name='feed-full-update'], div.feed-shared-update-v2, article")
        print(f"Feed cards found: {len(cards)}")

        if cards:
            card = cards[0]
            await card.scroll_into_view_if_needed()
            await asyncio.sleep(1)

            # Inspect Author Name inside card
            author_els = await card.query_selector_all("span[class*='actor__title'], span.update-components-actor__name, div[class*='actor'] a span, span.feed-shared-actor__name, div[class*='actor__name']")
            print(f"Author name candidates inside card 0: {len(author_els)}")
            for idx, el in enumerate(author_els[:3]):
                print(f"  Author candidate #{idx}: text={(await el.inner_text()).strip()!r} tag={await el.evaluate('e => e.tagName')} class={(await el.get_attribute('class'))!r}")

            # Inspect Headline inside card
            headline_els = await card.query_selector_all("span[class*='actor__description'], div[class*='actor__headline'], span[class*='actor__sub-description']")
            print(f"Headline candidates inside card 0: {len(headline_els)}")
            for idx, el in enumerate(headline_els[:3]):
                print(f"  Headline candidate #{idx}: text={(await el.inner_text()).strip()!r}")

            # Inspect Post Commentary text inside card
            text_els = await card.query_selector_all("div.update-components-update-activity__commentary, div.feed-shared-update-v2__description-text, div.update-components-text, span.break-words")
            print(f"Post text content candidates inside card 0: {len(text_els)}")
            for idx, el in enumerate(text_els[:3]):
                txt = (await el.inner_text()).strip().replace("\n", " ")
                print(f"  Text candidate #{idx}: len={len(txt)} preview={txt[:70]!r}")

            # Inspect See More button inside card
            see_more = await card.query_selector("button[data-test-id='expandable-text-button'], button.feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('...more'), button:has-text('more')")
            if see_more:
                print(f"See More button found! text={(await see_more.inner_text()).strip()!r}")
            else:
                print("No see-more button in card 0 (or post is short)")

            # Click Comment button to open editor box
            comment_btn = await card.query_selector("button[aria-label*='Comment' i]")
            if comment_btn:
                print("Clicking Comment button on card 0...")
                await comment_btn.click()
                await asyncio.sleep(2)

                # Inspect editor
                editors = await card.query_selector_all("div[contenteditable='true'], div[role='textbox']")
                if not editors:
                    editors = await page.query_selector_all("div.comments-comment-box div[contenteditable='true'], div[contenteditable='true'][role='textbox']")
                print(f"Editors found after clicking Comment: {len(editors)}")
                for idx, ed in enumerate(editors):
                    role = await ed.get_attribute("role") or ""
                    aria = await ed.get_attribute("aria-label") or ""
                    cls = await ed.get_attribute("class") or ""
                    print(f"  Editor #{idx}: role={role!r} aria={aria!r} class={cls[:50]!r}")

                # Type sample into editor and check submit button
                if editors:
                    await editors[0].click()
                    await editors[0].fill("Test draft verification")
                    await asyncio.sleep(1)

                    submits = await card.query_selector_all("button.comments-comment-box__submit-button, button.artdeco-button--primary[type='submit'], button:has-text('Comment')")
                    if not submits:
                        submits = await page.query_selector_all("button.comments-comment-box__submit-button, button.artdeco-button--primary[type='submit'], div.comments-comment-box button:has-text('Comment')")
                    print(f"Submit buttons found while typing: {len(submits)}")
                    for idx, sb in enumerate(submits):
                        txt = (await sb.inner_text()).strip()
                        vis = await sb.is_visible()
                        dis = await sb.get_attribute("disabled")
                        print(f"  Submit btn #{idx}: text={txt!r} vis={vis} dis={dis}")

                    # Clear editor
                    await editors[0].fill("")
                    await asyncio.sleep(1)

        # ── 2. LINKEDIN NOTIFICATIONS INTERACTIVE INSPECTION ──
        print("\n--- [2] LINKEDIN NOTIFICATIONS DEEP DIVE ---")
        await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded", timeout=40000)
        await page.bring_to_front()
        await asyncio.sleep(3)

        notif_cards = await page.query_selector_all("article.nt-card, div[class*='nt-card__container'], div[class*='nt-card']")
        print(f"Notification cards found: {len(notif_cards)}")

        if notif_cards:
            # Find an actionable notification card
            actionable_idx = None
            for idx, n_card in enumerate(notif_cards[:10]):
                txt = (await n_card.inner_text()).lower()
                if any(kw in txt for kw in ["replied", "commented", "mentioned", "tagged", "response"]):
                    actionable_idx = idx
                    print(f"Actionable notification card found at index {idx}: {txt[:80].replace(chr(10), ' ')}...")
                    break

            if actionable_idx is not None:
                print(f"Clicking actionable notification card #{actionable_idx}...")
                await notif_cards[actionable_idx].click()
                await asyncio.sleep(3.5)
                await page.bring_to_front()

                print(f"Opened page URL: {page.url}")

                # Check for Reply buttons on opened thread
                reply_btns = await page.query_selector_all("button.comments-comment-item__reply-button, button[aria-label*='Reply' i], button:has-text('Reply')")
                print(f"Reply buttons on opened thread: {len(reply_btns)}")
                for idx, rb in enumerate(reply_btns[:3]):
                    aria = await rb.get_attribute("aria-label") or ""
                    txt = (await rb.inner_text()).strip()
                    print(f"  Reply btn #{idx}: text={txt!r} aria={aria!r}")

                # Click first reply button if available
                if reply_btns:
                    print("Clicking first Reply button...")
                    await reply_btns[0].click()
                    await asyncio.sleep(2)

                # Check for Editors
                editors = await page.query_selector_all("div[contenteditable='true'][role='textbox'], div[contenteditable='true']")
                print(f"Editors on opened notification thread: {len(editors)}")
                for idx, ed in enumerate(editors):
                    aria = await ed.get_attribute("aria-label") or ""
                    vis = await ed.is_visible()
                    print(f"  Editor #{idx}: vis={vis} aria={aria!r}")

                # Check for Submit buttons
                submits = await page.query_selector_all("button.comments-comment-box__submit-button, button:has-text('Reply'), button:has-text('Post'), button.artdeco-button--primary[type='submit']")
                print(f"Submit buttons on opened thread: {len(submits)}")
                for idx, sb in enumerate(submits[:4]):
                    txt = (await sb.inner_text()).strip()
                    vis = await sb.is_visible()
                    dis = await sb.get_attribute("disabled")
                    print(f"  Submit btn #{idx}: text={txt!r} vis={vis} dis={dis}")

        # ── 3. GEMINI WEB INTERACTIVE INSPECTION ──
        print("\n--- [3] GEMINI WEB DEEP DIVE ---")
        await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=40000)
        await page.bring_to_front()
        await asyncio.sleep(3)

        editor = await page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
        if editor:
            print("Found Gemini prompt editor!")
            await editor.click()
            await page.keyboard.insert_text("Hello Gemini, test DOM audit.")
            await asyncio.sleep(1.5)

            # Check send buttons now that text is typed!
            send_btns = await page.query_selector_all("button[aria-label*='Send' i], button[aria-label*='submit' i], button[aria-label*='Run' i], button.send-button, button:has-text('Send')")
            if not send_btns:
                # Find all buttons near the editor
                send_btns = await page.query_selector_all("div.input-area button, rich-textarea button, button.send-button")
            print(f"Gemini Send buttons after typing text: {len(send_btns)}")
            for idx, sb in enumerate(send_btns):
                aria = await sb.get_attribute("aria-label") or ""
                txt = (await sb.inner_text()).strip()
                cls = await sb.get_attribute("class") or ""
                vis = await sb.is_visible()
                dis = await sb.get_attribute("disabled")
                print(f"  Send btn #{idx}: text={txt!r} aria={aria!r} vis={vis} dis={dis} class={cls[:40]!r}")

            # Clear editor text without sending prompt
            await editor.fill("")

            # Click Upload button to inspect menu & file inputs
            upload_btn = await page.query_selector("button[aria-label*='Upload' i], button[aria-label*='Add' i], button[aria-label*='plus' i]")
            if upload_btn:
                print("Clicking Gemini Upload button ('Upload & tools')...")
                await upload_btn.click()
                await asyncio.sleep(1.5)

                menu_items = await page.query_selector_all("div[role='menu'] *, div[role='menuitem'], button:has-text('Upload'), span:has-text('Upload')")
                print(f"Upload menu items exposed: {len(menu_items)}")
                for idx, item in enumerate(menu_items[:5]):
                    txt = (await item.inner_text()).strip()
                    print(f"  Menu item #{idx}: text={txt!r}")

                file_inputs = await page.locator("input[type='file']").all()
                print(f"File inputs found after opening menu: {len(file_inputs)}")

        print("\n=" * 75)
        print("🎉 INTERACTIVE DEEP DIVE AUDIT COMPLETE!")
        print("=" * 75)

if __name__ == "__main__":
    asyncio.run(main())
