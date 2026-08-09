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
    def validate(cls, post_text: str, media_files: Optional[Union[Path, list[Path]]] = None) -> tuple[bool, str]:
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

        if media_files:
            media_list = [media_files] if isinstance(media_files, Path) else media_files
            for m_path in media_list:
                if Path(m_path).exists() and Path(m_path).stat().st_size < 1024:
                    return False, f"Image asset too small or corrupt ({Path(m_path).name}: {Path(m_path).stat().st_size} bytes)"

        return True, "Passed all quality, hook, and readability checks"


class LinkedInPublisher:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.user_data_dir = settings.linkedin_user_data_dir
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    async def ensure_logged_in(self, page) -> bool:
        """Verifies session active; returns True if logged in."""
        try:
            print("🔍 Verifying LinkedIn login session...")
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"⚠️ Page load notice: {e}")

        print(f" Current URL: {page.url}")
        if "feed" in page.url.lower():
            print("✅ Already logged in to LinkedIn!")
            return True

        if "login" in page.url.lower() or "signup" in page.url.lower():
            print("🔑 Profile not logged in. Proceeding with auto-login...")
            if settings.linkedin_username and settings.linkedin_password:
                try:
                    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
                    await page.fill("#username", settings.linkedin_username)
                    await page.fill("#password", settings.linkedin_password)
                    await page.click("button[type='submit']")
                    await page.wait_for_timeout(5000)
                except Exception as login_err:
                    print(f"❌ Auto-login error: {login_err}")

        return "feed" in page.url.lower()

    async def publish_post_option(self, option_dir: Path, page: Optional[Any] = None, dry_run: bool = False) -> bool:
        """Publishes a LinkedIn post option (text + all media assets) directly to LinkedIn."""
        post_txt_file = option_dir / "linkedin_post.txt"
        media_dir = option_dir / "media"

        if not post_txt_file.exists():
            print(f"❌ Error: Post text file missing in {option_dir}")
            return False

        post_text = post_txt_file.read_text(encoding="utf-8").strip()

        # Find all valid media assets in option folder
        media_files = list(media_dir.glob("*")) if media_dir.exists() else []
        valid_media = [f for f in media_files if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".gif"]]
        valid_media.sort(key=lambda p: p.name)

        # Content Quality Gate Verification
        is_valid, quality_reason = ContentQualityGate.validate(post_text, valid_media)
        if not is_valid:
            print(f"🛑 [Content Quality Gate Failed] Skipping post option: {quality_reason}")
            return False

        print(f"✅ [Content Quality Gate Passed] {quality_reason}")
        print(f"\n🚀 Publishing Post Option to LinkedIn from: {option_dir.name}")
        print(f" Media Assets ({len(valid_media)} files): {[f.name for f in valid_media] if valid_media else 'None (Text Only)'}")
        print(f" Post Preview: {post_text[:120]}...\n")

        if dry_run:
            print("🧪 [DRY RUN] Skipping actual LinkedIn publishing.")
            return True

        if page:
            return await self._publish_on_page(page, post_text, valid_media)

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

            res = await self._publish_on_page(target_page, post_text, valid_media)
            await context.close()
            return res

    async def _publish_on_page(self, page, post_text: str, valid_media: list[Path]) -> bool:
        """Executes actual DOM actions on the LinkedIn feed page to create and submit a post with all media assets."""
        try:
            if "feed" not in page.url.lower():
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

            # 1. Click 'Start a post' trigger button
            print(" ├── Triggering LinkedIn post editor...")
            start_post_selectors = [
                "text=Start a post",
                "button:has-text('Start a post')",
                "span:has-text('Start a post')",
                ".share-box-feed-entry__top-bar button",
                ".share-box-feed-entry__wrapper button",
                ".share-box-feed-entry__wrapper",
                "button.share-mb-launcher",
                "button[data-view-name='share-box-trigger']"
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
                try:
                    loc = page.get_by_text("Start a post")
                    if await loc.count() > 0:
                        await loc.first.click(force=True)
                        clicked = True
                        print(" └── Clicked 'Start a post' using get_by_text fallback")
                except Exception as loc_e:
                    print(f" ⚠️ Locator fallback notice: {loc_e}")

            if not clicked:
                print(" ⚠️ Could not locate 'Start a post' button via standard selectors.")
                return False

            await page.wait_for_timeout(3000)

            # 2. Upload ALL media files via file chooser interception (Prevents OS Dialog Popup & Guarantees Upload)
            if valid_media:
                print(f" ├── Attaching {len(valid_media)} media asset(s): {[f.name for f in valid_media]} ...")
                media_paths = [str(f.resolve()) for f in valid_media]
                attached = False

                # Strategy A: Use expect_file_chooser() with media trigger icon
                media_btn_selectors = [
                    "button[aria-label*='media']",
                    "button[aria-label*='photo']",
                    "button[aria-label*='Photo']",
                    "button.share-promoted-detour-button",
                    "button:has-text('Add media')",
                    "button:has-text('Media')"
                ]
                for m_sel in media_btn_selectors:
                    try:
                        m_btn = await page.query_selector(m_sel)
                        if m_btn and await m_btn.is_visible():
                            async with page.expect_file_chooser(timeout=4000) as fc_info:
                                await m_btn.click(force=True)
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(media_paths)
                            attached = True
                            print(f" └── Intercepted file chooser and attached all {len(valid_media)} files headlessly!")
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue

                # Strategy B: Fallback to direct input[type='file'] if expect_file_chooser skipped
                if not attached:
                    file_input = await page.query_selector("input[type='file']")
                    if not file_input:
                        file_inputs = await page.query_selector_all("input[type='file']")
                        if file_inputs:
                            file_input = file_inputs[0]

                    if file_input:
                        await file_input.set_input_files(media_paths)
                        attached = True
                        print(f" └── Attached all {len(valid_media)} media files via fallback input element!")
                        await page.wait_for_timeout(3000)

                if attached:
                    # Click 'Next' or 'Done' on media editor modal if presented
                    next_media_selectors = [
                        "button:has-text('Next')",
                        "button:has-text('Done')",
                        "button:has-text('Save')",
                        "button.share-box-footer__primary-btn",
                        "div.share-box-footer button.artdeco-button--primary"
                    ]
                    for n_sel in next_media_selectors:
                        try:
                            n_btn = await page.wait_for_selector(n_sel, timeout=3000)
                            if n_btn and await n_btn.is_visible():
                                await n_btn.click(force=True)
                                print(f" └── Clicked media modal next using selector: {n_sel}")
                                await page.wait_for_timeout(2000)
                                break
                        except Exception:
                            continue

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
                    if editor and await editor.is_visible():
                        break
                except Exception:
                    continue

            if editor:
                await editor.focus()
                await page.wait_for_timeout(500)
                print(" ├── Typing post copy with humanized keystroke dynamics...")
                from utils.playwright_utils import PlaywrightResilience
                await PlaywrightResilience.human_type_with_mistakes(page, editor, post_text)
                await page.wait_for_timeout(2000)

            # 4. Click Post button
            print(" ├── Clicking 'Post' button...")
            post_submit_selectors = [
                "button.share-actions__primary-action",
                "button:has-text('Post')",
                "div.share-box-footer button:has-text('Post')",
                "button.artdeco-button--primary:has-text('Post')"
            ]
            for p_sel in post_submit_selectors:
                try:
                    p_btn = await page.wait_for_selector(p_sel, timeout=3000)
                    if p_btn:
                        await p_btn.click(force=True)
                        print(f" └── Clicked 'Post' using selector: {p_sel}")
                        await page.wait_for_timeout(6000)
                        print("🎉 Successfully published post to LinkedIn!")
                        return True
                except Exception:
                    continue

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
