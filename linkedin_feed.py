import asyncio
import random
import sys
import os
import time
from typing import List, Dict, Any
from playwright.async_api import Page
from utils.playwright_utils import PlaywrightResilience
from gemini_ai import GeminiAIClient
from engagement_tracker import already_engaged, mark_engaged

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class LinkedInFeedEngine:
    def __init__(self, page: Page, preproduction: bool = True):
        self.page = page
        self.preproduction = preproduction
        self.ai = GeminiAIClient()

    async def process_feed_posts(self, max_posts: int = 3) -> List[Dict[str, Any]]:
        print(f"\n📱 Navigating to LinkedIn Feed (Target: {max_posts} posts)...")
        if not await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/feed/"):
            return []

        if await PlaywrightResilience.verify_security_checkpoint(self.page):
            print("🚨 [Security Gate] LinkedIn CAPTCHA / Security Checkpoint detected in Feed. Halting module.")
            return []

        # Reset to top first, then human-scroll down to load initial DOM cards
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.8)
        await PlaywrightResilience.human_scroll(self.page, random.randint(500, 800))
        await asyncio.sleep(1.5)

        # Robust selector fallback list for feed cards
        post_selectors = [
            "div[data-view-name='feed-full-update']",
            "div.feed-shared-update-v2",
            "article.feed-shared-update",
            "[role='article']",
            "[role='listitem']",
            "div[class*='update-v2']",
            "div.occludable-update"
        ]
        
        post_cards = []
        for sel in post_selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > len(post_cards):
                post_cards = found
                # Stop on first selector that returns results — don't overwrite with worse fallbacks
                break

        if not post_cards:
            post_cards = await self.page.query_selector_all("main div.scaffold-layout__main div[class*='feed'], main div[class*='update']")

        # Fallback: Find cards by traversing up from visible comment buttons
        if not post_cards:
            comment_btns = await self.page.query_selector_all("button[aria-label*='Comment']")
            print(f"DEBUG: Found {len(comment_btns)} comment buttons on viewport.")
            for btn in comment_btns:
                parent = btn
                for _ in range(5):
                    parent_handle = await parent.evaluate_handle("el => el.parentElement")
                    parent_el = parent_handle.as_element() if parent_handle else None
                    if parent_el:
                        parent = parent_el
                    else:
                        break
                if parent:
                    post_cards.append(parent)

        print(f"🔍 Found {len(post_cards)} post cards on feed viewport.")
        engaged = []

        from engagement_tracker import check_daily_limit, get_pacing_multiplier
        pacing = get_pacing_multiplier()
        if check_daily_limit("feed_comment", 20):
            print("ℹ️ [Feed Mode] Daily comment quota (20/20) reached. Running in LIKE-ONLY mode for feed posts.")

        for idx, card in enumerate(post_cards):
            if len(engaged) >= max_posts:
                break
            try:
                # Scroll card into view
                try:
                    await card.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass

                # Extract Author Name FIRST and print immediately to logs
                author_handle = await card.evaluate_handle("""el => {
                    const nameEl = el.querySelector('span.update-components-actor__name, span.feed-shared-actor__name, span[class*="actor__title"], div[class*="actor__title"], a[data-view-name*="actor"], a[href*="/in/"], a[class*="actor"]');
                    if (nameEl && nameEl.innerText.trim()) return nameEl.innerText.trim();
                    const imgEl = el.querySelector('.update-components-actor img, .feed-shared-actor img, img[alt]');
                    if (imgEl && imgEl.alt && imgEl.alt.trim() && !imgEl.alt.includes('logo')) return imgEl.alt.trim();
                    const ariaEl = el.querySelector('[aria-label*="profile" i], [aria-label*="View" i]');
                    if (ariaEl) {
                        const aria = ariaEl.getAttribute('aria-label') || '';
                        const match = aria.match(/View\\s+([^'’]+)['’]s\\s+profile/i);
                        if (match) return match[1].trim();
                    }
                    return '';
                }""")
                raw_author = await author_handle.json_value() if author_handle else ""
                author = raw_author.splitlines()[0] if raw_author else ""
                if "•" in author:
                    author = author.split("•")[0].strip()
                if not author:
                    author = "LinkedIn Creator"

                print(f"\n📌 [Feed Post #{len(engaged) + 1}] Processing post by: {author}")

                # 1. Expand "...more" button using exact LinkedIn data-test-id attribute
                try:
                    see_more = await card.query_selector("button[data-testid='expandable-text-button'], [data-testid='expandable-text-button'], button[data-test-id='expandable-text-button'], button:has-text('...more')")
                    if not see_more:
                        see_more_handle = await card.evaluate_handle("""el => {
                            const btns = Array.from(el.querySelectorAll('button, span[role="button"], span'));
                            return btns.find(b => {
                                // Never click <a> link tags (e.g. school or company profile links)
                                if (b.tagName.toLowerCase() === 'a' || b.closest('a')) return false;
                                const t = (b.innerText || '').trim().toLowerCase();
                                return (t === '… more' || t === '...more' || t.endsWith('more') || t === 'more') && b.offsetWidth > 0 && b.offsetHeight > 0;
                            }) || null;
                        }""")
                        see_more = see_more_handle.as_element() if see_more_handle else None

                    if see_more:
                        await see_more.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await see_more.click(force=True)
                        print("📖 Clicked ...more button to expand full post content")
                        await asyncio.sleep(1.2)
                except Exception:
                    pass

                # 2. Extract FULL post commentary text without line truncation
                text_el = await card.query_selector(
                    "[data-testid='expandable-text-box'], "
                    "span[data-testid='expandable-text-box'], "
                    "div.update-components-update-activity__commentary, "
                    "div.feed-shared-update-v2__description-text, "
                    "div.update-components-text, "
                    "div[data-view-name*='update-text'], "
                    "div[data-view-name*='commentary'], "
                    "span.break-words[class*='commentary'], "
                    "p.break-words, "
                    "span.break-words, "
                    "div.feed-shared-text"
                )
                
                post_text = ""
                if text_el:
                    post_text = (await text_el.inner_text()).strip()
                else:
                    # Fallback: Parse card text lines but preserve FULL content (do not truncate to 3 lines)
                    raw_text = (await card.inner_text()).strip()
                    lines = [l.strip() for l in raw_text.splitlines() if len(l.strip()) > 15]
                    # Filter out UI action buttons / header lines
                    filtered = [
                        l for l in lines 
                        if not any(w in l.lower() for w in ["like", "comment", "repost", "send", "follow", "connection", "impressions", "promoted", "suggested"])
                    ]
                    post_text = "\n".join(filtered) if filtered else raw_text

                if len(post_text) < 20:
                    continue

                # Dedup: skip if we already commented on this post within 7 days
                dedup_key = f"{author}::{post_text[:200]}"
                if already_engaged("feed_comment", dedup_key):
                    print(f"  [SKIP] Already commented on {author}'s post. Skipping.")
                    continue

                # Extract headline/organization (e.g. "Management Trainee @ UltraTech Cement")
                headline_el = await card.query_selector(
                    "span.update-components-actor__description, "
                    "div.update-components-actor__headline, "
                    "span.feed-shared-actor__description, "
                    "div[class*='actor__description'], "
                    "div[class*='actor__headline'], "
                    "span[class*='actor__sub-description']"
                )
                headline = (await headline_el.inner_text()).strip() if headline_el else ""
                headline = headline.splitlines()[0] if headline else ""

                author_with_details = f"{author} ({headline})" if headline else author

                # Step 2 Verification: Extract attached post image (or capture full screenshot if text-only)
                image_path = None
                try:
                    temp_name = f"temp_post_{len(engaged) + 1}_{int(time.time())}.png"
                    await card.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)

                    # Look for attached media image inside post card (strictly ignoring profile photos / avatar icons)
                    img_handle = await card.evaluate_handle("""el => {
                        // First check for explicit media anchor containers (e.g. showCommentBox=true or highlightedUpdateUrn)
                        const mediaAnchorImg = el.querySelector('a[href*="showCommentBox=true"] img, a[href*="highlightedUpdateUrn"] img, div.update-components-image img');
                        if (mediaAnchorImg && mediaAnchorImg.offsetWidth > 100 && mediaAnchorImg.offsetHeight > 100) {
                            return mediaAnchorImg;
                        }

                        const imgs = Array.from(el.querySelectorAll('img'));
                        return imgs.find(img => {
                            // Exclude profile photos, actor avatars, company logos, and header icons
                            if (img.closest('.update-components-actor') || 
                                img.closest('.feed-shared-actor') || 
                                img.closest('.EntityPhoto-circle-3') ||
                                (img.className || '').includes('avatar') ||
                                (img.className || '').includes('actor') ||
                                (img.src || '').includes('profile-displayphoto') ||
                                (img.src || '').includes('company-logo')) {
                                return false;
                            }
                            // Must be a substantial post media photo (> 150px width & height)
                            return img.offsetWidth > 150 && img.offsetHeight > 150;
                        }) || null;
                    }""")
                    img_el = img_handle.as_element() if img_handle else None

                    attached_saved = False
                    if img_el:
                        try:
                            img_src = await img_el.get_attribute("src")
                            if img_src and img_src.startswith("http"):
                                resp = await self.page.request.get(img_src, timeout=5000)
                                if resp.status == 200:
                                    img_bytes = await resp.body()
                                    with open(temp_name, "wb") as f:
                                        f.write(img_bytes)
                                    with open("step2_post_content_copied.png", "wb") as f:
                                        f.write(img_bytes)
                                    attached_saved = True
                                    print(f"🖼️ [Post Media] Extracted exact attached image from post for Gemini!")
                        except Exception as fetch_err:
                            print(f"⚠️ Notice downloading post image: {fetch_err}")

                    if not attached_saved:
                        print(f"📸 [Verification Step 2] Taking full page screenshot showing full post content...")
                        await self.page.screenshot(path=temp_name)
                        await self.page.screenshot(path="step2_post_content_copied.png")

                    if os.path.exists(temp_name):
                        image_path = temp_name
                except Exception as img_err:
                    print(f"⚠️ Could not capture post image/screenshot: {img_err}")

                # Step 1: Like Post (Runs unconditionally for every post card, even if comment quota is exhausted)
                if not self.preproduction:
                    await asyncio.sleep(random.uniform(1.0, 2.2) * pacing)
                    like_btn = await card.query_selector("button[aria-label*='Reaction button' i], button.react-button__trigger, button[aria-label*='Like' i], button:has-text('Like')")
                    if not like_btn:
                        like_handle = await card.evaluate_handle("""el => {
                            const btns = Array.from(el.querySelectorAll('button, [role="button"]'));
                            return btns.find(b => {
                                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                                const txt = (b.innerText || '').trim().toLowerCase();
                                return (aria.includes('like') || aria.includes('react') || txt.includes('like')) && 
                                       (txt !== 'comment' && txt !== 'repost' && txt !== 'send') && 
                                       b.offsetWidth > 0;
                            }) || null;
                        }""")
                        like_btn = like_handle.as_element() if like_handle else None

                    if like_btn:
                        try:
                            is_already_liked = await like_btn.evaluate("""btn => {
                                const pressed = btn.getAttribute('aria-pressed') === 'true';
                                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                                const activeClass = btn.className.includes('active') || btn.className.includes('selected');
                                return pressed || label.includes('unlike') || activeClass;
                            }""")
                            if not is_already_liked:
                                await like_btn.scroll_into_view_if_needed()
                                try:
                                    box = await like_btn.bounding_box()
                                    if box:
                                        await self.page.mouse.move(box["x"] + box["width"]/2 + random.randint(-5, 5), box["y"] + box["height"]/2 + random.randint(-5, 5))
                                except Exception:
                                    pass
                                await asyncio.sleep(random.uniform(0.4, 0.8) * pacing)
                                await like_btn.click(force=True)
                                print(f"👍 Liked {author}'s post")
                                await asyncio.sleep(random.uniform(1.2, 2.0) * pacing)
                                await self.page.screenshot(path="step1_post_liked.png")
                            else:
                                print(f"👍 Post by {author} is already liked.")
                        except Exception as lk_err:
                            print(f"⚠️ Like button notice: {lk_err}")

                # Check if Daily Comment Quota (20/20) is exhausted
                if check_daily_limit("feed_comment", 20):
                    print(f"⏩ [Comment Cap 20/20] Liked {author}'s post, skipping comment generation.")
                    # Human behavior: Organic scroll down to next post card
                    await PlaywrightResilience.human_scroll(self.page, random.randint(400, 700))
                    continue

                ai_comment = await self.ai.generate_feed_comment(post_text, author_with_details, page=self.page, image_path=image_path)

                if self.preproduction:
                    print(f"[{len(engaged)+1}] 🧪 [PREPROD] {author}: {ai_comment[:50]}...")
                    engaged.append({"author": author, "comment": ai_comment})
                else:
                    # Open Comment Box
                    comment_btn = await card.query_selector("button.comment-button, button[aria-label*='Comment' i], button:has-text('Comment')")
                    if not comment_btn:
                        comment_handle = await card.evaluate_handle("""el => {
                            const btns = Array.from(el.querySelectorAll('button, [role="button"]'));
                            return btns.find(b => {
                                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                                const txt = (b.innerText || '').trim().toLowerCase();
                                return (aria.includes('comment') || txt.includes('comment')) && b.offsetWidth > 0;
                            }) || null;
                        }""")
                        comment_btn = comment_handle.as_element() if comment_handle else None

                    if comment_btn:
                        try:
                            await comment_btn.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await comment_btn.click(force=True)
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                        except Exception:
                            pass

                    # Step 4 & Step 5: Type Comment & Submit with Screenshot Verifications
                    editor = await card.query_selector("div[aria-label='Text editor for creating comment'], div.tiptap.ProseMirror, div[aria-label*='comment' i], div[contenteditable='true'], div[role='textbox']")
                    if not editor:
                        editor = await self.page.query_selector("div[aria-label='Text editor for creating comment'], div.comments-comment-box div[contenteditable='true'], div.tiptap.ProseMirror, div[aria-label*='comment' i], div[contenteditable='true'][role='textbox']")

                    if editor:
                        await self.page.bring_to_front()
                        await editor.scroll_into_view_if_needed()
                        await asyncio.sleep(0.4)
                        await PlaywrightResilience.human_type_with_mistakes(self.page, editor, ai_comment)
                        await PlaywrightResilience.random_thinking_pause()

                        try:
                            await editor.evaluate("""el => {
                                el.focus();
                                el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText' }));
                                el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
                            }""")
                            await asyncio.sleep(0.6)
                        except Exception:
                            pass

                        # Verification Step 4: Screenshot verifying comment written in editor
                        await self.page.screenshot(path="step4_comment_written.png")
                        await self.page.screenshot(path="debug_linkedin_comment_typed.png")

                        submit_btn = await card.query_selector(
                            "button.comments-comment-box__submit-button, "
                            "form.comments-comment-box__form button.artdeco-button--primary, "
                            "div.comments-comment-box__submit button.artdeco-button--primary, "
                            "button.artdeco-button--primary[type='submit']"
                        )
                        if not submit_btn:
                            submit_handle = await card.evaluate_handle("""el => {
                                const btns = Array.from(el.querySelectorAll('button'));
                                return btns.find(b => {
                                    const txt = (b.innerText || '').trim();
                                    return (txt === 'Comment' || txt.includes('Comment')) && b.offsetWidth > 0 && b.offsetHeight > 0;
                                }) || null;
                            }""")
                            submit_btn = submit_handle.as_element() if submit_handle else None

                        # Fallback: search page-level scope if button is outside card container
                        if not submit_btn:
                            submit_btn = await self.page.query_selector(
                                "button.comments-comment-box__submit-button, "
                                "form.comments-comment-box__form button.artdeco-button--primary, "
                                "div.comments-comment-box__submit button.artdeco-button--primary, "
                                "button.artdeco-button--primary[type='submit']"
                            )

                        if submit_btn:
                            try:
                                await submit_btn.click(force=True, timeout=4000)
                            except Exception:
                                await submit_btn.evaluate("b => b.click()")
                            print(f"[{len(engaged)+1}] ✅ Comment posted on {author}'s post")
                            await asyncio.sleep(random.uniform(3.0, 5.0))

                            # Verification Step 5: Screenshot verifying comment posted
                            await self.page.screenshot(path="step5_comment_posted.png")
                            engaged.append({"author": author, "comment": ai_comment})
                            # Record engagement so we never double-comment this post
                            mark_engaged("feed_comment", dedup_key)

                # Human behavior: Organic scroll down + 20% chance of brief reverse scroll to re-read
                await PlaywrightResilience.human_scroll(self.page, random.randint(450, 750))
                await PlaywrightResilience.occasional_reverse_scroll(self.page, probability=0.20)

                # Ensure page stays on feed URL; if navigation happened, break — card handles are stale
                if "linkedin.com/feed" not in self.page.url:
                    print("⚠️ Feed navigated away to external link. Returning to Feed...")
                    await PlaywrightResilience.safe_goto(self.page, "https://www.linkedin.com/feed/")
                    await asyncio.sleep(1.5)
                    break

            except Exception as e:
                print(f"⚠️ Feed error: {e}")
                continue

        print(f"✅ Feed cycle complete. Engaged with {len(engaged)} posts.")
        return engaged
