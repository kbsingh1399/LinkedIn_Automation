import asyncio
from playwright.async_api import async_playwright

async def get_inbox_dom():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=r"C:\Users\SIGMA\Documents\LinkedIn_Automation\chrome_profile",
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
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
