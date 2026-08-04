import os
import time
from typing import List, Optional, Dict, Set
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import random
import asyncio

load_dotenv()

_PERMANENT_FAIL_CODES = {400, 401, 403}
_RATE_LIMIT_CODES = {429, 500, 503}
_LAST_GLOBAL_REQUEST_TIME = 0.0

class GeminiAIClient:
    def __init__(self):
        keys = []
        if os.getenv("GEMINI_API_KEY"):
            keys.append(os.getenv("GEMINI_API_KEY"))
        for i in range(1, 15):
            k = os.getenv(f"GEMINI_API_KEY_{i}")
            if k and k not in keys:
                keys.append(k)

        self.api_keys: List[str] = keys
        self.current_key_idx: int = 0
        self.dead_keys: Set[str] = set()
        self.last_used_time: Dict[str, float] = {k: 0.0 for k in self.api_keys}
        self.response_cache: Dict[str, str] = {}

        if self.api_keys:
            print(f"🔑 Gemini AI Client initialized with {len(self.api_keys)} API keys.")
        else:
            print("⚠️ No GEMINI_API_KEY found. Using fallback.")

    def _get_active_key(self) -> Optional[str]:
        live_keys = [k for k in self.api_keys if k not in self.dead_keys]
        if not live_keys:
            return None
        for offset in range(len(self.api_keys)):
            idx = (self.current_key_idx + offset) % len(self.api_keys)
            k = self.api_keys[idx]
            if k not in self.dead_keys:
                self.current_key_idx = idx
                return k
        return None

    def _rotate_key(self, reason: str = "success"):
        if self.api_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            live = len(self.api_keys) - len(self.dead_keys)
            print(f"🔄 Rotated Gemini key → Key #{self.current_key_idx + 1} ({live} live) [{reason}]")

    def _blacklist_key(self, key: str):
        if key not in self.dead_keys:
            self.dead_keys.add(key)
            masked = f"{key[:8]}...{key[-4:]}"
            live = len(self.api_keys) - len(self.dead_keys)
            print(f"🚫 Gemini key blacklisted: {masked} ({live} live keys remaining)")

    async def generate_content_web(self, prompt: str, page) -> Optional[str]:
        """Automates the Gemini Web Interface (gemini.google.com) to generate response."""
        context = page.context
        
        # 1. Search for existing Gemini tab in active context
        gemini_page = None
        for p in context.pages:
            try:
                if "gemini.google.com" in p.url:
                    gemini_page = p
                    break
            except Exception:
                pass

        if not gemini_page:
            print("🌐 [GEMINI WEB] Opening Web Gemini tab (gemini.google.com)...")
            gemini_page = await context.new_page()
            await gemini_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            await asyncio.sleep(4)

        # 2. Check Login Status
        signin_button = await gemini_page.query_selector("a[href*='accounts.google.com'], button:has-text('Sign in'), a:has-text('Sign in')")
        if signin_button:
            print("\n⚠️ [ACTION REQUIRED] Please log in to Google on the opened Chrome window to use Gemini Web.")
            # Pause and wait for login (up to 45 seconds)
            for wait_idx in range(15):
                await asyncio.sleep(3)
                editor = await gemini_page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
                if editor:
                    break
            else:
                print("❌ [GEMINI WEB] Login check timed out. Falling back to API keys.")
                return None

        # 3. Find input textbox
        editor = await gemini_page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
        if not editor:
            print("❌ [GEMINI WEB] Could not locate prompt textbox editor. Falling back to API keys.")
            return None

        # 4. Count existing model responses before submitting
        prev_responses = await gemini_page.query_selector_all("model-response")
        prev_count = len(prev_responses)

        # 5. Input prompt and Send
        print("🌐 [GEMINI WEB] Typing prompt into Web Gemini interface...")
        await editor.focus()
        await editor.fill(prompt)
        await asyncio.sleep(1.0)

        send_btn = await gemini_page.query_selector("button[aria-label*='Send'], button[aria-label*='submit']")
        if send_btn:
            await send_btn.click()
        else:
            await gemini_page.keyboard.press("Enter")

        # 6. Wait for stream completion (monitor text length stability)
        print("🌐 [GEMINI WEB] Waiting for reply generation to finish streaming...")
        await asyncio.sleep(3.0)
        
        response_text = ""
        last_len = 0
        stable_checks = 0
        
        for check in range(30):
            await asyncio.sleep(1.5)
            responses = await gemini_page.query_selector_all("model-response")
            if len(responses) > prev_count:
                last_resp = responses[-1]
                
                # Try finding markdown body or raw text
                md_body = await last_resp.query_selector(".markdown, .model-response-text, message-content")
                if md_body:
                    current_text = (await md_body.inner_text()).strip()
                else:
                    current_text = (await last_resp.inner_text()).strip()

                if len(current_text) > 0 and len(current_text) == last_len:
                    stable_checks += 1
                    if stable_checks >= 2: # Stable for 3.0 seconds
                        response_text = current_text
                        break
                else:
                    stable_checks = 0
                    last_len = len(current_text)

        if response_text:
            print(f"🌐 [GEMINI WEB] Successfully fetched response! (Length: {len(response_text)})")
            return response_text
        
        print("❌ [GEMINI WEB] Response streaming timeout. Falling back to API keys.")
        return None

    async def generate_content(self, prompt: str, system_instruction: str = "", page=None) -> Optional[str]:
        cache_key = f"{system_instruction}\n\n{prompt}".strip()
        if cache_key in self.response_cache:
            print("💾 [CACHE HIT] Returning cached AI response.")
            return self.response_cache[cache_key]

        # 1. Try Web Interface fallback if page is available
        if page:
            try:
                web_res = await self.generate_content_web(prompt, page)
                if web_res:
                    self.response_cache[cache_key] = web_res
                    return web_res
            except Exception as e:
                print(f"⚠️ Web Gemini failed ({type(e).__name__}). Falling back to API Keys rotation...")

        if not self.api_keys:
            return None

        live_keys = [k for k in self.api_keys if k not in self.dead_keys]
        if not live_keys:
            return None

        MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        BACKOFF_WAITS = [60, 120, 300]
        rate_limited_keys = set()

        for round_idx in range(3):
            active_key = self._get_active_key()
            if not active_key:
                break

            total_live = len(self.api_keys) - len(self.dead_keys)

            for _ in range(total_live):
                active_key = self._get_active_key()
                if not active_key:
                    break

                for model_name in MODELS:
                    global _LAST_GLOBAL_REQUEST_TIME
                    now = time.time()
                    global_elapsed = now - _LAST_GLOBAL_REQUEST_TIME
                    if global_elapsed < 2.0:
                        wait_sec = 2.0 - global_elapsed
                        print(f"⏳ Global throttle... waiting {wait_sec:.1f}s")
                        await asyncio.sleep(wait_sec)

                    elapsed = now - self.last_used_time.get(active_key, 0.0)
                    if elapsed < 4.1:
                        wait_sec = 4.1 - elapsed
                        masked = f"{active_key[:8]}...{active_key[-4:]}"
                        print(f"⏳ Pacing request for key {masked}... waiting {wait_sec:.1f}s")
                        await asyncio.sleep(wait_sec)

                    _LAST_GLOBAL_REQUEST_TIME = time.time()
                    self.last_used_time[active_key] = time.time()

                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={active_key}"
                    payload = {"contents": [{"parts": [{"text": cache_key}]}]}

                    try:
                        data = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as response:
                            result = json.loads(response.read().decode("utf-8"))
                            candidates = result.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts and "text" in parts[0]:
                                    text = parts[0]["text"].strip()
                                    self._rotate_key(reason=f"{model_name} success")
                                    self.response_cache[cache_key] = text
                                    return text

                    except urllib.error.HTTPError as e:
                        status = e.code
                        if status in _PERMANENT_FAIL_CODES:
                            self._blacklist_key(active_key)
                            break
                        elif status in _RATE_LIMIT_CODES:
                            masked = f"{active_key[:8]}...{active_key[-4:]}"
                            print(f"⏳ Rate-limit ({status}) on key {masked} — rotating key...")
                            rate_limited_keys.add(active_key)
                            break
                        else:
                            print(f"⚠️ HTTP {status} on model {model_name} — trying next model...")

                    except Exception as e:
                        print(f"⚠️ Request error on model {model_name}: {type(e).__name__}")

                    self._rotate_key(reason="trying next key")

            live_non_limited = [k for k in self.api_keys if k not in self.dead_keys and k not in rate_limited_keys]
            if not live_non_limited and round_idx < 2:
                wait_sec = BACKOFF_WAITS[round_idx]
                print(f"⏳ All live keys rate-limited. Waiting {wait_sec}s...")
                await asyncio.sleep(wait_sec)
                rate_limited_keys.clear()

        print("⚠️ All Gemini key rotation rounds exhausted — using fallback.")
        return None

    async def generate_feed_comment(self, post_text: str, author_name: str = "Author", media_desc: str = "", page=None) -> str:
        media_info = f"\nAttached Media: {media_desc}" if media_desc else ""
        prompt = f"""You are Karanbir Singh, a Demand Planning & Supply Chain Specialist.
Write an authentic 2-sentence LinkedIn comment for this post by {author_name}.

Post:
\"\"\"{post_text}\"\"\"
{media_info}

Requirements: Address specific concepts, share practical insight, NO generic fluff. Return ONLY the comment."""

        result = await self.generate_content(prompt, page=page)
        if result:
            return result

        text_lower = (post_text + " " + media_desc).lower()
        if "supply chain" in text_lower or "logistics" in text_lower:
            templates = [
                "Real-world disruptions highlight exact lead-time vulnerabilities that static forecasts miss.",
                "Proactive inventory positioning and multi-echelon demand forecasting make all the difference."
            ]
        else:
            templates = [
                "Great point. Balancing strategic foresight with operational execution turns ideas into scalable results.",
                "A very relevant perspective. Continuous optimization and data-driven decisions are vital today."
            ]
        return random.choice(templates)

    async def generate_notification_reply(self, notification_text: str, parent_comment: str = "", page=None) -> str:
        prompt = f"""You are a senior tech professional replying to a notification.

Notification: {notification_text}
Context: {parent_comment}

Write a friendly 1-2 sentence response. Return ONLY the reply."""
        result = await self.generate_content(prompt, page=page)
        if result:
            return result
        return random.choice([
            "Appreciate the feedback! Spot on regarding the implementation tradeoffs.",
            "Thanks for sharing your input! Balancing speed with architectural clarity is key."
        ])

    async def generate_inbox_reply(self, chat_history: str, partner_name: str = "Connection", page=None) -> str:
        prompt = f"""You are Karanbir Singh, a software engineer & AI tech lead. Reply to this conversation with {partner_name}.

History:
\"\"\"{chat_history}\"\"\"

Write a warm, concise, professional reply (1-2 sentences). Return ONLY the reply."""
        result = await self.generate_content(prompt, page=page)
        if result:
            return result
        return random.choice([
            "Thanks for reaching out! Looking forward to keeping in touch.",
            "Appreciate the message! Hope everything is going great on your end."
        ])
