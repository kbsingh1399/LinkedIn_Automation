"""
Full acceptance pipeline runner with login gate, then DOM probe across all 3 pages.
Runs in PREPRODUCTION mode (no real posts/comments/messages sent).
"""
import asyncio
import sys
from playwright.async_api import async_playwright
from linkedin_publisher import LinkedInPublisher
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


PASS = "PASS"
FAIL = "FAIL"
results = []


def log(label: str, status: str, evidence: str):
    icon = "✅" if status == PASS else "❌"
    results.append({"label": label, "status": status, "evidence": evidence})
    print(f"{icon} [{status}] {label}")
    print(f"   Evidence: {evidence[:160]}")
    print()


async def probe_dom(page, url: str, label: str):
    """Navigate to a page and fingerprint what's actually there."""
    print(f"\n{'─'*60}")
    print(f"  DOM PROBE: {label}  →  {url}")
    print(f"{'─'*60}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"  ⚠️ Navigation error: {e}")
    await asyncio.sleep(4)
    await page.mouse.wheel(0, 1200)
    await asyncio.sleep(3)

    # Check we're not on the login page
    current_url = page.url
    if "login" in current_url or "authwall" in current_url:
        print(f"  ❌ REDIRECTED TO LOGIN — session may have expired for: {url}")
        log(f"Session valid on {label}", FAIL, f"Redirected to: {current_url}")
        return

    log(f"Session valid on {label}", PASS, f"URL: {current_url}")

    # Probe stable attributes
    stable_probes = [
        ("button[aria-label*='Like']", "Like buttons"),
        ("button[aria-label*='Comment']", "Comment buttons"),
        ("button[aria-label*='Repost']", "Repost buttons"),
        ("button[aria-label*='Send']", "Send/Message buttons"),
        ("[role='article']", "Article roles"),
        ("[role='listitem']", "List-item roles"),
        ("[role='feed']", "Feed role"),
        ("div[contenteditable='true']", "Editable editors"),
        ("div[role='textbox']", "Textbox roles"),
    ]

    found_any = False
    for sel, name in stable_probes:
        els = await page.query_selector_all(sel)
        if els:
            found_any = True
            # Print first element's aria-label for context
            aria = await els[0].get_attribute("aria-label") or ""
            print(f"  ✅ {name}: {len(els)} found  [aria-label={aria!r}]")

    # Dump all unique button aria-labels
    btns = await page.query_selector_all("button[aria-label]")
    unique_labels = sorted(set([
        (await b.get_attribute("aria-label") or "").strip()
        for b in btns
        if await b.get_attribute("aria-label")
    ]))
    print(f"\n  All {len(unique_labels)} button aria-labels on {label}:")
    for lbl in unique_labels[:25]:
        print(f"    - {lbl!r}")

    # Sample post text
    text_found = False
    spans = await page.query_selector_all("main span, main p, main div")
    for sp in spans:
        try:
            txt = (await sp.inner_text()).strip()
            if 40 < len(txt) < 300 and "Sign in" not in txt and "\n" not in txt[:60]:
                tag = await sp.evaluate("el => el.tagName")
                print(f"\n  Sample text [{tag}]: {txt[:120]!r}")
                text_found = True
                break
        except Exception:
            pass

    log(
        f"DOM content loaded on {label}",
        PASS if found_any or text_found else FAIL,
        f"Stable elements found: {found_any} | Text found: {text_found}"
    )


async def run_acceptance():
    print("=" * 60)
    print("  🛡️  ACCEPTANCE ORCHESTRATOR — FULL PIPELINE VERIFICATION")
    print("=" * 60)
    print("  Mode: PREPRODUCTION (no real actions will be taken)")
    print("=" * 60)

    publisher = LinkedInPublisher(headless=False)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(publisher.user_data_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--new-window", "--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ── GATE 1: Login ──────────────────────────────────────────
        print("\n[GATE 1] Verifying / Establishing LinkedIn Session...")
        logged_in = await publisher.ensure_logged_in(page)
        log(
            "LinkedIn Authentication Gate",
            PASS if logged_in else FAIL,
            f"Session active: {logged_in} | URL: {page.url}"
        )

        if not logged_in:
            print("❌ ESCALATED: Cannot proceed without a valid session. Please log in manually to the browser window that opened.")
            await context.close()
            print_summary()
            return

        # ── GATE 2: Feed DOM + Feed Engine ─────────────────────────
        print("\n[GATE 2] Feed Page — DOM Probe + Feed Engine (preproduction)...")
        await probe_dom(page, "https://www.linkedin.com/feed/", "FEED")

        # Now run the feed engine in preproduction
        feed_engine = LinkedInFeedEngine(page=page, preproduction=True)
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        await page.mouse.wheel(0, 1200)
        await asyncio.sleep(3)
        feed_posts = await feed_engine.process_feed_posts(max_posts=2)
        log(
            "Feed Engine — Post Detection & Preproduction Cycle",
            PASS if len(feed_posts) > 0 else FAIL,
            f"Posts processed: {len(feed_posts)} | Sample author: {feed_posts[0]['author'] if feed_posts else 'NONE'}"
        )

        # ── GATE 3: Notifications DOM + Engine ─────────────────────
        print("\n[GATE 3] Notifications Page — DOM Probe + Notifications Engine (preproduction)...")
        await probe_dom(page, "https://www.linkedin.com/notifications/", "NOTIFICATIONS")

        notif_engine = LinkedInNotificationsEngine(page=page, preproduction=True)
        await page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        notifs = await notif_engine.process_top_20_notifications()
        log(
            "Notifications Engine — Top 20 Audit",
            PASS if isinstance(notifs, list) else FAIL,
            f"Notifications found: {len(notifs)}"
        )

        # ── GATE 4: Inbox / Messaging DOM + Engine ─────────────────
        print("\n[GATE 4] Messaging Page — DOM Probe + Inbox Engine (preproduction)...")
        await probe_dom(page, "https://www.linkedin.com/messaging/", "MESSAGING")

        inbox_engine = LinkedInInboxEngine(page=page, preproduction=True)
        await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        convs = await inbox_engine.process_top_20_messages()
        log(
            "Inbox Engine — Top 20 Conversations Audit",
            PASS if len(convs) > 0 else FAIL,
            f"Conversations found: {len(convs)} | Sample: {convs[0]['partner_name'] if convs else 'NONE'}"
        )

        await context.close()

    print_summary()


def print_summary():
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    failed = total - passed
    print("\n" + "=" * 60)
    print("  📊 ACCEPTANCE REPORT")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == PASS else "❌"
        print(f"  {icon} {r['status']:4s}  {r['label']}")
    print(f"\n  Result: {passed}/{total} gates passed")
    if failed == 0:
        print("  Status: ACCEPTED ✅")
    else:
        print(f"  Status: ESCALATED ⚠️  ({failed} gate(s) failed)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_acceptance())
