"""
Production-Grade Playwright Resilience + Advanced Human Behavior Layer
"""

import asyncio
import random
import logging
from typing import List, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class PlaywrightResilience:
    """Centralized resilience + human behavior utilities."""

    SELECTORS = {
        "comment_box": [
            "div[contenteditable='true'][role='textbox']",
            "div.comments-comment-box-editor div[contenteditable]",
            "div[role='textbox']",
        ],
        "like_button": [
            "button[aria-label*='Like']",
            "button.react-button__trigger",
            "[aria-label*='Like']",
        ],
        "post_submit": [
            "button[aria-label*='Post comment']",
            "button.comments-comment-box__submit-button",
            "button.artdeco-button--primary",
        ],
        "send_button": [
            "button[aria-label*='Send']",
            "button.msg-form__send-button",
            "button:has-text('Send')",
        ],
        "notification_card": ["article.nt-card", "div.notification-item"],
        "message_card": ["li.msg-conversation-listitem", "div.msg-conversation-card"],
    }

    @staticmethod
    async def safe_goto(page: Page, url: str, timeout: int = 45000, retries: int = 3) -> bool:
        for attempt in range(retries):
            try:
                await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                await page.wait_for_timeout(random.randint(800, 1500))
                return True
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return False

    @staticmethod
    async def robust_action(page: Page, action: str, selectors: List[str], text: str = "", timeout: int = 8000) -> bool:
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=timeout, state="visible")
                if not el:
                    continue
                if action == "click":
                    await el.click()
                elif action == "fill" and text:
                    await el.click()
                    await asyncio.sleep(0.2)
                    for char in text:
                        await el.type(char, delay=random.randint(15, 40))
                await page.wait_for_timeout(random.randint(400, 900))
                return True
            except PlaywrightTimeoutError:
                continue
        return False

    @staticmethod
    async def human_type_with_mistakes(page: Page, element, text: str):
        """Types with realistic mistakes and corrections."""
        await element.focus()
        await asyncio.sleep(random.uniform(0.3, 0.7))

        for i, char in enumerate(text):
            if random.random() < 0.08 and i > 3:
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await element.type(wrong_char, delay=random.randint(40, 90))
                await asyncio.sleep(random.uniform(0.4, 0.9))
                for _ in range(random.randint(1, 3)):
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.15, 0.35))
            
            await element.type(char, delay=random.randint(25, 75))
            if random.random() < 0.12:
                await asyncio.sleep(random.uniform(0.6, 1.4))

    @staticmethod
    async def smooth_mouse_move(page: Page, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 18):
        for i in range(1, steps + 1):
            t = i / steps
            x = start_x + (end_x - start_x) * (3 * t**2 - 2 * t**3) + random.uniform(-3, 3)
            y = start_y + (end_y - start_y) * (3 * t**2 - 2 * t**3) + random.uniform(-3, 3)
            try:
                await page.mouse.move(int(x), int(y))
            except:
                pass
            await asyncio.sleep(random.uniform(0.008, 0.025))

    @staticmethod
    async def occasional_reverse_scroll(page: Page, probability: float = 0.25):
        if random.random() < probability:
            await page.mouse.wheel(0, random.randint(-300, -120))
            await page.wait_for_timeout(random.uniform(600, 1400))

    @staticmethod
    async def random_thinking_pause():
        await asyncio.sleep(random.uniform(1.2, 3.8))

    @staticmethod
    async def occasional_page_refresh(page: Page, probability: float = 0.18):
        """Occasionally refreshes the current page (very human behavior)."""
        if random.random() < probability:
            print("🔄 [Human Behavior] Refreshing page...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(random.uniform(2.5, 5.0))
            except:
                pass

    @staticmethod
    async def random_viewport_resize(page: Page, context):
        """Occasionally resizes the viewport slightly."""
        if random.random() < 0.22:
            try:
                current = page.viewport_size or {"width": 1280, "height": 850}
                new_width = current["width"] + random.randint(-120, 120)
                new_height = current["height"] + random.randint(-80, 80)
                new_width = max(1100, min(new_width, 1600))
                new_height = max(700, min(new_height, 1100))
                
                await page.set_viewport_size({"width": new_width, "height": new_height})
                await asyncio.sleep(random.uniform(1.5, 3.5))
            except:
                pass

    @staticmethod
    def get(key: str) -> List[str]:
        return PlaywrightResilience.SELECTORS.get(key, [])
