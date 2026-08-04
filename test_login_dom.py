import asyncio
from playwright.async_api import async_playwright
from config import settings

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(settings.linkedin_user_data_dir),
            headless=False,
            viewport={"width": 1280, "height": 850}
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        print(f"Current URL: {page.url}")

        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} inputs:")
        for idx, i in enumerate(inputs):
            id_attr = await i.get_attribute("id")
            name_attr = await i.get_attribute("name")
            type_attr = await i.get_attribute("type")
            placeholder = await i.get_attribute("placeholder")
            print(f"  [{idx}] id='{id_attr}' name='{name_attr}' type='{type_attr}' placeholder='{placeholder}'")

        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons:")
        for idx, b in enumerate(buttons):
            text = (await b.inner_text()).strip()
            type_attr = await b.get_attribute("type")
            print(f"  [{idx}] text='{text}' type='{type_attr}'")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
