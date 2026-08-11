import asyncio
from playwright.async_api import async_playwright
from config import settings
from utils.stealth_chrome import launch_stealth_chrome

async def main():
    async with async_playwright() as p:
        context, page = await launch_stealth_chrome(p, profile="linkedin")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Scroll down to load feed
        await page.mouse.wheel(0, 800)
        await page.wait_for_timeout(3000)

        divs = await page.query_selector_all("div")
        print(f"Total divs on page: {len(divs)}")

        selectors = [
            "div[data-view-name='feed-full-update']",
            "div.feed-shared-update-v2",
            "div[data-urn*='activity']",
            "div.occludable-update",
            "div.update-components-actor",
            "div.scaffold-finite-scroll div"
        ]

        for sel in selectors:
            elems = await page.query_selector_all(sel)
            print(f"Selector '{sel}': {len(elems)} elements")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
