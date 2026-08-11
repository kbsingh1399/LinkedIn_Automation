import asyncio
from playwright.async_api import async_playwright
from utils.stealth_chrome import launch_stealth_chrome

async def get_inbox_dom():
    async with async_playwright() as p:
        context, page = await launch_stealth_chrome(p, profile="linkedin")
        
        await page.goto("https://www.linkedin.com/messaging/")
        await asyncio.sleep(5)
        
        # Click the 3rd conversation
        convs = await page.query_selector_all("li.msg-conversation-listitem")
        if len(convs) >= 3:
            await convs[2].click()
            await asyncio.sleep(3)
        
        # Dump HTML of the message list container
        html = await page.evaluate('''() => {
            let container = document.querySelector(".msg-s-message-list-container, ul.msg-s-message-list, div.msg-s-message-list-inner, section.msg-s-message-list, div[data-view-name='message-thread']");
            if (!container) {
                // fallback to the whole form area's parent
                let form = document.querySelector(".msg-form");
                if (form) {
                    container = form.parentElement.parentElement;
                }
            }
            return container ? container.innerHTML : document.body.innerHTML;
        }''')
        
        with open("inbox_dom_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(get_inbox_dom())
