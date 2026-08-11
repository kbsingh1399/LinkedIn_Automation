"""
Live DOM Button Debugger
Opens the real Chrome profile and interactively probes every submit/reply/send
button on Feed, Notifications, and Inbox pages.

Run:  python debug_buttons_live.py
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from utils.stealth_chrome import launch_stealth_chrome

BUTTON_QUERIES = {
    "FEED_COMMENT_SUBMIT": [
        "button.comments-comment-box__submit-button",
        "button[aria-label*='Post comment' i]",
        "button.artdeco-button--primary[class*='submit']",
        "form.comments-comment-box__form button[type='submit']",
        "div.comments-comment-box button.artdeco-button--primary",
    ],
    "NOTIFICATION_REPLY_SUBMIT": [
        "button.comments-comment-box__submit-button",
        "button[aria-label*='Reply' i]",
        "button[aria-label*='Post' i]",
        "div.comments-comment-box__submit button",
        "form button.artdeco-button--primary",
    ],
    "INBOX_SEND_BUTTON": [
        "button.msg-form__send-button",
        "button[aria-label*='Send' i]",
        "button[type='submit'][class*='msg']",
        "footer button.artdeco-button--primary",
    ],
}

async def probe_buttons(page, label: str, selectors: list):
    print(f"\n{'='*60}")
    print(f"  BUTTON PROBE: {label}")
    print(f"{'='*60}")
    results = []
    for sel in selectors:
        try:
            els = await page.query_selector_all(sel)
            for i, el in enumerate(els):
                box = await el.bounding_box()
                visible = box is not None and box["width"] > 0 and box["height"] > 0
                text = (await el.inner_text()).strip()[:60] if visible else ""
                aria = await el.get_attribute("aria-label") or ""
                disabled = await el.get_attribute("disabled")
                tag = await el.evaluate("e => e.tagName")
                results.append({
                    "selector": sel,
                    "index": i,
                    "tag": tag,
                    "text": text,
                    "aria": aria,
                    "visible": visible,
                    "disabled": disabled is not None,
                    "box": box,
                })
                status = "VISIBLE" if visible else "HIDDEN"
                dis_mark = " [DISABLED]" if disabled is not None else ""
                print(f"  [{status}]{dis_mark} sel={sel!r}  text={text!r}  aria={aria!r}")
        except Exception as e:
            print(f"  [ERROR] sel={sel!r}: {e}")
    return results


async def open_comment_box_feed(page):
    """Click the Comment button on the first post to expose the editor."""
    print("\n  > Clicking Comment button on first feed post...")
    try:
        btn = await page.query_selector("button[aria-label='Comment']")
        if btn:
            await btn.click()
            await asyncio.sleep(1.5)
            print("  > Comment box opened. Probing submit button...")
        else:
            print("  > No Comment button found on feed.")
    except Exception as e:
        print(f"  > Error opening comment box: {e}")


async def open_notification_reply(page):
    """Click the first actionable notification card to expose reply box."""
    print("\n  > Clicking first notification card...")
    try:
        cards = await page.query_selector_all("article.nt-card, li.nt-card")
        for card in cards[:5]:
            try:
                await card.click()
                await asyncio.sleep(2.0)
                # Check if a reply box appeared
                reply_box = await page.query_selector(
                    "[contenteditable='true'], textarea, div.comments-comment-box"
                )
                if reply_box:
                    print("  > Reply box appeared after clicking notification card.")
                    break
            except Exception:
                continue
        else:
            print("  > No reply box found after clicking notifications.")
    except Exception as e:
        print(f"  > Error: {e}")


async def check_inbox_active_chat(page):
    """Click first conversation to open chat panel."""
    print("\n  > Opening first inbox conversation...")
    try:
        conv = await page.query_selector(
            "li.msg-conversations-container__convo-item, "
            "div.msg-conversations-container__convo-item"
        )
        if conv:
            await conv.click()
            await asyncio.sleep(2.0)
            print("  > Conversation opened.")
        else:
            print("  > No conversation items found.")
    except Exception as e:
        print(f"  > Error: {e}")


async def highlight_element(page, selector: str):
    """Flash-highlight a found element so it's visible in Chrome."""
    try:
        await page.evaluate(f"""
            (function() {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return;
                const orig = el.style.outline;
                el.style.outline = "4px solid red";
                el.style.backgroundColor = "rgba(255,0,0,0.15)";
                setTimeout(() => {{
                    el.style.outline = orig;
                    el.style.backgroundColor = "";
                }}, 3000);
            }})();
        """)
    except Exception:
        pass


