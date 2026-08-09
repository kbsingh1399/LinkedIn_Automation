import asyncio
import json
import sys
import os
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

ARTIFACT_DIR = Path(r"C:\Users\SIGMA\.gemini\antigravity\brain\fd360cef-096e-4bd0-8b59-dddf069fe9af")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = ARTIFACT_DIR / "feed_dom_analysis_report.json"
SCREENSHOT_PATH = ARTIFACT_DIR / "feed_dom_interactive_analysis.png"

async def is_cdp_active(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def analyze_linkedin_feed():
    print("=" * 75)
    print(" 🚀 LINKEDIN FEED DOM INTERACTIVE ANALYSIS & EXAMINATION SUITE")
    print("=" * 75)

    cdp_active = await is_cdp_active(9222)
    
    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connected to existing browser session via CDP on http://localhost:9222...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print(f"🚀 Launching Chrome with persistent profile: {settings.linkedin_user_data_dir}")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--test-type",
                    "--remote-debugging-port=9222"
                ]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        # Bring tab to front
        await page.bring_to_front()

        print("\n🌐 Navigating to LinkedIn Feed: https://www.linkedin.com/feed/ ...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        current_url = page.url
        page_title = await page.title()
        print(f"📌 Current URL: {current_url}")
        print(f"📄 Page Title: {page_title}")

        report = {
            "page_url": current_url,
            "page_title": page_title,
            "dom_structure_fingerprints": {},
            "active_feed_posts": [],
            "interactions": []
        }

        # ── 1. DOM STRUCTURE FINGERPRINTING ────────────────────────────
        print("\n📊 1. FINGERPRINTING LINKEDIN FEED DOM ELEMENTS...")
        selectors_to_check = {
            "feed_container": "[role='feed'], div.scaffold-finite-scroll, main.scaffold-layout__main, div.scaffold-layout__content",
            "post_articles": "div[data-id], div.feed-shared-update-v2, div[role='article'], div[data-view-name='feed-full-update'], div.occludable-update",
            "actor_names": "span.update-components-actor__name, span.feed-shared-actor__name, div[class*='actor__title'], a[class*='actor'], span.update-components-actor__title",
            "actor_headlines": "span.update-components-actor__description, div.update-components-actor__headline, span.feed-shared-actor__description",
            "like_buttons": "button[aria-label*='Like'], button.react-button__trigger, button[aria-label*='React']",
            "comment_buttons": "button[aria-label*='Comment'], button[aria-label*='comment']",
            "repost_buttons": "button[aria-label*='Repost'], button[aria-label*='repost']",
            "send_buttons": "button[aria-label*='Send'], button[aria-label*='send']",
            "see_more_buttons": "button.feed-shared-inline-show-more-text__see-more-less-toggle, button[data-test-id='expandable-text-button'], button:has-text('...more')",
            "comment_editors": "div.ql-editor, div[contenteditable='true'], div[role='textbox']",
            "identity_profile_module": "div.identity-headline, div.feed-identity-module, div.sidebar-module",
            "sort_dropdown": "button[aria-label*='Sort by']"
        }

        for key, sel in selectors_to_check.items():
            els = await page.query_selector_all(sel)
            count = len(els)
            aria_sample = await els[0].get_attribute("aria-label") if count > 0 else None
            tag_sample = await els[0].evaluate("el => el.tagName") if count > 0 else None
            print(f"   • {key:25s}: {count:2d} found (tag={tag_sample}, aria={aria_sample!r})")
            report["dom_structure_fingerprints"][key] = {
                "selector": sel,
                "count": count,
                "sample_tag": tag_sample,
                "sample_aria": aria_sample
            }

        # ── 2. ACTIVE FEED POST EXTRACTION ──────────────────────────────
        print("\n🔍 2. EXTRACTING ACTIVE FEED POST CARDS DETAILS...")
        post_cards = await page.query_selector_all("div[data-id], div.feed-shared-update-v2, div[data-view-name='feed-full-update']")
        if not post_cards:
            post_cards = await page.query_selector_all("div[role='article']")

        print(f"   Found {len(post_cards)} candidate feed post cards.")

        extracted_posts = []
        for idx, card in enumerate(post_cards[:5], 1):
            post_data = await card.evaluate("""(el, idx) => {
                const dataId = el.getAttribute('data-id') || el.getAttribute('data-urn') || el.getAttribute('id') || '';
                
                // Author Name
                const nameEl = el.querySelector("span.update-components-actor__name, span.feed-shared-actor__name, div[class*='actor__title'] span[aria-hidden='true'], a[class*='actor'] span, div.update-components-actor__title span");
                let authorName = nameEl ? (nameEl.innerText || nameEl.textContent).trim() : '';
                if (!authorName) {
                    const fallbackName = el.querySelector("span[dir='ltr']");
                    authorName = fallbackName ? (fallbackName.innerText || fallbackName.textContent).trim() : 'Unknown Author';
                }

                // Author Headline
                const headlineEl = el.querySelector("span.update-components-actor__description, div.update-components-actor__headline, span.feed-shared-actor__description, span.update-components-actor__supplementary-info");
                const authorHeadline = headlineEl ? (headlineEl.innerText || headlineEl.textContent).trim() : '';

                // Post Content Text
                const textEl = el.querySelector("div.update-components-text, div.feed-shared-update-v2__description, span.break-words, div.feed-shared-inline-show-more-text");
                const postText = textEl ? (textEl.innerText || textEl.textContent).trim() : (el.innerText || '').substring(0, 300);

                // Social Metrics
                const socialCountsEl = el.querySelector("span.social-details-social-counts__reactions-count, button[aria-label*='reaction']");
                const reactionsCount = socialCountsEl ? (socialCountsEl.innerText || '').trim() : '0';

                const commentCountEl = el.querySelector("button[aria-label*='comment']");
                const commentsCount = commentCountEl ? (commentCountEl.innerText || '').trim() : '0';

                // Media presence
                const hasImage = !!el.querySelector("img.update-components-image__image, div.feed-shared-image, img[src*='media']");
                const hasVideo = !!el.querySelector("video, div.feed-shared-video");
                const hasArticle = !!el.querySelector("article, div.update-components-article");

                return {
                    post_index: idx,
                    data_id: dataId,
                    author_name: authorName,
                    author_headline: authorHeadline,
                    text_snippet: postText.substring(0, 160).replace(/\\n/g, ' ') + (postText.length > 160 ? '...' : ''),
                    text_length: postText.length,
                    reactions_count: reactionsCount,
                    comments_count: commentsCount,
                    media_type: hasVideo ? 'Video' : (hasImage ? 'Image' : (hasArticle ? 'Article' : 'Text/Other'))
                };
            }""", idx)
            extracted_posts.append(post_data)
            print(f"   [{idx}] Author: {post_data['author_name']} | Media: {post_data['media_type']} | TextLen: {post_data['text_length']} chars")
            print(f"       Snippet: {post_data['text_snippet']!r}")

        report["active_feed_posts"] = extracted_posts

        # ── 3. LIVE INTERACTIVE DOM ACTIONS ─────────────────────────────
        print("\n🕹️ 3. EXECUTING LIVE DOM INTERACTIONS...")

        # Action A: Smooth scroll feed
        print("  [Action A] Smooth scrolling feed to test lazy-loading...")
        await page.mouse.wheel(0, 600)
        await asyncio.sleep(1.5)
        await page.mouse.wheel(0, 600)
        await asyncio.sleep(1.5)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        print("  ✅ Scroll interaction finished.")
        report["interactions"].append({"action": "smooth_scroll", "status": "PASSED"})

        # Action B: Expand post text via '...more' button
        print("  [Action B] Searching for '...more' expandable text button...")
        see_more_btns = await page.query_selector_all("button.feed-shared-inline-show-more-text__see-more-less-toggle, button[data-test-id='expandable-text-button'], button:has-text('...more')")
        if see_more_btns:
            await see_more_btns[0].click()
            await asyncio.sleep(1.5)
            print("  ✅ Clicked '...more' expansion button. Post content expanded.")
            report["interactions"].append({"action": "expand_post_more", "status": "PASSED"})
        else:
            print("  ℹ️ No '...more' button visible on current top viewport.")
            report["interactions"].append({"action": "expand_post_more", "status": "SKIPPED_NOT_VISIBLE"})

        # Action C: Hover over Reaction/Like button to inspect reaction picker menu
        print("  [Action C] Hovering over Like button to reveal live reaction picker...")
        like_btn = await page.query_selector("button[aria-label*='Like'], button.react-button__trigger, button[aria-label*='React']")
        if like_btn:
            await like_btn.hover()
            await asyncio.sleep(2)
            reactions = await page.query_selector_all("button[aria-label*='Like'], button[aria-label*='Celebrate'], button[aria-label*='Support'], button[aria-label*='Love'], button[aria-label*='Insightful'], button[aria-label*='Funny']")
            reaction_labels = []
            for r in reactions:
                lbl = await r.get_attribute("aria-label")
                if lbl and lbl not in reaction_labels:
                    reaction_labels.append(lbl)
            print(f"  ✅ Reactions picker revealed! Found options: {reaction_labels}")
            report["interactions"].append({"action": "hover_like_reactions", "status": "PASSED", "reactions": reaction_labels})
        else:
            print("  ⚠️ Like button element not found.")
            report["interactions"].append({"action": "hover_like_reactions", "status": "FAILED_NOT_FOUND"})

        # Action D: Open Comment box & target TipTap rich text editor
        print("  [Action D] Clicking Comment button & focusing TipTap editor...")
        comment_btn = await page.query_selector("button[aria-label*='Comment'], button[aria-label*='comment']")
        if comment_btn:
            await comment_btn.click()
            await asyncio.sleep(2)
            # Scoped to page per body-level editor rule
            editor = await page.query_selector("div.ql-editor, div[contenteditable='true']")
            if editor:
                await editor.click()
                await asyncio.sleep(1)
                await editor.fill("DOM examination test draft...")
                await asyncio.sleep(1.5)
                await editor.fill("")  # Clear text safeguard
                await asyncio.sleep(1)
                print("  ✅ TipTap comment editor focused, typed test string, and safely cleared (PREPRODUCTION).")
                report["interactions"].append({"action": "open_and_type_comment_editor", "status": "PASSED"})
            else:
                print("  ⚠️ Comment editor element not found after clicking comment button.")
                report["interactions"].append({"action": "open_and_type_comment_editor", "status": "FAILED_EDITOR_MISSING"})
        else:
            print("  ⚠️ Comment button element not found.")
            report["interactions"].append({"action": "open_and_type_comment_editor", "status": "FAILED_BUTTON_MISSING"})

        # Capture Screenshot
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=False)
        print(f"\n📸 Live browser screenshot captured: {SCREENSHOT_PATH}")
        report["screenshot_path"] = str(SCREENSHOT_PATH)

        # Write Report JSON
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"📁 JSON analysis report written: {OUTPUT_JSON}")

        print("\n" + "=" * 75)
        print(" 🎉 LINKEDIN FEED DOM INTERACTIVE EXAMINATION COMPLETE!")
        print("=" * 75)

if __name__ == "__main__":
    asyncio.run(analyze_linkedin_feed())
