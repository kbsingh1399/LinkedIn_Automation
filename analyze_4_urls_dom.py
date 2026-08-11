import asyncio
import sys
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from utils.stealth_chrome import launch_stealth_chrome, apply_stealth_window

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPORT_PATH = Path(r"C:\Users\SIGMA\.gemini\antigravity-ide\brain\728c3d79-fe7b-4a11-9cd2-0486c8fc9c68\four_urls_dom_analysis.json")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

TARGET_URLS = [
    "https://www.linkedin.com/feed/",
    "https://www.linkedin.com/notifications/",
    "https://www.linkedin.com/messaging/",
    "https://gemini.google.com/app"
]

async def is_port_active(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def analyze_target_url(page, url: str):
    print(f"\n===========================================================================")
    print(f" 🌐 ANALYZING TARGET URL: {url}")
    print(f"===========================================================================")

    # Check current URL or navigate
    if url not in page.url:
        print(f"📌 Navigating tab to {url} ...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            print(f"  ⚠️ Navigation note: {e}")

    await asyncio.sleep(4)
    await page.bring_to_front()
    await page.mouse.wheel(0, 800)
    await asyncio.sleep(2)

    current_title = await page.title()
    current_url = page.url
    print(f"📄 Connected Title : {current_title}")
    print(f"🔗 Connected URL   : {current_url}")

    # Specific selector dictionary based on target page type
    dom_metrics = {}

    if "linkedin.com/feed" in current_url:
        selectors = {
            "Feed_Containers": "div.feed-shared-update-v2, div[data-id], article, div.occludable-update",
            "Like_Buttons": "button[aria-label*='Like'], button.react-button__trigger",
            "Comment_Buttons": "button[aria-label*='Comment']",
            "Repost_Buttons": "button[aria-label*='Repost']",
            "Send_Buttons": "button[aria-label*='Send']",
            "TipTap_Editors": "div.ql-editor, div[contenteditable='true'], div[role='textbox']",
            "Search_Bar": "input.search-global-typeahead__input, input[aria-label*='Search']",
            "Identity_Module": "div.feed-identity-module, div.identity-headline"
        }
    elif "linkedin.com/notifications" in current_url:
        selectors = {
            "Notification_Cards": "article.nt-card, div.notification-card, div.nt-card-content",
            "Notification_Text": "div.nt-card-content__title, span.nt-card-content__text",
            "Unread_Badges": "span.nt-card__unread-indicator, div.nt-card--unread",
            "Action_Buttons": "button[aria-label*='Reply'], button[aria-label*='More options']",
            "Inline_Reply_Editors": "div[contenteditable='true'], textarea, input[type='text']",
            "Global_Nav": "nav.global-nav__nav"
        }
    elif "linkedin.com/messaging" in current_url:
        selectors = {
            "Conversation_List": "ul.msg-conversations-container__convo-list, div.msg-conversations-container__convo-item",
            "Active_Chat_Header": "h2.msg-entity-lockup__entity-title, div.msg-thread__topcard",
            "Chat_Message_Bubbles": "div.msg-s-event-listitem__message-bubble, p.msg-s-event-listitem__body",
            "Message_Input_Box": "div.msg-form__contenteditable, div[contenteditable='true'], div[role='textbox']",
            "Send_Message_Button": "button.msg-form__send-button, button[type='submit']",
            "Attachment_Buttons": "button[aria-label*='Attach'], button[aria-label*='Image']"
        }
    elif "gemini.google.com" in current_url:
        selectors = {
            "Prompt_Input_Box": "div.rich-textarea, div[contenteditable='true'], textarea, p.placeholder",
            "Submit_Prompt_Button": "button[aria-label*='Send'], button.send-button",
            "Gemini_Response_Cards": "message-content, div.model-response-text, div.markdown",
            "Model_Picker": "button[aria-label*='Model'], div.model-selector",
            "New_Chat_Button": "button[aria-label*='New chat'], div.side-nav-button",
            "Code_Blocks": "pre, code-block, div.code-block"
        }
    else:
        selectors = {
            "All_Buttons": "button",
            "Editable_Editors": "div[contenteditable='true'], textarea, input",
            "Headings": "h1, h2, h3"
        }

    print("\n📊 DOM SELECTOR COUNT BREAKDOWN:")
    for cat, sel in selectors.items():
        try:
            els = await page.query_selector_all(sel)
            count = len(els)
            aria = await els[0].get_attribute("aria-label") if count > 0 else ""
            tag = await els[0].evaluate("el => el.tagName") if count > 0 else ""
            print(f"   • {cat:22s}: {count:2d} found (tag={tag}, aria={aria!r})")
            dom_metrics[cat] = {
                "selector": sel,
                "count": count,
                "sample_tag": tag,
                "sample_aria": aria
            }
        except Exception as e:
            print(f"   • {cat:22s}: Error - {e}")
            dom_metrics[cat] = {"selector": sel, "count": 0, "error": str(e)}

    return {
        "requested_url": url,
        "actual_url": current_url,
        "title": current_title,
        "dom_metrics": dom_metrics
    }

async def main():
    print("=" * 75)
    print(" 🔬 CDP MULTI-URL DEEP DOM ANALYSIS AGENT")
    print("===========================================================================")

    async with async_playwright() as p:
        active = await is_port_active(9222)
        if active:
            print("🔗 Connecting via CDP to user's open debug Chrome on http://127.0.0.1:9222 ...")
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else None
        else:
            print("🚀 Launching Chrome in visible stealth mode ...")
            context, _ = await launch_stealth_chrome(p, profile="linkedin")

        pages = context.pages if context and context.pages else []
        page = pages[0] if pages else await context.new_page()

        results = []
        for url in TARGET_URLS:
            res = await analyze_target_url(page, url)
            results.append(res)

        # Write unified report
        full_report = {
            "timestamp": str(asyncio.get_event_loop().time()),
            "total_urls_analyzed": len(results),
            "url_reports": results
        }

        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        print("\n" + "=" * 75)
        print(f"🎉 4-URL DEEP DOM ANALYSIS COMPLETE!")
        print(f"📁 Unified Report saved to: {REPORT_PATH}")
        print("=" * 75)

if __name__ == "__main__":
    asyncio.run(main())
