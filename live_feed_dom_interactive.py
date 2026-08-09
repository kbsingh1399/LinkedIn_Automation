import asyncio
import sys
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUTPUT_JSON = Path(r"C:\Users\SIGMA\.gemini\antigravity\brain\de41d7d2-9a12-4600-baa6-af721315cfc1\feed_dom_interactive_report.json")
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
SCREENSHOT_PATH = OUTPUT_JSON.parent / "agentic_feed_dom_analysis.png"

async def is_cdp_active(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def run_feed_dom_interactive():
    print("=" * 70)
    print("  🔬 LINKEDIN FEED LIVE DOM ANALYSIS & INTERACTION SUITE")
    print("=" * 70)

    cdp_active = await is_cdp_active(9222)
    
    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connecting directly via CDP to open Chrome at http://localhost:9222 ...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print("🚀 Launching persistent visible Chrome instance...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        await page.bring_to_front()

        print("\n🌐 Navigating to https://www.linkedin.com/feed/ ...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        print(f"📌 Current URL: {page.url}")
        print(f"📄 Page Title: {await page.title()}")

        report = {
            "page_url": page.url,
            "page_title": await page.title(),
            "dom_structures": {},
            "interactions": []
        }

        # ── 1. DOM ANALYSIS & FINGERPRINTING ──────────────────────
        print("\n📊 1. FINGERPRINTING LINKEDIN FEED DOM STRUCTURE...")
        
        selectors_to_check = {
            "feed_container": "[role='feed'], div.scaffold-finite-scroll",
            "post_articles": "div[data-id], div.feed-shared-update-v2, div[role='article'], div[data-view-name='feed-full-update']",
            "author_names": "span.update-components-actor__name, span.feed-shared-actor__name, div[class*='actor__title'], a[class*='actor']",
            "author_headlines": "span.update-components-actor__description, div.update-components-actor__headline, span.feed-shared-actor__description",
            "like_buttons": "button[aria-label*='Like'], button.react-button__trigger",
            "comment_buttons": "button[aria-label*='Comment']",
            "repost_buttons": "button[aria-label*='Repost']",
            "send_buttons": "button[aria-label*='Send']",
            "see_more_buttons": "button.feed-shared-inline-show-more-text__see-more-less-toggle, button[data-test-id='expandable-text-button'], button:has-text('...more')",
            "comment_editors": "div.ql-editor, div[contenteditable='true'], div[role='textbox']",
            "profile_card": "div.identity-headline, div.feed-identity-module",
            "sort_dropdown": "button[aria-label*='Sort by']",
            "search_input": "input[aria-label*='Search']"
        }

        for key, sel in selectors_to_check.items():
            els = await page.query_selector_all(sel)
            count = len(els)
            aria_sample = await els[0].get_attribute("aria-label") if count > 0 else None
            tag_sample = await els[0].evaluate("el => el.tagName") if count > 0 else None
            print(f"   • {key:20s}: {count:2d} found (tag={tag_sample}, aria={aria_sample!r})")
            report["dom_structures"][key] = {
                "selector": sel,
                "count": count,
                "sample_tag": tag_sample,
                "sample_aria": aria_sample
            }

        # ── 2. LIVE DOM INTERACTIONS ──────────────────────────────
        print("\n🕹️ 2. EXECUTING LIVE DOM INTERACTIONS...")

        # Interaction A: Scroll Feed to Trigger Lazy Loading
        print("\n  [Interaction A] Smooth scrolling down feed...")
        await page.mouse.wheel(0, 800)
        await asyncio.sleep(2)
        await page.mouse.wheel(0, 800)
        await asyncio.sleep(2)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        report["interactions"].append({"action": "smooth_scroll", "status": "PASSED"})
        print("  ✅ Feed scroll completed.")

        # Interaction B: Click ...more expansion button on post
        print("\n  [Interaction B] Expanding post content via '...more' button...")
        see_more_btns = await page.query_selector_all("button.feed-shared-inline-show-more-text__see-more-less-toggle, button[data-test-id='expandable-text-button'], button:has-text('...more')")
        if see_more_btns:
            await see_more_btns[0].click()
            await asyncio.sleep(1.5)
            print("  ✅ Clicked '...more' expansion button.")
            report["interactions"].append({"action": "expand_post_more", "status": "PASSED"})
        else:
            print("  ℹ️ No '...more' button visible on top post.")
            report["interactions"].append({"action": "expand_post_more", "status": "SKIPPED_NOT_FOUND"})

        # Interaction C: Hover over Reaction/Like button to reveal Reaction Picker
        print("\n  [Interaction C] Hovering over Like button to inspect reaction picker...")
        like_btn = await page.query_selector("button[aria-label*='Like'], button.react-button__trigger")
        if like_btn:
            await like_btn.hover()
            await asyncio.sleep(2)
            reactions = await page.query_selector_all("button[aria-label*='Like'], button[aria-label*='Celebrate'], button[aria-label*='Support'], button[aria-label*='Love'], button[aria-label*='Insightful'], button[aria-label*='Funny']")
            reaction_names = [await r.get_attribute("aria-label") for r in reactions if await r.get_attribute("aria-label")]
            print(f"  ✅ Reactions menu revealed! Found {len(reactions)} reaction options: {reaction_names[:6]}")
            report["interactions"].append({"action": "hover_like_reactions", "status": "PASSED", "reactions_found": reaction_names[:6]})
        else:
            print("  ⚠️ Like button not found.")
            report["interactions"].append({"action": "hover_like_reactions", "status": "FAILED"})

        # Interaction D: Open Comment Section & Focus TipTap Rich Text Editor
        print("\n  [Interaction D] Opening Comment box & focusing TipTap editor...")
        comment_btn = await page.query_selector("button[aria-label*='Comment']")
        if comment_btn:
            await comment_btn.click()
            await asyncio.sleep(2)
            editor = await page.query_selector("div.ql-editor, div[contenteditable='true']")
            if editor:
                await editor.click()
                await asyncio.sleep(1)
                print("  ✅ Comment TipTap editor focused! Typing diagnostic comment draft...")
                await editor.fill("Live DOM analysis verification in progress...")
                await asyncio.sleep(2)
                # Clear text box without submitting
                await editor.fill("")
                await asyncio.sleep(1)
                print("  ✅ Comment box cleared cleanly (PREPRODUCTION mode).")
                report["interactions"].append({"action": "open_and_type_comment_editor", "status": "PASSED"})
            else:
                print("  ⚠️ TipTap editor element not found after clicking comment button.")
                report["interactions"].append({"action": "open_and_type_comment_editor", "status": "FAILED_EDITOR_MISSING"})
        else:
            print("  ⚠️ Comment button not found.")
            report["interactions"].append({"action": "open_and_type_comment_editor", "status": "FAILED_BUTTON_MISSING"})

        # Capture live DOM state screenshot
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=False)
        print(f"📸 Screenshot captured to {SCREENSHOT_PATH}")
        report["screenshot_path"] = str(SCREENSHOT_PATH)

        # Save Report
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("\n" + "=" * 70)
        print(f"🎉 FEED DOM ANALYSIS & INTERACTION COMPLETE!")
        print(f"📁 Report saved to: {OUTPUT_JSON}")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_feed_dom_interactive())
