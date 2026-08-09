import os
import time
import base64
from typing import List, Optional, Dict, Set
from dotenv import load_dotenv
import random
import asyncio

load_dotenv()

class GeminiAIClient:
    # Cache LLM responses for 1 hour per prompt key to prevent unbounded growth
    _CACHE_TTL = 3600

    def __init__(self):
        self._response_cache: Dict[str, tuple] = {}  # key -> (response_text, timestamp)
        print("🌐 Gemini AI Client initialized in Web-Only Mode.")

    def _cache_get(self, key: str) -> Optional[str]:
        entry = self._response_cache.get(key)
        if entry and (time.time() - entry[1]) < self._CACHE_TTL:
            return entry[0]
        if entry:
            del self._response_cache[key]
        return None

    def _cache_set(self, key: str, value: str) -> None:
        self._response_cache[key] = (value, time.time())

    async def automate_google_login(self, page) -> bool:
        print("🌐 [GEMINI WEB] Attempting automated Google Sign-In...")
        try:
            email_input = await page.wait_for_selector('input[type="email"], #identifierId', timeout=15000)
            if not email_input:
                print("❌ [GEMINI WEB] Email input field not found.")
                return False

            await email_input.focus()
            await email_input.fill("gabrumusic.official@gmail.com")
            await asyncio.sleep(1.5)

            next_btn = await page.query_selector('#identifierNext, button:has-text("Next"), button:has-text("Siguiente")')
            if next_btn:
                await next_btn.click()
            else:
                await page.keyboard.press("Enter")
            await asyncio.sleep(4.5)

            password_input = await page.wait_for_selector('input[type="password"], input[name="password"]', timeout=15000)
            if not password_input:
                print("❌ [GEMINI WEB] Password input field not found.")
                return False

            await password_input.focus()
            await password_input.fill("Lu$er2hero")
            await asyncio.sleep(1.5)

            next_pwd_btn = await page.query_selector('#passwordNext, button:has-text("Next"), button:has-text("Siguiente")')
            if next_pwd_btn:
                await next_pwd_btn.click()
            else:
                await page.keyboard.press("Enter")
            await asyncio.sleep(5.0)

            # Wait for redirect or check for security bypass buttons
            for _ in range(10):
                if "gemini.google.com" in page.url:
                    print("✅ [GEMINI WEB] Successfully redirected back to Gemini.")
                    return True
                
                bypass_btn = await page.query_selector('button:has-text("Not now"), button:has-text("Skip"), button:has-text("Confirm")')
                if bypass_btn:
                    try:
                        print("🌐 [GEMINI WEB] Clicking security bypass button...")
                        await bypass_btn.click()
                        await asyncio.sleep(3.0)
                    except:
                        pass
                await asyncio.sleep(2)

            return "gemini.google.com" in page.url
        except Exception as e:
            print(f"❌ [GEMINI WEB] Auto Google login failed: {e}")
            return False

    async def generate_content_web(self, prompt: str, page, image_path: Optional[str] = None) -> Optional[str]:
        """Automates the Gemini Web Interface (gemini.google.com) to generate response."""
        # TTL cache check — avoid duplicate LLM calls for same prompt within 1 hour
        if not image_path:
            cached = self._cache_get(prompt[:200])
            if cached:
                return cached

        context = page.context
        
        # 1. Search for existing Gemini tab in active context
        gemini_page = None
        for p in context.pages:
            try:
                if not p.is_closed() and "gemini.google.com" in p.url:
                    gemini_page = p
                    break
            except Exception:
                pass

        if not gemini_page or gemini_page.is_closed():
            print("🌐 [GEMINI WEB] Opening Web Gemini tab (gemini.google.com)...")
            gemini_page = await context.new_page()
            for _attempt in range(2):
                try:
                    await gemini_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=30000)
                    break
                except Exception:
                    if _attempt == 0:
                        await asyncio.sleep(3)
            try:
                await gemini_page.bring_to_front()
            except Exception:
                pass
            await asyncio.sleep(4)

        # Guard: detect Google's "Couldn't sign you in" bot-detection error page
        blocked_heading = await gemini_page.query_selector("h1:has-text('Couldn'), div:has-text('Couldn\\'t sign you in')")
        if not blocked_heading:
            # Also check by page title / URL pattern
            page_title = await gemini_page.title()
            if "couldn" in page_title.lower() or "sign" in gemini_page.url.lower() and "error" in gemini_page.url.lower():
                blocked_heading = True
        if blocked_heading:
            print("❌ [GEMINI WEB] Google blocked automated login ('Couldn't sign you in').")
            print("   FIX: Open Chrome manually using the persistent profile and log into")
            print("   https://gemini.google.com once — the session will persist for future runs.")
            print("   Profile path:", str(context._impl_obj._options.get("userDataDir", "user_data")))
            return None

        # 2. Check Login Status by searching for prompt textbox editor
        editor = await gemini_page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
        if not editor:
            print("🌐 [GEMINI WEB] Text box not found. Checking if Sign-in is required...")
            signin_button = await gemini_page.query_selector("a[href*='accounts.google.com/ServiceLogin'], a[href*='accounts.google.com/signin'], button:has-text('Sign in'), a:has-text('Sign in'), a[href*='accounts.google.com']")
            if signin_button:
                print("🌐 [GEMINI WEB] Sign-in required. Redirecting to Google Login page...")
                try:
                    async with context.expect_page(timeout=5000) as new_page_info:
                        await signin_button.click()
                    login_page = await new_page_info.value
                    print("🌐 [GEMINI WEB] Login opened in a new tab.")
                except Exception:
                    login_page = gemini_page
                    print("🌐 [GEMINI WEB] Login loading in the same tab.")

                await asyncio.sleep(4.0)

                # Check for bot-detection block on the login page too
                blocked = await login_page.query_selector("h1:has-text('Couldn')")
                if blocked:
                    print("❌ [GEMINI WEB] Google bot-detection triggered on login page.")
                    print("   Please log into gemini.google.com manually in the persistent Chrome profile once.")
                    return None

                success = await self.automate_google_login(login_page)
                if success:
                    gemini_page = login_page
                else:
                    print("\n⚠️ [ACTION REQUIRED] Automated Google login failed. Please log in manually on the opened Chrome window.")
                    for wait_idx in range(15):
                        await asyncio.sleep(3)
                        editor = await gemini_page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
                        if editor:
                            break
                    else:
                        print("❌ [GEMINI WEB] Login check timed out.")
                        return None

        # 3. Find input textbox
        editor = await gemini_page.query_selector(".ql-editor, div[contenteditable='true'][role='textbox']")
        if not editor:
            print("❌ [GEMINI WEB] Could not locate prompt textbox editor.")
            return None

        # 4. Upload image if provided and exists
        if image_path and os.path.exists(image_path):
            try:
                print(f"🌐 [GEMINI WEB] Attaching image: {image_path}...")
                file_attached = False

                # Approach A: Iterate over ALL file inputs in DOM (including shadow DOM)
                file_inputs = await gemini_page.locator("input[type='file']").all()
                for f_input in file_inputs:
                    try:
                        await f_input.set_files(image_path, timeout=3000)
                        await f_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                        file_attached = True
                        print("🌐 [GEMINI WEB] Successfully attached image via file input locator!")
                        await asyncio.sleep(3.5)
                        break
                    except Exception:
                        continue

                # Approach B: Click '+' button, select 'Upload file' menu option, and bind file
                if not file_attached:
                    plus_btn = await gemini_page.query_selector(
                        "button[aria-label*='Add'], "
                        "button[aria-label*='Upload'], "
                        "button[aria-label*='Attach'], "
                        "button[aria-label*='plus'], "
                        "button.uploader-button, "
                        "div[role='button']:has-text('+')"
                    )
                    if plus_btn:
                        try:
                            await plus_btn.click()
                            await asyncio.sleep(0.8)
                            
                            # Find hidden file input exposed after clicking upload menu
                            f_inputs = await gemini_page.locator("input[type='file']").all()
                            for f_in in f_inputs:
                                try:
                                    await f_in.set_files(image_path, timeout=3000)
                                    await f_in.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                                    file_attached = True
                                    print("🌐 [GEMINI WEB] Successfully attached image via upload menu file input!")
                                    await asyncio.sleep(3.5)
                                    break
                                except Exception:
                                    continue
                        except Exception as up_err:
                            print(f"⚠️ Upload menu notice: {up_err}")

                # Approach C: Paste image via Clipboard API + Control+v
                if not file_attached:
                    try:
                        with open(image_path, "rb") as img_f:
                            b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                        mime_type = "image/png" if image_path.endswith(".png") else "image/jpeg"
                        data_uri = f"data:{mime_type};base64,{b64_data}"

                        await context.grant_permissions(["clipboard-read", "clipboard-write"])
                        await gemini_page.bring_to_front()
                        await editor.focus()

                        await gemini_page.evaluate("""async (uri) => {
                            const res = await fetch(uri);
                            const blob = await res.blob();
                            const item = new ClipboardItem({ [blob.type]: blob });
                            await navigator.clipboard.write([item]);
                        }""", data_uri)

                        await asyncio.sleep(0.5)
                        await gemini_page.keyboard.press("Control+v")
                        file_attached = True
                        print("🌐 [GEMINI WEB] Successfully pasted image via Clipboard API (Control+v)!")
                        await asyncio.sleep(3.0)
                    except Exception as paste_err:
                        print(f"⚠️ [GEMINI WEB] Clipboard paste fallback notice: {paste_err}")

                if not file_attached:
                    print("⚠️ [GEMINI WEB] Could not attach image. Proceeding with text-only prompt.")

            except Exception as e:
                print(f"⚠️ [GEMINI WEB] Error uploading image: {e}")
            finally:
                try:
                    os.remove(image_path)
                except Exception:
                    pass

        # 5. Count existing model responses before submitting
        prev_responses = await gemini_page.query_selector_all("model-response")
        prev_count = len(prev_responses)

        # 6. Input prompt atomically using keyboard.insert_text to preserve newlines without triggering Enter submits
        print("🌐 [GEMINI WEB] Typing prompt into Web Gemini interface...")
        await gemini_page.bring_to_front()
        await asyncio.sleep(0.8)
        await editor.focus()
        await asyncio.sleep(0.3)

        # Atomic text insertion: prevents newlines from firing Enter keypresses or breaking contenteditable DOM
        await gemini_page.keyboard.insert_text(prompt)
        await asyncio.sleep(1.5)

        # Screenshot verification: verify prompt and image pasted properly into Gemini UI
        await gemini_page.screenshot(path="step3_gemini_pasted.png")

        send_btn = await gemini_page.query_selector(
            "button[aria-label*='Send message' i], "
            "button[aria-label*='Send' i], "
            "button[aria-label*='submit' i], "
            "button[aria-label*='Run' i], "
            "button.send-button"
        )
        if send_btn:
            await send_btn.click()
        else:
            await gemini_page.keyboard.press("Enter")

        # 7. Wait for stream completion (monitor text length stability)
        print("🌐 [GEMINI WEB] Waiting for reply generation to finish streaming...")
        await asyncio.sleep(1.5)
        
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
                        await gemini_page.screenshot(path="debug_gemini_reply_received.png")
                        break
                else:
                    stable_checks = 0
                    last_len = len(current_text)

        if response_text:
            print(f"🌐 [GEMINI WEB] Successfully fetched response! (Length: {len(response_text)})")
            return response_text
        
        print("❌ [GEMINI WEB] Response streaming timeout.")
        return None

    async def generate_content(self, prompt: str, system_instruction: str = "", page=None, image_path: Optional[str] = None) -> Optional[str]:
        cache_key = f"{system_instruction}\n\n{prompt}".strip()
        cached = self._cache_get(cache_key)
        if cached:
            print("💾 [CACHE HIT] Returning cached AI response.")
            return cached

        if page:
            try:
                web_res = await self.generate_content_web(prompt, page, image_path)
                if web_res:
                    self._cache_set(cache_key, web_res)
                    return web_res
            except Exception as e:
                print(f"⚠️ Web Gemini failed ({type(e).__name__}).")

        print("⚠️ Strictly using Web Gemini. No API key fallback.")
        return None

    async def generate_feed_comment(self, post_text: str, author_name: str = "Author", media_desc: str = "", page=None, image_path: Optional[str] = None) -> str:
        media_info = f"\nAttached image/media: {media_desc}" if media_desc else ""
        prompt = f"""You are Karanbir Singh, a Supply Chain and Production Planning professional at Reliance Industries, India. You are active on LinkedIn and write comments as a thoughtful peer.

Adapt to the Post Type:
- If it's a MEME or JOKE: Keep it lighthearted, fun, or drop a quick laughing/witty remark.
- If it's RELIGIOUS or SPIRITUAL: Be respectful, humble, and warm (e.g., "Beautiful message", "Well said", "Truly inspiring").
- If it's a PERSONAL MILESTONE (new job, anniversary, award): Be warm, congratulatory, and supportive.
- If it's PROFESSIONAL/INDUSTRY content: Be intellectual and grounded in business/supply chain reality. Pick 1 specific fact to react to.

Your commenting style rules:
- Write a highly humanized, natural, conversational comment. Sound like a real person typing on their phone, not an AI.
- NEVER start with robotic phrases like "Great post", "Spot on", "Absolutely", "Loved this" (unless it's a personal/spiritual post where simple warmth is fine).
- NEVER end with: "Keep it up!", "All the best!", "More power to you!", "Kudos!"
- Write 1-2 sentences max.
- Plain English. No buzzword stacking, no hollow affirmations.
- Return ONLY the comment text. No quotes, no preamble.

BAD (never write like this):
"Congratulations on this amazing milestone! Wishing you all the best on your journey ahead."

GOOD (write like this):
"Cellulose acetate from agricultural residue is an interesting feedstock choice — in supply chain terms, feedstock variability alone can make or break unit economics at pilot scale. Curious whether the CSTUP grant covers a pilot batch run or is scoped to lab characterisation for now?"

Now write a 2-sentence comment for this post:
Author: {author_name}
Post: {post_text}{media_info}"""

        result = await self.generate_content(prompt, page=page, image_path=image_path)
        if result:
            # Strip any accidental leading/trailing quotes Gemini sometimes adds
            return result.strip().strip('"').strip("'")

        text_lower = (post_text + " " + media_desc).lower()
        if "supply chain" in text_lower or "logistics" in text_lower or "inventory" in text_lower:
            return random.choice([
                "Lead-time variability is exactly where static safety-stock models break down — multi-echelon simulation handles this far better.",
                "S&OP alignment between commercial and supply teams is still the single biggest unlock most companies miss."
            ])
        elif "ai" in text_lower or "machine learning" in text_lower or "data" in text_lower:
            return random.choice([
                "Feature engineering on time-series demand data is where most ML forecasting projects either win or stall.",
                "Model accuracy matters less than model trust — if planners don\'t believe the output, adoption stays at zero."
            ])
        else:
            return random.choice([
                "The gap between research validation and operational scale-up is where most promising projects stall — good to see institutional backing bridging that.",
                "Persistence through iterative failure is genuinely underrated in technical work — the grant is recognition of the process, not just the outcome."
            ])

    async def generate_notification_reply(self, notification_text: str, parent_comment: str = "", post_context: str = "", page=None, image_path: Optional[str] = None) -> str:
        prompt = f"""You are Karanbir Singh, a Supply Chain and Production Planning professional at Reliance Industries, India.

Someone replied to or mentioned you in a LinkedIn comment thread.

Your reply rules:
- Write a highly humanized, natural, and conversational reply. Sound like a real person, not an AI.
- Adapt to the conversation tone: Be lighthearted for memes, respectful for spiritual posts, supportive for personal news, and professional for industry topics.
- Reference something specific from their message — a word, their name, or the topic they raised
- 1-2 sentences only
- Tone: warm, collegial, and grounded
- NEVER use: "Absolutely!", "Totally agree!", "Great point!", "Thanks for sharing!", "Indeed!", "Spot on!"
- Do NOT start with "Thank you for your"
- Return ONLY the reply text. No quotes.

Post Content including attachment if it have one:
{post_context}

Karan comment:
{parent_comment}

Reply to karan comment:
{notification_text}

If an image of the post/thread is attached, analyze it to understand the full context of the conversation and the original post (such as memes, infographics, or specific text).

Write a reply:"""
        
        result = await self.generate_content(prompt, page=page, image_path=image_path)
        if result:
            return result.strip().strip('"').strip("'")
        return random.choice([
            "Exactly — the practical constraint is always where the theory gets stress-tested.",
            "Fair point, and that tradeoff is often what separates a pilot from a scaled deployment."
        ])

    async def generate_inbox_reply(self, chat_history: str, partner_name: str, page=None, image_path: str = None) -> str:
        # Cap history to last 15 exchanges to prevent token overflow
        history_lines = [l for l in chat_history.strip().split("\n") if l.strip()]
        capped_history = "\n".join(history_lines[-30:])  # ~15 exchanges = 30 lines

        prompt = f"""You are Karanbir Singh, a Supply Chain and Production Planning professional at Reliance Industries, India.

You get LinkedIn DMs from recruiters, students, peers, and connections.
You are replying to a DM from: {partner_name}

Recent conversation (oldest to newest):
{capped_history}

Reply rules:
- Write a highly humanized, natural DM. Sound like a real person chatting, not an AI writing a formal email.
- 1-3 sentences max
- Match their register and context: lighthearted for memes/jokes, respectful for spiritual, professional for work topics.
- If they asked a specific question, answer it directly and honestly
- Birthday/congrats messages: warm but brief, not over-the-top
- Job/referral asks: be honest about your capacity without over-promising
- If the conversation is already closed/complete, a short warm close is fine
- Never use placeholders like [Your Name] or [Company]
- Do not wrap reply in quotes
- Return ONLY the reply text."""

        if page:
            result = await self.generate_content_web(prompt, page, image_path=image_path)
            if result:
                return result.strip().strip('"').strip("'")

        result = await self.generate_content(prompt, page=page)
        if result:
            return result.strip().strip('"').strip("'")
        return random.choice([
            "Hey, thanks for reaching out! Happy to connect and chat more.",
            "Appreciate the message — let me know how I can help."
        ])


        if page:
            result = await self.generate_content_web(prompt, page, image_path=image_path)
            if result:
                return result.strip().strip('"').strip("'")

        result = await self.generate_content(prompt, page=page)
        if result:
            return result.strip().strip('"').strip("'")
        return random.choice([
            "Hey, thanks for reaching out! Happy to connect and chat more.",
            "Appreciate the message — let me know how I can help."
        ])
