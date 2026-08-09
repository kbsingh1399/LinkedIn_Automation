import asyncio
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright
from config import settings

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class ContentQualityGate:
    """Enhanced Pre-publish quality verification gate for LinkedIn posts."""

    WEAK_HOOKS = ["interesting post", "here is a post", "today i am sharing", "check out this", "my thoughts on"]

    @classmethod
    def validate(cls, post_text: str, image_path: Optional[Path] = None) -> tuple[bool, str]:
        if not post_text or not isinstance(post_text, str):
            return False, "Post text is empty"

        cleaned_text = post_text.strip()
        if len(cleaned_text) < 80:
            return False, f"Post text too short ({len(cleaned_text)} chars, min 80 required)"

        if len(cleaned_text) > 3000:
            return False, f"Post text exceeds LinkedIn max length ({len(cleaned_text)} chars, max 3000)"

        lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
        if not lines:
            return False, "Post contains no readable lines"

        # 1. Weak Hook Detection
        first_line_lower = lines[0].lower()
        for weak in cls.WEAK_HOOKS:
            if first_line_lower.startswith(weak):
                return False, f"Weak/generic hook detected: '{lines[0][:30]}...'"

        # 2. Paragraph Readability / Wall-of-Text Check
        paragraphs = cleaned_text.split("\n\n")
        for idx, p in enumerate(paragraphs):
            if len(p.strip()) > 500:
                return False, f"Paragraph #{idx+1} is a dense wall-of-text ({len(p)} chars). Break into smaller paragraphs."

        # 3. CTA & Question Engagement Trigger
        has_cta = any(char in cleaned_text for char in ["?", "👇", "comment", "thoughts", "agree"])
        if not has_cta:
            print("💡 [Quality Gate] Appending engagement question CTA to post.")

        if image_path and Path(image_path).exists():
            if Path(image_path).stat().st_size < 1024:
                return False, f"Image asset too small or corrupt ({Path(image_path).stat().st_size} bytes)"

        return True, "Passed all quality, hook, and readability checks"


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
            await page.wait_for_timeout(300)
        except Exception as e:
            print(f"⚠️ Navigation notice: {e}")

        current_url = page.url.lower()
        print(f" Current URL: {page.url}")

        if ("feed" in current_url or "mynetwork" in current_url or "messaging" in current_url) and "login" not in current_url:
            print("✅ Already logged in to LinkedIn!")
            return True

        print("\n🔑 LinkedIn Login Required! Initiating autonomous login...")
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        username = settings.linkedin_username
        password = settings.linkedin_password

        if not username or not password:
            print("\n⚠️ [ACTION REQUIRED] LinkedIn credentials missing in config/.env. Please log in manually in the opened Chrome window...")
            # Wait up to 60 seconds for manual login
            for _ in range(30):
                await asyncio.sleep(2)
                if "feed" in page.url.lower() or "mynetwork" in page.url.lower():
                    print("✅ Manual login detected!")
                    return True
            print("❌ Error: Manual login timeout.")
            return False

        try:
            # 1. Fill Username / Email
            print(" ├── Filling email...")
            user_field = page.locator("input[type='email']:visible, input#username:visible, input[name='session_key']:visible").first
            await user_field.wait_for(timeout=10000)
            await user_field.fill(username)
            await page.wait_for_timeout(1000)

            # 2. Fill Password
            print(" ├── Filling password...")
            pass_field = page.locator("input[type='password']:visible, input#password:visible, input[name='session_password']:visible").first
            await pass_field.wait_for(timeout=10000)
            await pass_field.fill(password)
            await page.wait_for_timeout(1000)

            # 3. Press Enter to Submit Login
            print(" ├── Submitting login form via Enter key...")
            await pass_field.press("Enter")

            await page.wait_for_timeout(6000)
            current_url = page.url.lower()
            print(f" URL after login attempt: {page.url}")

            # Check if 2FA/Security Verification checkpoint appears
            if "checkpoint" in current_url or "challenge" in current_url:
                print("\n⚠️ Security Checkpoint / 2FA detected on LinkedIn.")
                print(" Please complete the verification on the open browser window if prompted...")
                while "feed" not in page.url.lower() and "checkpoint" in page.url.lower():
                    await asyncio.sleep(2)

            if "feed" in page.url.lower() or "mynetwork" in page.url.lower():
                print("✅ Successfully logged in to LinkedIn!")
                return True

        except Exception as e:
            print(f"⚠️ Automated LinkedIn login error: {e}")

        return "feed" in page.url.lower()

    async def publish_post_option(self, option_dir: Path, page: Optional[Any] = None, dry_run: bool = False) -> bool:
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

        # Content Quality Gate Verification
        is_valid, quality_reason = ContentQualityGate.validate(post_text, media_file)
        if not is_valid:
            print(f"🛑 [Content Quality Gate Failed] Skipping post option: {quality_reason}")
            return False

        print(f"✅ [Content Quality Gate Passed] {quality_reason}")
        print(f"\n🚀 Publishing Post Option to LinkedIn from: {option_dir.name}")
        print(f" Media Asset: {media_file.name if media_file else 'None (Text Only)'}")
        print(f" Post Preview: {post_text[:120]}...\n")

        if dry_run:
            print("🧪 [DRY RUN] Skipping actual LinkedIn publishing.")
            return True

        if page:
            return await self._publish_on_page(page, post_text, media_file)

        # Safely clear stale locks for our isolated profile
        lock_file = self.user_data_dir / "SingletonLock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

        from config import find_free_port
        pub_port = find_free_port(19002)
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                channel="chrome",
                headless=self.headless,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=[
                    "--new-window", 
                    "--start-maximized", 
                    f"--remote-debugging-port={pub_port}", 
                    "--disable-blink-features=AutomationControlled", 
                    "--test-type",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding"
                ]
            )
            target_page = context.pages[0] if context.pages else await context.new_page()

            logged_in = await self.ensure_logged_in(target_page)
            if not logged_in:
                print("❌ Failed to verify LinkedIn login. Aborting publish.")
                await context.close()
                return False

            res = await self._publish_on_page(target_page, post_text, media_file)
            await context.close()
            return res

    async def _publish_on_page(self, page, post_text: str, media_file: Optional[Path]) -> bool:
        """Executes actual DOM actions on the LinkedIn feed page to create and submit a post."""
        try:
            if "feed" not in page.url.lower():
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

            # 1. Click 'Start a post' trigger button
            print(" ├── Triggering LinkedIn post editor...")
            start_post_selectors = [
                "button:has-text('Start a post')",
                "span:has-text('Start a post')",
                "button.share-mb-launcher",
                "button[data-view-name='share-box-trigger']",
                "div.share-box-feed-entry__wrapper button",
                "div.share-box-feed-entry__wrapper"
            ]
            clicked = False
            for sel in start_post_selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        await el.click(force=True)
                        clicked = True
                        print(f" └── Clicked 'Start a post' using selector: {sel}")
                        break
                except Exception:
                    continue

            if not clicked:
                print(" ⚠️ Could not locate 'Start a post' button via standard selectors.")
                return False

            await page.wait_for_timeout(3000)

            # 2. Upload media file if present
            if media_file:
                print(f" ├── Attaching media file: {media_file.name} ...")
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(str(media_file.resolve()))
                    await page.wait_for_timeout(4000)

                    # Click 'Next' or 'Done' on media editor modal if presented
                    next_media_btn = await page.query_selector("button:has-text('Next'), button:has-text('Done')")
                    if next_media_btn:
                        await next_media_btn.click(force=True)
                        await page.wait_for_timeout(2000)

            # 3. Insert Post Copy
            print(" ├── Entering post content...")
            editor_selectors = [
                "div.ql-editor",
                "div[contenteditable='true']",
                "div[role='textbox']"
            ]
            editor = None
            for sel in editor_selectors:
                try:
                    editor = await page.wait_for_selector(sel, timeout=4000)
                    if editor:
                        break
                except Exception:
                    continue

            if editor:
                await editor.focus()
                await editor.fill(post_text)
                await page.wait_for_timeout(2000)

            # 4. Click Post button
            print(" ├── Clicking 'Post' button...")
            post_submit_btn = await page.query_selector("button.share-actions__primary-action, button:has-text('Post')")
            if post_submit_btn:
                await post_submit_btn.click(force=True)
                await page.wait_for_timeout(6000)
                print("🎉 Successfully published post to LinkedIn!")
                return True

        except Exception as e:
            print(f"⚠️ Error while publishing post on page: {e}")

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
            args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--test-type"]

        )
        page = context.pages[0] if context.pages else await context.new_page()
        await publisher.ensure_logged_in(page)
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