async def main():
    async with async_playwright() as p:
        ctx, page = await launch_stealth_chrome(p, profile="linkedin")

        all_results = {}

        # ── GATE 2: Feed ────────────────────────────────────────────
        print("\n\n[FEED] Navigating to LinkedIn Feed...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await page.evaluate("window.scrollTo(0, 0)")
        await open_comment_box_feed(page)
        await page.screenshot(path="dbg_feed_comment_box.png")

        feed_results = await probe_buttons(page, "FEED_COMMENT_SUBMIT", BUTTON_QUERIES["FEED_COMMENT_SUBMIT"])
        all_results["feed"] = feed_results

        # Highlight best match
        for r in feed_results:
            if r["visible"] and not r["disabled"]:
                await highlight_element(page, r["selector"])
                print(f"\n  *** BEST FEED SUBMIT BUTTON: {r['selector']!r}  text={r['text']!r} ***")
                await asyncio.sleep(2)
                break

        await page.screenshot(path="dbg_feed_submit_highlighted.png")

        # ── GATE 3: Notifications ───────────────────────────────────
        print("\n\n[NOTIFICATIONS] Navigating to LinkedIn Notifications...")
        await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await page.evaluate("window.scrollTo(0, 0)")
        await open_notification_reply(page)
        await page.screenshot(path="dbg_notif_reply_box.png")

        notif_results = await probe_buttons(page, "NOTIFICATION_REPLY_SUBMIT", BUTTON_QUERIES["NOTIFICATION_REPLY_SUBMIT"])
        all_results["notifications"] = notif_results

        for r in notif_results:
            if r["visible"] and not r["disabled"]:
                await highlight_element(page, r["selector"])
                print(f"\n  *** BEST NOTIFICATION SUBMIT BUTTON: {r['selector']!r}  text={r['text']!r} ***")
                await asyncio.sleep(2)
                break

        await page.screenshot(path="dbg_notif_submit_highlighted.png")

        # ── GATE 4: Inbox ────────────────────────────────────────────
        print("\n\n[INBOX] Navigating to LinkedIn Messaging...")
        await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await check_inbox_active_chat(page)
        await page.screenshot(path="dbg_inbox_chat.png")

        inbox_results = await probe_buttons(page, "INBOX_SEND_BUTTON", BUTTON_QUERIES["INBOX_SEND_BUTTON"])
        all_results["inbox"] = inbox_results

        for r in inbox_results:
            if r["visible"] and not r["disabled"]:
                await highlight_element(page, r["selector"])
                print(f"\n  *** BEST INBOX SEND BUTTON: {r['selector']!r}  text={r['text']!r} ***")
                await asyncio.sleep(2)
                break

        await page.screenshot(path="dbg_inbox_send_highlighted.png")

        # ── SUMMARY ─────────────────────────────────────────────────
        print("\n\n" + "="*60)
        print("  BUTTON PROBE SUMMARY")
        print("="*60)
        for module, results in all_results.items():
            visible = [r for r in results if r.get("visible") and not r.get("disabled")]
            print(f"  {module.upper()}: {len(visible)} visible+enabled buttons found")
            for r in visible:
                print(f"    OK  {r['selector']!r}  text={r['text']!r}")

        print("\n  Screenshots saved: dbg_feed_*, dbg_notif_*, dbg_inbox_*")
        print("\n  Browser staying open for 30s for manual inspection...")
        await asyncio.sleep(30)
        await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())
