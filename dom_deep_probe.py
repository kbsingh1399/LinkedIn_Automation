"""
Deep DOM fingerprinter for LinkedIn - finds what actually exists on each page
after LinkedIn's CSS class obfuscation.
"""
import asyncio
import sys
from playwright.async_api import async_playwright

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


async def dump_page(page, url: str, label: str):
    print(f"\n{'='*60}")
    print(f" PROBING: {label}")
    print(f"{'='*60}")

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    await page.mouse.wheel(0, 1200)
    await asyncio.sleep(3)

    # --- Stable attribute probes (aria, role, data-*) ---
    probes = [
        # Feed post containers
        "[aria-label*='feed']",
        "[aria-label*='post']",
        "[role='article']",
        "[role='listitem']",
        "[role='feed']",
        # Author / actor area
        "a[aria-label*='profile']",
        # Engagement buttons
        "button[aria-label*='Like']",
        "button[aria-label*='Comment']",
        "button[aria-label*='Repost']",
        "button[aria-label*='Send']",
        # Notification items
        "[aria-label*='notification']",
        "li[class*='notification']",
        # Messaging
        "li[class*='conversation']",
        "[aria-label*='conversation']",
        "[aria-label*='message']",
        # Generic post text
        "[class*='comment-box']",
        "[class*='editor']",
        "div[contenteditable='true']",
        "div[role='textbox']",
    ]

    print("\n[Aria / Role / Data-* probes]")
    for sel in probes:
        try:
            found = await page.query_selector_all(sel)
            if found:
                sample = found[0]
                tag = await sample.evaluate("el => el.tagName")
                cls = (await sample.get_attribute("class") or "")[:60]
                aria = await sample.get_attribute("aria-label") or ""
                print(f"  FOUND {len(found):2d}x  {sel!r}")
                print(f"         tag={tag}  aria-label={aria!r}  class={cls!r}")
        except Exception:
            pass

    # Look for all buttons and dump unique aria-labels
    print("\n[All buttons with aria-labels]")
    btns = await page.query_selector_all("button[aria-label]")
    seen = set()
    for btn in btns:
        lbl = await btn.get_attribute("aria-label") or ""
        if lbl and lbl not in seen:
            seen.add(lbl)
            print(f"  BUTTON: {lbl!r}")

    # Look for any divs with post/article content
    print("\n[Text content in main area - first 3 text blocks > 40 chars]")
    spans = await page.query_selector_all("main span, main p, main div")
    found_texts = 0
    for sp in spans:
        if found_texts >= 3:
            break
        try:
            txt = (await sp.inner_text()).strip()
            if 40 < len(txt) < 300 and "\n" not in txt[:40]:
                cls = (await sp.get_attribute("class") or "")[:60]
                tag = await sp.evaluate("el => el.tagName")
                print(f"  [{tag}] class={cls!r}")
                print(f"   text={txt[:100]!r}")
                found_texts += 1
        except Exception:
            pass


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=r"C:\Users\SIGMA\Documents\LinkedIn_Automation\user_data",
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await dump_page(page, "https://www.linkedin.com/feed/", "FEED")
        await dump_page(page, "https://www.linkedin.com/notifications/", "NOTIFICATIONS")
        await dump_page(page, "https://www.linkedin.com/messaging/", "MESSAGING / INBOX")

        await context.close()

asyncio.run(main())
