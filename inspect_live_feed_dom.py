import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

async def main():
    user_data_dir = settings.linkedin_user_data_dir
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--start-maximized", "--remote-debugging-port=9223", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Scroll down to ensure content renders
        for _ in range(5):
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(0.5)

        info = await page.evaluate("""() => {
            const main = document.querySelector("main") || document.body;
            const children = Array.from(main.children);
            const containers = Array.from(main.querySelectorAll("div[id], div[class*='feed'], div[class*='update'], div[data-id]"));
            
            return {
                url: window.location.href,
                mainChildCount: children.length,
                containerCount: containers.length,
                samples: containers.slice(0, 15).map(c => ({
                    tag: c.tagName,
                    id: c.id,
                    className: c.className.substring(0, 80),
                    dataUrn: c.getAttribute("data-urn"),
                    dataId: c.getAttribute("data-id"),
                    textLen: (c.innerText || "").length
                }))
            };
        }""")

        print(f"URL: {info['url']}")
        print(f"Main Children: {info['mainChildCount']} | Containers Found: {info['containerCount']}")
        for idx, s in enumerate(info['samples'], 1):
            print(f" [{idx:02d}] Tag: {s['tag']} | ID: '{s['id']}' | Class: '{s['className']}' | Data-Id: '{s['dataId']}' | TextLen: {s['textLen']}")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
