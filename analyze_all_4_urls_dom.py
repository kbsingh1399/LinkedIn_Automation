import asyncio
import sys
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPORT_FILE = Path("dom_analysis_report_all_4_urls.json")

async def check_cdp(port: int = 9222) -> bool:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return req.status == 200
    except Exception:
        return False

async def audit_url(page, url: str, name: str, queries: dict) -> dict:
    print("\n" + "=" * 70)
    print(f" 🌐 AGENTIC DOM AUDIT FOR {name.upper()}")
    print(f" 📍 URL: {url}")
    print("=" * 70)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
    except Exception as e:
        print(f"⚠️ Page goto error for {url}: {e}")

    await page.bring_to_front()
    await asyncio.sleep(4)

    # Maximize via CDP
    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Browser.setWindowBounds", {"windowId": 1, "bounds": {"windowState": "maximized"}})
    except Exception:
        pass

    # Scroll slightly to trigger lazy elements
    await page.mouse.wheel(0, 500)
    await asyncio.sleep(1.5)
    await page.mouse.wheel(0, -300)
    await asyncio.sleep(1)

    result = {
        "url": page.url,
        "title": await page.title(),
        "selectors": {}
    }

    for key, sel_list in queries.items():
        if isinstance(sel_list, str):
            sel_list = [sel_list]
        
        matches = []
        best_sel = None
        best_count = 0
        
        for sel in sel_list:
            try:
                els = await page.query_selector_all(sel)
                cnt = len(els)
                if cnt > 0:
                    matches.append({"selector": sel, "count": cnt})
                    if cnt > best_count:
                        best_count = cnt
                        best_sel = sel
            except Exception as sel_err:
                matches.append({"selector": sel, "error": str(sel_err)})

        # Get details for up to 2 sample elements of the best working selector
        samples = []
        if best_sel:
            try:
                els = await page.query_selector_all(best_sel)
                for idx, el in enumerate(els[:2]):
                    try:
                        tag = await el.evaluate("el => el.tagName")
                        text = (await el.inner_text()).strip().replace("\n", " ")[:100]
                        aria = await el.get_attribute("aria-label") or ""
                        cls = await el.get_attribute("class") or ""
                        role = await el.get_attribute("role") or ""
                        samples.append({
                            "index": idx,
                            "tag": tag,
                            "role": role,
                            "aria": aria,
                            "class": cls[:60],
                            "text": text
                        })
                    except Exception:
                        pass
            except Exception:
                pass

        print(f"  • {key:28s} | Best: {best_sel if best_sel else 'NONE':45s} | Count: {best_count:2d}")
        result["selectors"][key] = {
            "best_selector": best_sel,
            "best_count": best_count,
            "all_tested": matches,
            "samples": samples
        }

    # Take screenshot for visual audit
    screenshot_name = f"audit_screenshot_{name}.png"
    try:
        await page.screenshot(path=screenshot_name)
        print(f"  📸 Screenshot saved: {screenshot_name}")
    except Exception as sc_err:
        print(f"  ⚠️ Screenshot failed: {sc_err}")

    return result

