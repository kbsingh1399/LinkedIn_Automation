import asyncio
from playwright.async_api import async_playwright
from utils.stealth_chrome import launch_stealth_chrome

async def inspect_reply_button():
    async with async_playwright() as p:
        context, page = await launch_stealth_chrome(p, profile="linkedin")
        await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        cards = await page.query_selector_all("article.nt-card")
        print(f"Total cards: {len(cards)}")

        for i, card in enumerate(cards):
            txt = await card.inner_text()
            txt_lower = txt.lower()
            if "mentioned" in txt_lower or "replied" in txt_lower or "commented" in txt_lower:
                print(f"\n--- Clicking Actionable Notif #{i+1}: {txt[:60]} ---")
                await card.click()
                await asyncio.sleep(4)

                print("Current URL:", page.url)

                # 1. First check if editor exists
                editors = await page.query_selector_all("div[contenteditable='true']")
                if not editors:
                    print("No contenteditable editors found immediately. Searching for Comment / Reply trigger buttons...")
                    # Try clicking Comment button on the post card
                    comment_btns = await page.query_selector_all("button:has-text('Comment'), button[aria-label*='Comment' i], button.comment-button")
                    print(f"Found {len(comment_btns)} Comment buttons on page.")
                    for cb in comment_btns:
                        if await cb.is_visible():
                            print("Clicking Comment button on post...")
                            await cb.click(force=True)
                            await asyncio.sleep(2)
                            break
                    
                    # Try clicking Reply button on comment thread if still no editor
                    editors = await page.query_selector_all("div[contenteditable='true']")
                    if not editors:
                        reply_btns = await page.query_selector_all("button:has-text('Reply'), button[aria-label*='Reply' i], button.comments-comment-social-bar__action-tab")
                        print(f"Found {len(reply_btns)} Reply buttons on page.")
                        for rb in reply_btns:
                            if await rb.is_visible():
                                print("Clicking Reply button under comment...")
                                await rb.click(force=True)
                                await asyncio.sleep(2)
                                break

                editors = await page.query_selector_all("div[contenteditable='true']")
                print(f"Found {len(editors)} contenteditable editors after trigger click.")

                for idx, ed in enumerate(editors):
                    vis = await ed.is_visible()
                    print(f"Editor #{idx+1} Visible: {vis}")

                    # Type sample text to activate submit button
                    await ed.fill("Thank you!")
                    await asyncio.sleep(1)

                    # Search buttons in parent container
                    btns = await page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll("button"));
                        return buttons.map(b => ({
                            text: b.innerText.trim(),
                            aria: b.getAttribute("aria-label"),
                            class: b.className,
                            visible: b.offsetWidth > 0 && b.offsetHeight > 0
                        })).filter(b => b.visible && (b.text.includes("Reply") || b.text.includes("Post") || (b.aria && (b.aria.includes("Reply") || b.aria.includes("Post")))));
                    }''')
                    print(f"Submit buttons found after typing: {btns}")
                break

if __name__ == "__main__":
    asyncio.run(inspect_reply_button())
