import asyncio
import os
import sys
from playwright.async_api import async_playwright
from linkedin_publisher import LinkedInPublisher

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def agentic_feed_dom():
    pub = LinkedInPublisher(headless=False)
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(pub.user_data_dir),
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--test-type",
                "--remote-debugging-port=9222"
            ]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        # OS Maximize via CDP
        try:
            client = await context.new_cdp_session(page)
            win = await client.send("Browser.getWindowForTarget")
            await client.send("Browser.setWindowBounds", {"windowId": win["windowId"], "bounds": {"windowState": "maximized"}})
        except Exception as e:
            print(f"⚠️ Could not set window bounds via CDP: {e}")
        
        await pub.ensure_logged_in(page)
        await page.bring_to_front()
        
        print("\n🤖 [AGENTIC CONTROL] Navigating to LinkedIn Feed...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        # Scroll down to trigger lazy loading of feed posts
        for _ in range(3):
            await page.mouse.wheel(0, 600)
            await asyncio.sleep(1.0)
            
        try:
            await page.wait_for_selector("div.feed-shared-update-v2, article, div[data-urn]", timeout=10000)
        except Exception as e:
            print(f"⚠️ Wait for feed selector timeout: {e}")
        
        # Agentic DOM Analysis of Feed Posts
        dom_report = await page.evaluate('''() => {
            const selectors = [
                "div[data-view-name='feed-full-update']",
                "div.feed-shared-update-v2",
                "article.feed-shared-update",
                "[role='article']",
                "[role='listitem']",
                "div[class*='update-v2']",
                "div.occludable-update"
            ];
            let posts = [];
            for (const sel of selectors) {
                const found = Array.from(document.querySelectorAll(sel));
                if (found.length > posts.length) {
                    posts = found;
                    break;
                }
            }
            return posts.slice(0, 5).map((post, idx) => {
                const authorEl = post.querySelector('.update-components-actor__name, .feed-shared-actor__name, span[class*="actor__name"], span[aria-hidden="true"]');
                const textEl = post.querySelector('.update-components-text, .feed-shared-update-v2__description, div[class*="description"], span.break-words');
                const commentBtn = post.querySelector('button.comment-button, button[aria-label*="Comment" i], button:has-text("Comment")');
                const likeBtn = post.querySelector('button.react-button__trigger, button[aria-label*="Like" i], button:has-text("Like")');
                return {
                    index: idx + 1,
                    urn: post.getAttribute('data-urn') || post.getAttribute('data-id') || 'N/A',
                    author: authorEl ? authorEl.innerText.trim().split('\\n')[0] : 'Unknown',
                    textSnippet: textEl ? textEl.innerText.trim().slice(0, 120) : 'No text body',
                    hasCommentButton: !!commentBtn,
                    hasLikeButton: !!likeBtn
                };
            });
        }''')
        
        print(f"\n📊 [DOM ANALYSIS REPORT] Found {len(dom_report)} active feed posts:")
        for item in dom_report:
            print(f"  • Post #{item['index']} | Author: {item['author']} | LikeBtn: {item['hasLikeButton']} | CommentBtn: {item['hasCommentButton']}")
            print(f"    Text: {item['textSnippet']}...")
            
        screenshot_path = "agentic_feed_dom_analysis.png"
        await page.screenshot(path=screenshot_path)
        print(f"\n📸 Saved screenshot: {screenshot_path}")
        await asyncio.sleep(2)
        await context.close()

if __name__ == "__main__":
    asyncio.run(agentic_feed_dom())
