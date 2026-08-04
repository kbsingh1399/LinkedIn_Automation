import asyncio
import sys
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def main():
    user_data_dir = settings.linkedin_user_data_dir
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--start-maximized", "--remote-debugging-port=9223", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Scroll to load action bar
        await page.mouse.wheel(0, 400)
        await asyncio.sleep(2)

        # Click first comment button
        comment_btn = await page.query_selector("button[aria-label='Comment'], button[aria-label*='Comment']")
        if comment_btn:
            print("👇 Clicking Comment Button...")
            await comment_btn.click()
            await asyncio.sleep(3)

        # Inspect DOM after clicking Comment button
        info = await page.evaluate("""() => {
            const allElements = Array.from(document.querySelectorAll("div, p, span, form"));
            const commentInputs = allElements.filter(e => {
                const isEditable = e.getAttribute("contenteditable") === "true" || e.getAttribute("role") === "textbox" || e.className.includes("editor") || e.className.includes("comment");
                return isEditable && e.tagName !== "BUTTON";
            });

            const submitBtns = Array.from(document.querySelectorAll("button")).filter(b => {
                const text = (b.innerText || "").toLowerCase();
                const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                return text.includes("post") || text.includes("comment") || aria.includes("post") || aria.includes("comment");
            });

            return {
                inputsFound: commentInputs.length,
                inputSamples: commentInputs.slice(0, 5).map(e => ({
                    tag: e.tagName,
                    className: e.className,
                    contenteditable: e.getAttribute("contenteditable"),
                    role: e.getAttribute("role"),
                    placeholder: e.getAttribute("placeholder")
                })),
                submitsFound: submitBtns.length,
                submitSamples: submitBtns.slice(0, 5).map(b => ({
                    tag: b.tagName,
                    className: b.className,
                    innerText: b.innerText,
                    ariaLabel: b.getAttribute("aria-label")
                }))
            };
        }""")

        print(f"📊 Comment Inputs Found ({info['inputsFound']}):")
        for idx, item in enumerate(info['inputSamples'], 1):
            print(f"  [{idx}] Tag: {item['tag']} | Class: '{item['className']}' | ContentEditable: {item['contenteditable']} | Role: {item['role']}")

        print(f"\n📊 Submit Buttons Found ({info['submitsFound']}):")
        for idx, item in enumerate(info['submitSamples'], 1):
            print(f"  [{idx}] Class: '{item['className']}' | Text: '{item['innerText'].strip()}' | Aria: '{item['ariaLabel']}'")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
