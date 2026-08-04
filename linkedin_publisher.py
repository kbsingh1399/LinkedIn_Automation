import asyncio
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInPublisher:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.user_data_dir = settings.linkedin_user_data_dir
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    async def ensure_logged_in(self, page) -> bool:
        """Navigates to LinkedIn and performs automated login if required."""
        print("🔍 Verifying LinkedIn login session...")
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"⚠️ Navigation notice: {e}")

        current_url = page.url.lower()
        print(f"   Current URL: {page.url}")

        if ("feed" in current_url or "mynetwork" in current_url or "messaging" in current_url) and "login" not in current_url:
            print("✅ Already logged in to LinkedIn!")
            return True

        print("\n🔑 LinkedIn Login Required! Initiating autonomous login...")
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        username = settings.linkedin_username
        password = settings.linkedin_password

        if not username or not password:
            print("❌ Error: LinkedIn credentials missing in config / .env!")
            return False

        try:
            # 1. Fill Username / Email
            print("  ├── Filling email...")
            user_field = page.locator("input[type='email']:visible, input#username:visible, input[name='session_key']:visible").first
            await user_field.wait_for(timeout=10000)
            await user_field.fill(username)
            await page.wait_for_timeout(1000)

            # 2. Fill Password
            print("  ├── Filling password...")
            pass_field = page.locator("input[type='password']:visible, input#password:visible, input[name='session_password']:visible").first
            await pass_field.wait_for(timeout=10000)
            await pass_field.fill(password)
            await page.wait_for_timeout(1000)

            # 3. Press Enter to Submit Login
            print("  ├── Submitting login form via Enter key...")
            await pass_field.press("Enter")

            await page.wait_for_timeout(6000)
            current_url = page.url.lower()
            print(f"   URL after login attempt: {page.url}")

            # Check if 2FA/Security Verification checkpoint appears
            if "checkpoint" in current_url or "challenge" in current_url:
                print("\n⚠️ Security Checkpoint / 2FA detected on LinkedIn.")
                print("   Please complete the verification on the open browser window if prompted...")
                while "feed" not in page.url.lower() and "checkpoint" in page.url.lower():
                    await asyncio.sleep(2)

            if "feed" in page.url.lower() or "mynetwork" in page.url.lower():
                print("✅ Successfully logged in to LinkedIn!")
                return True

        except Exception as e:
            print(f"⚠️ Automated LinkedIn login error: {e}")

        return "feed" in page.url.lower()

    async def publish_post_option(self, option_dir: Path, dry_run: bool = False) -> bool:
        """Publishes a LinkedIn post option (text + media) directly to LinkedIn."""
        post_txt_file = option_dir / "linkedin_post.txt"
        media_dir = option_dir / "media"

        if not post_txt_file.exists():
            print(f"❌ Error: Post text file missing in {option_dir}")
            return False

        post_text = post_txt_file.read_text(encoding="utf-8").strip()

        # Find media asset
        media_files = list(media_dir.glob("*")) if media_dir.exists() else []
        valid_media = [f for f in media_files if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".gif"]]
        media_file = valid_media[0] if valid_media else None

        print(f"\n🚀 Publishing Post Option to LinkedIn from: {option_dir.name}")
        print(f"   Media Asset: {media_file.name if media_file else 'None (Text Only)'}")
        print(f"   Post Preview: {post_text[:120]}...\n")

        if dry_run:
            print("🧪 [DRY RUN] Skipping actual LinkedIn publishing.")
            return True

        # Safely clear stale locks for our isolated profile without affecting other Chrome processes
        lock_file = self.user_data_dir / "SingletonLock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                channel="chrome",
                headless=self.headless,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized", "--remote-debugging-port=9223", "--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else await context.new_page()

            logged_in = await self.ensure_logged_in(page)
            if not logged_in:
                print("❌ Failed to verify LinkedIn login. Aborting publish.")
                await context.close()
                return False

            # Navigate to feed
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            try:
                # 1. Click 'Start a post' trigger button
                print("  ├── Triggering LinkedIn post editor...")
                start_post_selectors = [
                    "button.share-mb-launcher",
                    "button:has-text('Start a post')",
                    "button[data-view-name='share-box-trigger']",
                    "div.share-box-feed-entry__wrapper button"
                ]
                start_btn = None
                for sel in start_post_selectors:
                    try:
                        start_btn = await page.wait_for_selector(sel, timeout=5000)
                        if start_btn:
                            break
                    except:
                        continue

                if start_btn:
                    await start_btn.click()
                    await page.wait_for_timeout(3000)

                # 2. Upload media file if present
                if media_file:
                    print(f"  ├── Attaching media file: {media_file.name} ...")
                    file_input = await page.query_selector("input[type='file']")
                    if file_input:
                        await file_input.set_input_files(str(media_file.resolve()))
                        await page.wait_for_timeout(4000)

                        # Click 'Next' or 'Done' on media editor modal if presented
                        next_media_btn = await page.query_selector("button:has-text('Next'), button:has-text('Done')")
                        if next_media_btn:
                            await next_media_btn.click()
                            await page.wait_for_timeout(2000)

                # 3. Insert Post Copy
                print("  ├── Entering post content...")
                editor_selectors = [
                    "div.ql-editor",
                    "div[contenteditable='true']",
                    "div[role='textbox']"
                ]
                editor = None
                for sel in editor_selectors:
                    try:
                        editor = await page.wait_for_selector(sel, timeout=5000)
                        if editor:
                            break
                    except:
                        continue

                if editor:
                    await editor.focus()
                    await editor.fill(post_text)
                    await page.wait_for_timeout(2000)

                # 4. Click Post button
                print("  ├── Clicking 'Post' button...")
                post_submit_btn = await page.query_selector("button.share-actions__primary-action, button:has-text('Post')")
                if post_submit_btn:
                    await post_submit_btn.click()
                    await page.wait_for_timeout(6000)
                    print("🎉 Successfully published post to LinkedIn!")
                    await context.close()
                    return True

            except Exception as e:
                print(f"⚠️ Error while publishing post: {e}")
            finally:
                await context.close()

        return False

async def main():
    publisher = LinkedInPublisher(headless=False)
    # Check login session
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(publisher.user_data_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await publisher.ensure_logged_in(page)
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
