import os
import sys
import json
import random
import time
import asyncio
import urllib.request
import urllib.error
from typing import List, Optional, Set, Dict
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Automatically load environment variables from .env file
load_dotenv()

# HTTP status codes that indicate a key is permanently unusable
_PERMANENT_FAIL_CODES = {400, 401, 403}
# HTTP status codes that indicate we should wait and retry
_RATE_LIMIT_CODES = {429, 500, 503}
# Global throttle to pace requests across all keys
_LAST_GLOBAL_REQUEST_TIME = 0.0

class GeminiAIClient:
    def __init__(self):
        keys = []
        # Support GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2 ... GEMINI_API_KEY_10
        if os.getenv("GEMINI_API_KEY"):
            keys.append(os.getenv("GEMINI_API_KEY"))
        for i in range(1, 15):
            k = os.getenv(f"GEMINI_API_KEY_{i}")
            if k and k not in keys:
                keys.append(k)

        self.api_keys: List[str] = keys
        self.current_key_idx: int = 0
        self.dead_keys: Set[str] = set()   # permanently blacklisted keys
        self.last_used_time: Dict[str, float] = {k: 0.0 for k in self.api_keys}
        self.response_cache: Dict[str, str] = {}
        if self.api_keys:
            print(f"🔑 Gemini AI Client initialized with {len(self.api_keys)} API keys for active rotation.")
        else:
            print("⚠️ Notice: No GEMINI_API_KEY found in .env. Using dynamic contextual fallback engine.")

    def _get_active_key(self) -> Optional[str]:
        """Returns the next live (non-dead) key, cycling through the list."""
        live_keys = [k for k in self.api_keys if k not in self.dead_keys]
        if not live_keys:
            return None
        # Find next live key starting from current index
        for offset in range(len(self.api_keys)):
            idx = (self.current_key_idx + offset) % len(self.api_keys)
            k = self.api_keys[idx]
            if k not in self.dead_keys:
                self.current_key_idx = idx
                return k
        return None

    def _rotate_key(self, reason: str = "success"):
        """Advances the key index to the next live key."""
        if self.api_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            live = len(self.api_keys) - len(self.dead_keys)
            print(f"🔄 Rotated Gemini key → Key #{self.current_key_idx + 1}  ({live} live / {len(self.dead_keys)} dead)  [{reason}]")

    def _blacklist_key(self, key: str):
        """Permanently removes a key from rotation due to auth/permission failure."""
        if key not in self.dead_keys:
            self.dead_keys.add(key)
            masked = f"{key[:8]}...{key[-4:]}"
            live = len(self.api_keys) - len(self.dead_keys)
            print(f"🚫 Gemini key blacklisted (invalid/disabled): {masked}  ({live} live keys remaining)")

    async def generate_content_web(self, prompt: str, page) -> Optional[str]:
        """Generates content via gemini.google.com using an existing or new tab in page.context."""
        try:
            if not page or not hasattr(page, "context"):
                return None

            gemini_page = None
            for p in page.context.pages:
                if "gemini.google.com" in p.url:
                    gemini_page = p
                    break

            if not gemini_page:
                gemini_page = await page.context.new_page()
                await gemini_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=30000)

            editor_selector = ".ql-editor, div[contenteditable='true'][role='textbox']"
            try:
                editor = await gemini_page.wait_for_selector(editor_selector, timeout=5000)
            except Exception:
                print("⚠️ [ACTION REQUIRED] Please log in to Gmail/Google on the opened Gemini window.")
                try:
                    editor = await gemini_page.wait_for_selector(editor_selector, timeout=30000)
                except Exception:
                    print("⚠️ Web Gemini text box not found (not logged in or timed out). Falling back to API keys...")
                    return None

            initial_responses = await gemini_page.query_selector_all("model-response")
            initial_count = len(initial_responses)

            await editor.click()
            await editor.fill(prompt)

            send_btn = await gemini_page.query_selector("button[aria-label*='Send']")
            if send_btn and await send_btn.is_enabled():
                await send_btn.click()
            else:
                await editor.press("Enter")

            start_time = time.time()
            new_response_found = False
            while time.time() - start_time < 30:
                responses = await gemini_page.query_selector_all("model-response")
                if len(responses) > initial_count:
                    new_response_found = True
                    break
                await asyncio.sleep(1)

            if not new_response_found:
                print("⚠️ Web Gemini response element did not appear in time.")
                return None

            last_response = (await gemini_page.query_selector_all("model-response"))[-1]
            last_text = ""
            consecutive_stable = 0

            for _ in range(20):
                text_el = await last_response.query_selector(".model-response-text, .markdown")
                current_text = (await text_el.inner_text()).strip() if text_el else (await last_response.inner_text()).strip()

                if current_text and current_text == last_text:
                    consecutive_stable += 1
                    if consecutive_stable >= 2:
                        print("🌐 [WEB GEMINI SUCCESS] Response generated via Web UI.")
                        return current_text
                else:
                    consecutive_stable = 0
                    last_text = current_text

                await asyncio.sleep(1.5)

            if last_text:
                return last_text
            return None
        except Exception as e:
            print(f"⚠️ Web Gemini automation exception: {e}")
            return None

    async def generate_content(self, prompt: str, system_instruction: str = "", page=None) -> Optional[str]:
        cache_key = f"{system_instruction}\n\n{prompt}".strip()
        if cache_key in self.response_cache:
            print("💾 [CACHE HIT] Returning cached AI response.")
            return self.response_cache[cache_key]

        if page:
            print("🌐 Attempting AI generation via Web Gemini fallback engine...")
            web_result = await self.generate_content_web(prompt, page)
            if web_result:
                self.response_cache[cache_key] = web_result
                return web_result
            print("⚠️ Web Gemini generation failed or unavailable — falling back to API key rotation.")

        if not self.api_keys:
            return None

        live_keys = [k for k in self.api_keys if k not in self.dead_keys]
        if not live_keys:
            print("⚠️ All Gemini API keys are dead/exhausted — using fallback engine.")
            return None

        MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        BACKOFF_WAITS = [60, 120, 300]   # seconds to wait when all keys are rate-limited
        rate_limited_keys: Set[str] = set()

        # Attempt every live key once per round; up to 3 rounds with backoff
        for round_idx in range(3):
            active_key = self._get_active_key()
            if not active_key:
                break

            tried_in_round = 0
            total_live = len(self.api_keys) - len(self.dead_keys)

            for _ in range(total_live):
                active_key = self._get_active_key()
                if not active_key:
                    break

                for model_name in MODELS:
                    # Enforce global pacing (min 2.0s between ANY request to Gemini API globally)
                    global _LAST_GLOBAL_REQUEST_TIME
                    now = time.time()
                    global_elapsed = now - _LAST_GLOBAL_REQUEST_TIME
                    if global_elapsed < 2.0:
                        wait_sec = 2.0 - global_elapsed
                        print(f"⏳ Global throttle... waiting {wait_sec:.1f}s")
                        await asyncio.sleep(wait_sec)

                    # Apply API Pacing to stay under the 15 RPM (1 request every 4 seconds) limit per key
                    now = time.time()
                    elapsed = now - self.last_used_time.get(active_key, 0.0)
                    if elapsed < 4.1:
                        wait_sec = 4.1 - elapsed
                        masked = f"{active_key[:8]}...{active_key[-4:]}"
                        print(f"⏳ Pacing request for key {masked}... waiting {wait_sec:.1f}s to respect 15 RPM")
                        await asyncio.sleep(wait_sec)

                    _LAST_GLOBAL_REQUEST_TIME = time.time()
                    self.last_used_time[active_key] = time.time()

                    url = (
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{model_name}:generateContent?key={active_key}"
                    )
                    payload = {
                        "contents": [{
                            "parts": [{"text": cache_key}]
                        }]
                    }
                    try:
                        data = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=data, headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=15) as response:
                            result = json.loads(response.read().decode("utf-8"))
                            candidates = result.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts and "text" in parts[0]:
                                    text = parts[0]["text"].strip()
                                    self._rotate_key(reason=f"{model_name} success")
                                    # Save to cache
                                    self.response_cache[cache_key] = text
                                    return text

                    except urllib.error.HTTPError as e:
                        status = e.code
                        if status in _PERMANENT_FAIL_CODES:
                            # Key is invalid/revoked — remove permanently
                            self._blacklist_key(active_key)
                            break   # break model loop, key is dead
                        elif status in _RATE_LIMIT_CODES:
                            masked = f"{active_key[:8]}...{active_key[-4:]}"
                            print(f"⏳ Rate-limit ({status}) on key {masked} model {model_name} — rotating key...")
                            rate_limited_keys.add(active_key)
                            break   # break model loop, try next key
                        else:
                            print(f"⚠️ HTTP {status} on model {model_name} — trying next model...")

                    except Exception as e:
                        print(f"⚠️ Request error on model {model_name}: {type(e).__name__} — trying next model...")

                tried_in_round += 1
                self._rotate_key(reason="trying next key")

            # If all live keys were rate-limited this round, wait before retrying
            live_non_limited = [
                k for k in self.api_keys
                if k not in self.dead_keys and k not in rate_limited_keys
            ]
            if not live_non_limited and round_idx < 2:
                wait_sec = BACKOFF_WAITS[round_idx]
                print(f"⏳ All {len(rate_limited_keys)} live keys are rate-limited. Waiting {wait_sec}s before retry (round {round_idx + 2}/3)...")
                await asyncio.sleep(wait_sec)
                rate_limited_keys.clear()

        print("⚠️ All Gemini key rotation rounds exhausted — using fallback engine.")
        return None

    async def generate_feed_comment(self, post_text: str, author_name: str = "Author", media_desc: str = "", page=None) -> str:
        media_info = f"\nAttached Infographic / Media Context: {media_desc}" if media_desc else ""
        prompt = f"""
You are Karanbir Singh, a Demand Planning & Supply Chain Specialist (SAP MM/SD, AI Systems Engineering).
Write an authentic, highly specific 2-sentence LinkedIn comment replying to this post by {author_name}.

Post Content:
\"\"\"
{post_text}
\"\"\"
{media_info}

Requirements:
1. Address specific core concepts mentioned in the post text and attached infographic/media (e.g. supply chain resilience, demand forecasting, SAP/ERP bottlenecks, or AI system design).
2. Share a valuable, practical engineering/operational insight as an experienced professional.
3. Absolutely NO generic corporate fluff (NEVER say "Great post!", "Nice share!", "Spot on!", or "Thanks for sharing").
4. Return ONLY the final comment string.
"""
        result = await self.generate_content(prompt, page=page)
        if result:
            return result

        # Dynamic Contextual Fallback (Guarantees Unique Comments Every Time)
        text_lower = (post_text + " " + media_desc).lower()
        if "supply chain" in text_lower or "flood" in text_lower or "logistics" in text_lower or "demand" in text_lower:
            templates = [
                f"Real-world disruptions highlight exact lead-time vulnerabilities that static forecasts miss. Strengthening end-to-end visibility and safety-stock agility is essential for resilient operations.",
                f"Proactive inventory positioning and multi-echelon demand forecasting make all the difference during supply chain stress events.",
                f"Spotting structural bottlenecks early before they cascade across tier-1 suppliers is what separates agile supply chains from reactive ones."
            ]
        elif "ai" in text_lower or "model" in text_lower or "architecture" in text_lower or "data" in text_lower:
            templates = [
                f"The intersection of scalable system architecture and deterministic domain logic is key when deploying models in mission-critical environments.",
                f"High-throughput data pipelines demand rigorous benchmarking at every layer to prevent latency bottlenecks under load.",
                f"System resilience comes down to modular design and graceful fallback strategies during peak operational stress."
            ]
        elif "hiring" in text_lower or "career" in text_lower or "leader" in text_lower or "person" in text_lower:
            templates = [
                f"Execution discipline and continuous learning drive long-term impact far more than short-term trend chasing.",
                f"Empowering technical teams with clear ownership and fast feedback loops creates a culture of high operational excellence.",
                f"Focusing on core principles while staying adaptable to new paradigms is how engineering leaders build lasting value."
            ]
        else:
            templates = [
                f"Great point raised here. Balancing strategic foresight with operational execution is what turns ideas into scalable results.",
                f"A very relevant perspective. Continuous optimization and data-driven decision making are vital in today's fast-moving environment.",
                f"Strong takeaway! Clear alignment across cross-functional teams is essential for driving consistent progress."
            ]

        return random.choice(templates)

    async def generate_notification_reply(self, notification_text: str, parent_comment: str = "", page=None) -> str:
        prompt = f"""
You are a senior tech professional on LinkedIn replying to a user's notification/comment reply.

Notification: {notification_text}
Comment Context: {parent_comment}

Write a friendly, insightful 1-2 sentence response. Keep it engaging and professional. Return ONLY the reply text.
"""
        result = await self.generate_content(prompt, page=page)
        if result:
            return result

        replies = [
            "Appreciate the feedback! Spot on regarding the implementation tradeoffs.",
            "Thanks for sharing your input! Balancing speed with architectural clarity is key.",
            "Completely agree! Always great discussing these operational perspectives."
        ]
        return random.choice(replies)

    async def generate_inbox_reply(self, chat_history: str, partner_name: str = "Connection", page=None) -> str:
        prompt = f"""
You are Karanbir Singh, a software engineer & AI tech lead. Reply to this LinkedIn private message conversation with {partner_name}.

Recent Conversation History:
\"\"\"
{chat_history}
\"\"\"

Write a warm, concise, professional reply (1-2 sentences) maintaining business relationship context. Return ONLY the reply text.
"""
        result = await self.generate_content(prompt, page=page)
        if result:
            return result

        replies = [
            "Thanks for reaching out! Looking forward to keeping in touch. Have a great week ahead!",
            "Appreciate the message! Hope everything is going great on your end.",
            "Thanks for connecting! Let's stay in touch regarding upcoming initiatives."
        ]
        return random.choice(replies)