async def main():
    cdp_active = await check_cdp(9222)
    
    async with async_playwright() as p:
        if cdp_active:
            print("🔗 Connecting via CDP to existing Chrome on port 9222...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print("🚀 Launching visible persistent Chrome browser...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(settings.linkedin_user_data_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

        # Set window maximized
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setWindowBounds", {"windowId": 1, "bounds": {"windowState": "maximized"}})
        except Exception:
            pass

        full_report = {}

        # 1. LINKEDIN FEED
        feed_queries = {
            "feed_cards": [
                "div[data-view-name='feed-full-update']",
                "div.feed-shared-update-v2",
                "article.feed-shared-update",
                "[role='article']",
                "[role='listitem']",
                "div[class*='update-v2']",
                "div.occludable-update"
            ],
            "see_more_buttons": [
                "button[data-test-id='expandable-text-button']",
                "[data-test-id='expandable-text-button']",
                "button:has-text('...more')",
                "button.feed-shared-inline-show-more-text__see-more-less-toggle"
            ],
            "post_text_content": [
                "div.update-components-update-activity__commentary",
                "div.feed-shared-update-v2__description-text",
                "div.update-components-text",
                "span.break-words[class*='commentary']",
                "div.feed-shared-text",
                "span.break-words"
            ],
            "author_name": [
                "span.update-components-actor__name",
                "span.feed-shared-actor__name",
                "div[class*='actor__title']",
                "a[class*='actor']"
            ],
            "author_headline": [
                "span.update-components-actor__description",
                "div.update-components-actor__headline",
                "span.feed-shared-actor__description",
                "div[class*='actor__description']",
                "div[class*='actor__headline']",
                "span[class*='actor__sub-description']"
            ],
            "like_button": [
                "button.react-button__trigger",
                "button[aria-label*='Like' i]",
                "button:has-text('Like')",
                "button[aria-label*='React' i]"
            ],
            "comment_button": [
                "button.comment-button",
                "button[aria-label*='Comment' i]",
                "button:has-text('Comment')"
            ],
            "rich_text_editor": [
                "div[contenteditable='true']",
                "div[role='textbox']",
                "div.comments-comment-box div[contenteditable='true']",
                ".ql-editor"
            ],
            "comment_submit_button": [
                "button.comments-comment-box__submit-button",
                "form.comments-comment-box__form button.artdeco-button--primary",
                "div.comments-comment-box__submit button.artdeco-button--primary",
                "button.artdeco-button--primary[type='submit']"
            ]
        }
        full_report["linkedin_feed"] = await audit_url(page, "https://www.linkedin.com/feed/", "linkedin_feed", feed_queries)

        # 2. LINKEDIN NOTIFICATIONS
        notif_queries = {
            "notification_cards": [
                "article.nt-card",
                "div.notification-item",
                "li.nt-card",
                "div[data-urn]",
                "section.nt-card",
                "[class*='notification-card']",
                "main li",
                "main article",
                "div[class*='nt-card']"
            ],
            "reply_button": [
                "button.comments-comment-item__reply-button",
                "button[aria-label*='Reply to' i]",
                "button[aria-label*='Reply' i]",
                "button:has-text('Reply')"
            ],
            "notification_editor": [
                "div[contenteditable='true'][role='textbox']",
                "div[contenteditable='true']",
                "div[role='textbox']"
            ],
            "reply_submit_button": [
                "button.comments-comment-box__submit-button",
                "button:has-text('Reply')",
                "button:has-text('Post')",
                "button.artdeco-button--primary[type='submit']"
            ]
        }
        full_report["linkedin_notifications"] = await audit_url(page, "https://www.linkedin.com/notifications/", "linkedin_notifications", notif_queries)

        # 3. LINKEDIN MESSAGING
        messaging_queries = {
            "conversation_cards": [
                "li.msg-conversation-card",
                "li.msg-conversation-listitem",
                "div.msg-conversation-card",
                "a.msg-conversation-listitem__link",
                "a[href*='/messaging/thread/']",
                "div.msg-conversation-listitem__link",
                "div.msg-selectable-entity",
                "ul.msg-conversations-container__convo-list > li"
            ],
            "participant_names": [
                "h3.msg-conversation-listitem__participant-names",
                "span.msg-conversation-card__participant-names",
                "h3",
                "span[class*='participant-name']"
            ],
            "active_message_editor": [
                "div.msg-form__contenteditable[contenteditable='true']",
                "div[role='textbox'][aria-label*='message' i]",
                "div[contenteditable='true'][role='textbox']",
                "div[contenteditable='true']"
            ],
            "chat_history_items": [
                "li.msg-s-message-list__event",
                "li.msg-s-message-list__item",
                "li.msg-s-message-list-item",
                "div.msg-s-message-group",
                "div.msg-s-event-listitem"
            ],
            "sender_names_in_chat": [
                "span.msg-s-message-group__name",
                "span.msg-s-message-group__profile-info",
                "span.msg-s-message-group__meta",
                "span.msg-s-message-list__meta"
            ],
            "message_bubbles": [
                "p.msg-s-event-listitem__body",
                "div.msg-s-event-listitem__message-bubble",
                "div.msg-s-message-group__message-bubble"
            ],
            "send_button": [
                "button[aria-label='Send']",
                "button[aria-label*='Send' i]",
                "button.msg-form__send-button",
                "button[type='submit'][class*='msg-form']"
            ]
        }
        full_report["linkedin_messaging"] = await audit_url(page, "https://www.linkedin.com/messaging/", "linkedin_messaging", messaging_queries)

        # 4. GEMINI WEB
        gemini_queries = {
            "prompt_editor": [
                ".ql-editor",
                "div[contenteditable='true'][role='textbox']",
                "div[contenteditable='true']",
                "p.placeholder",
                "rich-textarea div[contenteditable='true']"
            ],
            "file_inputs": [
                "input[type='file']"
            ],
            "attachment_buttons": [
                "button[aria-label*='Add' i]",
                "button[aria-label*='Upload' i]",
                "button[aria-label*='Attach' i]",
                "button[aria-label*='plus' i]",
                "button.uploader-button",
                "div[role='button']:has-text('+')"
            ],
            "model_responses": [
                "model-response",
                ".markdown",
                ".model-response-text",
                "message-content"
            ],
            "send_button": [
                "button[aria-label*='Send' i]",
                "button[aria-label*='submit' i]",
                "button[aria-label*='Run' i]",
                "button.send-button"
            ],
            "sign_in_buttons": [
                "a[href*='accounts.google.com/ServiceLogin']",
                "a[href*='accounts.google.com/signin']",
                "button:has-text('Sign in')",
                "a:has-text('Sign in')"
            ]
        }
        full_report["gemini_web"] = await audit_url(page, "https://gemini.google.com/app", "gemini_web", gemini_queries)

        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        print("\n" + "=" * 70)
        print(f"🎉 DOM ANALYSIS COMPLETE ACROSS ALL 4 CORE URLS!")
        print(f"📁 Full JSON Report: {REPORT_FILE.resolve()}")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
