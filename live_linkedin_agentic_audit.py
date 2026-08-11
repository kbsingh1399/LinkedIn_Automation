import asyncio
import sys
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from utils.stealth_chrome import launch_stealth_chrome, apply_stealth_window

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

OUTPUT_FILE = Path(r"C:\Users\SIGMA\.gemini\antigravity-ide\brain\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\linkedin_feed_agentic_dom_audit.json")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def run_agentic_feed_audit():
    print("=" * 75)
    print(" 🤖 LINKEDIN FEED AGENTIC CONTROL & COMPREHENSIVE DOM ELEMENT AUDIT")
    print("=" * 75)

    cdp_active = await check_cdp(9222)

    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connected via CDP to active Chrome instance on http://localhost:9222")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            await apply_stealth_window(context, page)
        else:
            print("🚀 Launching visible persistent Chrome session...")
            context, page = await launch_stealth_chrome(p, profile="linkedin")

        print("\n🌐 Bringing https://www.linkedin.com/feed/ to front...")
        if "linkedin.com/feed" not in page.url:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        
        await asyncio.sleep(2)
        print(f"📌 Active Page URL: {page.url}")
        print(f"📄 Active Page Title: {await page.title()}")

        audit_results = {
            "page_url": page.url,
            "page_title": await page.title(),
            "element_categories": {},
            "live_actions_performed": []
        }

        # ── 1. COMPREHENSIVE ELEMENT AUDIT ────────────────────────
        print("\n🔍 Analyzing DOM categories on LinkedIn Feed...")
        
        element_queries = {
            "1_Header_Search_Input": "input.search-global-typeahead__input, input[aria-label*='Search']",
            "2_Global_Nav_Items": "li.global-nav__primary-item, nav.global-nav a",
            "3_Identity_Module": "div.feed-identity-module, div.identity-headline",
            "4_Start_Post_Trigger": "button.share-box-feed-entry__trigger, button:has-text('Start a post')",
            "5_Feed_Sort_Dropdown": "button[aria-label*='Sort by'], div.display-flex button:has-text('Sort by')",
            "6_Feed_Update_Cards": "div.feed-shared-update-v2, div[data-id], article",
            "7_Post_Author_Headlines": "span.update-components-actor__title, div.update-components-actor",
            "8_Post_Text_Content": "div.feed-shared-update-v2__description, span.break-words",
            "9_Like_Action_Buttons": "button[aria-label*='Like'], button.react-button__trigger",
            "10_Comment_Action_Buttons": "button[aria-label*='Comment']",
            "11_Repost_Action_Buttons": "button[aria-label*='Repost']",
            "12_Send_Action_Buttons": "button[aria-label*='Send']",
            "13_Expand_More_Buttons": "button.feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('...more')",
            "14_Rich_Text_Editors": "div.ql-editor, div[contenteditable='true'], div[role='textbox']",
            "15_Right_Sidebar_News": "div.feed-follows-module, div.news-module"
        }

        for cat_name, selector in element_queries.items():
            elements = await page.query_selector_all(selector)
            count = len(elements)
            sample_details = []
            
            for idx, el in enumerate(elements[:3]):
                try:
                    aria = await el.get_attribute("aria-label") or ""
                    tag = await el.evaluate("el => el.tagName")
                    text_content = (await el.inner_text()).strip().replace("\n", " ")[:80]
                    sample_details.append({"index": idx, "tag": tag, "aria": aria, "text": text_content})
                except Exception:
                    pass

            print(f"   • {cat_name:25s} | Count: {count:2d} | Samples: {len(sample_details)}")
            audit_results["element_categories"][cat_name] = {
                "selector": selector,
                "count": count,
                "samples": sample_details
            }

        # ── 2. AGENTIC LIVE CONTROL & ELEMENT INTERACTIONS ─────────
        print("\n⚡ Executing Agentic Live Element Interactions...")

        # Action 1: Focus Global Search Input
        print("  [Action 1] Focusing global search bar...")
        search_input = await page.query_selector("input.search-global-typeahead__input, input[aria-label*='Search']")
        if search_input:
            await search_input.click()
            await asyncio.sleep(1)
            await search_input.fill("Supply Chain Automation")
            await asyncio.sleep(1.5)
            # Clear search without navigating away from feed
            await search_input.fill("")
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
            print("  ✅ Search bar focused, test phrase typed, and cleared cleanly.")
            audit_results["live_actions_performed"].append({"action": "search_bar_interaction", "status": "SUCCESS"})

        # Action 2: Trigger Comment Box on top post card
        print("  [Action 2] Interacting with post comment action button...")
        comment_btn = await page.query_selector("button[aria-label*='Comment']")
        if comment_btn:
            await comment_btn.click()
            await asyncio.sleep(2)
            editor = await page.query_selector("div[contenteditable='true'], div[role='textbox']")
            if editor:
                await editor.click()
                await editor.fill("Agentic DOM verification: testing interaction workflow.")
                await asyncio.sleep(2)
                await editor.fill("")
                print("  ✅ Comment box toggled, editor focused, draft typed and cleared.")
                audit_results["live_actions_performed"].append({"action": "comment_box_interaction", "status": "SUCCESS"})

        # Action 3: Expand Post Text via ...more toggle
        print("  [Action 3] Expanding truncated post text via '...more'...")
        see_more = await page.query_selector("button.feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('...more')")
        if see_more:
            await see_more.click()
            await asyncio.sleep(1.5)
            print("  ✅ Expanded post body text.")
            audit_results["live_actions_performed"].append({"action": "expand_post_text", "status": "SUCCESS"})
        else:
            print("  ℹ️ All visible post bodies are fully expanded.")
            audit_results["live_actions_performed"].append({"action": "expand_post_text", "status": "NO_TRUNCATED_TEXT"})

        # Action 4: Smooth Viewport Scroll
        print("  [Action 4] Performing smooth agentic scroll down feed...")
        await page.mouse.wheel(0, 700)
        await asyncio.sleep(1.5)
        await page.mouse.wheel(0, 700)
        await asyncio.sleep(1.5)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        print("  ✅ Scroll interaction complete.")
        audit_results["live_actions_performed"].append({"action": "viewport_scroll", "status": "SUCCESS"})

        # Save Report
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=2)

        print("\n" + "=" * 75)
        print("🎉 AGENTIC CONTROL & DOM ELEMENT AUDIT COMPLETE!")
        print(f"📁 Detailed Audit Report: {OUTPUT_FILE}")
        print("=" * 75)

if __name__ == "__main__":
    asyncio.run(run_agentic_feed_audit())
