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

        user_el = page.locator("input[type='email']:visible, input#username:visible, input[name='session_key']:visible").first
        await user_el.wait_for(timeout=5000)
        print("Visible user input element found!")
        await user_el.fill(settings.linkedin_username)
        print("Filled email!")

        pass_el = page.locator("input[type='password']:visible, input#password:visible, input[name='session_password']:visible").first
        await pass_el.wait_for(timeout=5000)
        print("Visible password input element found!")
        await pass_el.fill(settings.linkedin_password)
        print("Filled password!")

        print("Pressing Enter to submit login...")
        await pass_el.press("Enter")

        await page.wait_for_timeout(8000)
        print(f"Final URL: {page.url}")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
