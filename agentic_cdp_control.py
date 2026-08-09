import asyncio
import sys
import json
import random
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPORT_PATH = Path(r"C:\Users\SIGMA\.gemini\antigravity-ide\brain\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\cdp_live_dom_analysis.json")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

async def is_port_active(port: int = 9222) -> bool:
    import urllib.request
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def run_cdp_dom_analysis_and_interact():
    print("=" * 75)
    print(" 🔬 CDP AGENTIC CONTROL — LIVE DOM ANALYSIS & INTERACTION PREVIEW")
    print("=" * 75)

    active = await is_port_active(9222)

    async with async_playwright() as p:
        if active:
            print("🔗 Connecting via CDP to user's open debug Chrome at http://127.0.0.1:9222 ...")
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        # Multi-tab discovery across browser contexts
        all_pages = []
        for ctx in browser.contexts:
            for pg in ctx.pages:
                all_pages.append(pg)

        linkedin_pages = [pg for pg in all_pages if "linkedin.com" in pg.url]
        print(f"📌 Total Open Browser Tabs: {len(all_pages)}")
        print(f"📌 LinkedIn Specific Tabs : {len(linkedin_pages)}")

        target_pages = linkedin_pages if linkedin_pages else all_pages[:1]

        multi_tab_report = {
            "total_tabs": len(target_pages),
            "tabs": []
        }

        for idx, target_page in enumerate(target_pages, 1):
            print(f"\n───────────────────────────────────────────────────────────────────────────")
            print(f"📌 [Tab {idx}/{len(target_pages)}] URL: {target_page.url}")
            print(f"📄 Connected Tab Title: {await target_page.title()}")

            try:
                await target_page.bring_to_front()
            except Exception:
                pass

        analysis_report = {
            "url": target_page.url,
            "title": await target_page.title(),
            "dom_breakdown": {},
            "interactions_executed": []
        }

        # ── 1. DOM ANALYSIS & FINGERPRINTING ──────────────────────
        print("\n🔍 1. ANALYZING DOM STRUCTURE ON ACTIVE TAB...")
        
        selectors = {
            "Feed_Containers": "div.feed-shared-update-v2, div[data-id], article, div.occludable-update",
            "Like_Buttons": "button[aria-label*='Like'], button.react-button__trigger",
            "Comment_Buttons": "button[aria-label*='Comment']",
            "Repost_Buttons": "button[aria-label*='Repost']",
            "Send_Buttons": "button[aria-label*='Send']",
            "See_More_Buttons": "button:has-text('...more'), button.feed-shared-inline-show-more-text__see-more-less-toggle",
            "TipTap_Editors": "div.ql-editor, div[contenteditable='true'], div[role='textbox']",
            "Search_Bar": "input.search-global-typeahead__input, input[aria-label*='Search']",
            "Identity_Module": "div.feed-identity-module, div.identity-headline"
        }

        for category, sel in selectors.items():
            elements = await target_page.query_selector_all(sel)
            count = len(elements)
            sample_aria = await elements[0].get_attribute("aria-label") if count > 0 else ""
            sample_tag = await elements[0].evaluate("el => el.tagName") if count > 0 else ""
            print(f"   • {category:22s}: {count:2d} found (tag={sample_tag}, aria={sample_aria!r})")
            analysis_report["dom_breakdown"][category] = {
                "selector": sel,
                "count": count,
                "sample_tag": sample_tag,
                "sample_aria": sample_aria
            }

        # Save DOM Fingerprint Report immediately
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(analysis_report, f, indent=2)
        print(f"📁 DOM Fingerprint saved to: {REPORT_PATH}")

        # ── 2. LIVE INTERACTION PREVIEW (PREPRODUCTION) ───────────
        print("\n🕹️ 2. EXECUTING LIVE DOM INTERACTIONS (PREPRODUCTION MODE)...")

        # Step A: Viewport Scroll
        print("  [Step A] Scrolling viewport down feed...")
        await target_page.mouse.wheel(0, 400)
        await asyncio.sleep(0.8)
        analysis_report["interactions_executed"].append({"step": "scroll_viewport", "status": "SUCCESS"})

        # Step B: Open Comment Editor
        print("  [Step B] Locating and clicking Comment action button...")
        comment_btns = await target_page.query_selector_all("button[aria-label*='Comment']")
        if comment_btns:
            top_btn = comment_btns[0]
            await top_btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            await top_btn.click(force=True)
            await asyncio.sleep(1.0)
            print("  ✅ Clicked Comment button. Editor container opened.")
            analysis_report["interactions_executed"].append({"step": "click_comment_button", "status": "SUCCESS"})

            # Step C: Focus TipTap Editor & Type Preview Draft
            print("  [Step C] Focusing TipTap editor and typing live preview draft...")
            editor = await target_page.query_selector("div.ql-editor, div[contenteditable='true'], div[role='textbox']")
            if editor:
                await editor.click()
                await asyncio.sleep(0.2)
                preview_text = "Agentic DOM analysis & live interaction preview."
                await target_page.keyboard.type(preview_text, delay=15)

                await asyncio.sleep(1.0)
                print(f"  ✅ Typed: {preview_text!r}")
                
                # Clear text editor without executing submit
                print("  [Step D] Clearing editor draft without submitting (Preproduction Mode)...")
                await editor.fill("")
                await asyncio.sleep(0.5)
                print("  ✅ Editor cleared cleanly. Zero execution/submission performed.")
                analysis_report["interactions_executed"].append({"step": "type_and_clear_editor", "status": "SUCCESS"})
            else:
                print("  ⚠️ TipTap editor box not found after clicking comment button.")
        else:
            print("  ⚠️ No Comment buttons located on active tab.")

        # Update Final Report
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(analysis_report, f, indent=2)

        print("\n" + "=" * 75)
        print("🎉 CDP LIVE DOM ANALYSIS & INTERACTION PREVIEW COMPLETE!")
        print(f"📁 Analysis Report saved to: {REPORT_PATH}")
        print("=" * 75)

if __name__ == "__main__":
    asyncio.run(run_cdp_dom_analysis_and_interact())
