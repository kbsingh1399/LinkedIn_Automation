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

    @staticmethod
    def is_company_name(name: str) -> bool:
        """Check if author or profile name belongs to a company/brand rather than an individual."""
        import re
        if not name:
            return False
        corporate_indicators = [
            r'\b(inc|corp|ltd|llc|pvt|limited|gmbh|plc|co\.|company|group|solutions|technologies|consulting|services|enterprises|global|international)\b',
            r'\b(tech|labs|digital|software|systems|networks|media|agency|capital|ventures|partners|associates|holdings|foundation)\b'
        ]
        name_lower = name.lower().strip()
        for pattern in corporate_indicators:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return True
        if len(name_lower.split()) >= 4:
            return True
        return False

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

    # Adjacent QWERTY neighbors — typos replace the target with one of these, never a random letter.
    ADJACENT_KEYS = {
        "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "ersfcx",
        "e": "wrsd", "f": "rtgdcv", "g": "tyhfvb", "h": "yujgbn",
        "i": "uojk", "j": "uikhnm", "k": "ijolm", "l": "kop",
        "m": "njk", "n": "bhjm", "o": "iplk", "p": "ol",
        "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
        "u": "yhji", "v": "cfgb", "w": "qeas", "x": "zsdc",
        "y": "tghu", "z": "asx",
        "1": "2q", "2": "13w", "3": "24e", "4": "35r",
        "5": "46t", "6": "57y", "7": "68u", "8": "79i",
        "9": "80o", "0": "9p",
    }

    COMMENT_EDITOR_SELECTOR = (
        "div[aria-label='Text editor for creating comment'], "
        "div.comments-comment-box div[contenteditable='true'], "
        "div.tiptap.ProseMirror, "
        "div[aria-label*='comment' i], "
        "div[contenteditable='true'][role='textbox']"
    )

    ALLOWED_CARD_TAGS = {"ARTICLE", "DIV", "LI", "SECTION", "A"}

    @staticmethod
    async def human_type_with_mistakes(page: Page, element, text: str):
        """
        Skill-accurate human typing:
          - 25-65ms per key
          - <=1.5% typo rate, max 2 typos, adjacent QWERTY only, then backspace-correct
          - 4% of spaces pause 0.5s-1.2s
        """
        try:
            await page.bring_to_front()
        except Exception:
            pass
        await element.focus()
        await asyncio.sleep(random.uniform(0.3, 0.6))

        typos_done = 0
        for char in text:
            if (
                char.isalnum()
                and typos_done < 2
                and random.random() < 0.015
            ):
                neighbors = PlaywrightResilience.ADJACENT_KEYS.get(char.lower(), "")
                if neighbors:
                    wrong = random.choice(neighbors)
                    if char.isupper():
                        wrong = wrong.upper()
                    await element.type(wrong, delay=random.randint(25, 65))
                    await asyncio.sleep(random.uniform(0.12, 0.32))
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.05, 0.16))
                    typos_done += 1

            await element.type(char, delay=random.randint(25, 65))
            if char == " " and random.random() < 0.04:
                await asyncio.sleep(random.uniform(0.5, 1.2))

        await asyncio.sleep(random.uniform(0.3, 0.6))

    @staticmethod
    async def find_last_visible_editor(page: Page, timeout_ms: int = 4000):
        """
        Body-level editor lookup. LinkedIn injects TipTap comment boxes at <body>,
        outside the post card. Always take the LAST visible editor (nested reply).
        """
        try:
            await page.bring_to_front()
        except Exception:
            pass
        locators = page.locator(PlaywrightResilience.COMMENT_EDITOR_SELECTOR)
        try:
            await locators.last.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            pass
        try:
            count = await locators.count()
        except Exception:
            return None
        for i in range(count - 1, -1, -1):
            el = locators.nth(i)
            try:
                if await el.is_visible():
                    return await el.element_handle()
            except Exception:
                continue
        return None

    @staticmethod
    async def is_html_element_card(card) -> bool:
        """Filter SVG/text nodes from broad class selectors (notification cards)."""
        try:
            tag = await card.evaluate("el => el && el.tagName ? el.tagName : ''")
            return bool(tag) and str(tag).upper() in PlaywrightResilience.ALLOWED_CARD_TAGS
        except Exception:
            return False

    @staticmethod
    async def safe_mouse_move(page: Page, target_x: int, target_y: int):
        """Safely moves mouse cursor to target coordinates with viewport safety bounds."""
        try:
            viewport = page.viewport_size or {"width": 1440, "height": 900}
            safe_x = max(10, min(int(target_x), viewport["width"] - 10))
            safe_y = max(10, min(int(target_y), viewport["height"] - 10))
            await page.mouse.move(safe_x, safe_y)
        except Exception:
            pass

    @staticmethod
    async def random_mouse_jitter(page: Page):
        """Simulates natural idle mouse cursor jittering across viewport."""
        try:
            viewport = page.viewport_size or {"width": 1440, "height": 900}
            target_x = random.randint(100, viewport["width"] - 100)
            target_y = random.randint(100, viewport["height"] - 100)
            await PlaywrightResilience.safe_mouse_move(page, target_x, target_y)
        except Exception:
            pass

    @staticmethod
    async def smooth_mouse_move(page: Page, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 18):
        for i in range(1, steps + 1):
            t = i / steps
            x = start_x + (end_x - start_x) * (3 * t**2 - 2 * t**3) + random.uniform(-3, 3)
            y = start_y + (end_y - start_y) * (3 * t**2 - 2 * t**3) + random.uniform(-3, 3)
            await PlaywrightResilience.safe_mouse_move(page, int(x), int(y))
            await asyncio.sleep(random.uniform(0.008, 0.025))

    @staticmethod
    async def human_scroll(page: Page, total_distance: int = 600):
        """
        Simulates realistic human scrolling:
        1. Breaks total distance into 3-6 organic micro-scroll bursts with ease-in-out curve.
        2. Moves mouse cursor smoothly across viewport during scroll.
        3. 20% chance of mid-scroll reading pause (1.2s - 3.5s).
        4. 25% chance of slight reverse scroll up (-80px to -220px) to re-read.
        """
        try:
            viewport = page.viewport_size or {"width": 1280, "height": 850}
            center_x = viewport["width"] // 2
            
            # Micro-move mouse cursor near center of feed
            mouse_target_x = center_x + random.randint(-150, 150)
            mouse_target_y = random.randint(300, 600)
            await page.mouse.move(mouse_target_x, mouse_target_y)

            # Split total distance into variable micro-bursts
            num_bursts = random.randint(3, 6)
            remaining = total_distance
            
            for burst_idx in range(num_bursts):
                if remaining <= 0:
                    break
                
                # Ease-in-out distance calculation per burst
                step = int((remaining / (num_bursts - burst_idx)) * random.uniform(0.7, 1.3))
                step = max(50, min(step, 280))
                
                # Perform wheel scroll with micro-delay
                await page.mouse.wheel(0, step)
                remaining -= step
                await asyncio.sleep(random.uniform(0.12, 0.35))
                
                # 20% chance of mid-scroll reading pause
                if random.random() < 0.20:
                    await asyncio.sleep(random.uniform(1.2, 3.2))

            # 25% chance of slight reverse scroll up (human re-reading behavior)
            if random.random() < 0.25:
                reverse_dist = random.randint(-220, -80)
                await page.mouse.wheel(0, reverse_dist)
                await asyncio.sleep(random.uniform(0.6, 1.4))
        except Exception:
            pass

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
        """No-op: stealth skill forbids a Playwright-fixed viewport."""
        return

    @staticmethod
    async def dismiss_blocking_overlays(page: Page) -> bool:
        """Finds and dismisses actual modal overlays or toast popups that intercept pointer events."""
        overlay_selectors = [
            "button.artdeco-modal__dismiss",
            "div.artdeco-modal button[aria-label*='Dismiss' i]",
            "div.artdeco-modal button[aria-label*='Close' i]",
            "button.artdeco-toast-item__dismiss"
        ]
        dismissed = False
        for sel in overlay_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click(force=True)
                    print(f"🛡️ [Safety Gate] Dismissed modal overlay: {sel}")
                    dismissed = True
                    await asyncio.sleep(0.5)
            except Exception:
                pass
        return dismissed

    @staticmethod
    async def verify_security_checkpoint(page: Page) -> bool:
        """Detects if LinkedIn triggered a security checkpoint or CAPTCHA page."""
        try:
            url_lower = page.url.lower()
            if "checkpoint" in url_lower or "challenge" in url_lower or "captcha" in url_lower:
                print("🚨 [Security Gate] LinkedIn Security Checkpoint / CAPTCHA detected!")
                print("   Execution paused to protect your account. Please solve the security check manually in Chrome.")
                return True
            checkpoint_heading = await page.query_selector("h1:has-text('Security Check'), h1:has-text('Verify it'), div:has-text('security check')")
            if checkpoint_heading:
                print("🚨 [Security Gate] LinkedIn Security Checkpoint heading detected!")
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def get(key: str) -> List[str]:
        return PlaywrightResilience.SELECTORS.get(key, [])

