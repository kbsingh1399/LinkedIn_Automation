"""
Comprehensive LinkedIn DOM Fingerprinter across all major LinkedIn pages.
Generates structural selector analysis for Feed, Notifications, Messaging, Network, and Jobs.
"""
import asyncio
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright
from linkedin_publisher import LinkedInPublisher

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPORT_PATH = Path(r"C:\Users\SIGMA\.gemini\antigravity-ide\brain\4ae04bfb-5033-4bd5-b14a-b253b801a724\dom_analysis_report.json")
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

report_data = {}

async def probe_page(page, url: str, label: str):
    print(f"\n{'='*60}")
    print(f"  🔍 PROBING DOM FOR PAGE: {label}")
    print(f"  URL: {url}")
    print(f"{'='*60}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"  ⚠️ Navigation warning: {e}")

    await asyncio.sleep(4)
    await page.mouse.wheel(0, 1200)
    await asyncio.sleep(3)

    current_url = page.url
    page_report = {
        "label": label,
        "target_url": url,
        "final_url": current_url,
        "stable_probes": [],
        "buttons": [],
        "text_inputs": [],
        "sample_texts": []
    }

    # 1. Probe Key Roles and Attributes
    probes = [
        ("button[aria-label*='Like']", "Like buttons"),
        ("button[aria-label*='Comment']", "Comment buttons"),
        ("button[aria-label*='Repost']", "Repost buttons"),
        ("button[aria-label*='Send']", "Send/Message buttons"),
        ("[role='article']", "Article roles"),
        ("[role='listitem']", "List-item roles"),
        ("[role='feed']", "Feed role"),
        ("div[contenteditable='true']", "Editable rich text boxes"),
        ("div[role='textbox']", "Textbox roles"),
        ("input[type='text']", "Text input elements"),
        ("textarea", "Textarea elements"),
        ("[aria-label*='notification']", "Notification cards"),
        ("[aria-label*='conversation']", "Conversation cards")
    ]

    print("\n  [Attributes & Role Breakdown]")
    for sel, desc in probes:
        try:
            els = await page.query_selector_all(sel)
            if els:
                sample = els[0]
                tag = await sample.evaluate("el => el.tagName")
                aria = await sample.get_attribute("aria-label") or ""
                cls = (await sample.get_attribute("class") or "")[:60]
                print(f"   ✅ {desc:25s} | Count: {len(els):2d} | tag={tag} | aria={aria!r}")
                page_report["stable_probes"].append({
                    "selector": sel,
                    "description": desc,
                    "count": len(els),
                    "tag": tag,
                    "aria_label": aria,
                    "sample_class": cls
                })
        except Exception:
            pass

    # 2. Extract Button Aria Labels
    btns = await page.query_selector_all("button[aria-label]")
    unique_labels = sorted(list(set([
        (await b.get_attribute("aria-label") or "").strip()
        for b in btns
        if await b.get_attribute("aria-label")
    ])))
    print(f"\n  [Unique Button Aria-Labels ({len(unique_labels)} found)]")
    for lbl in unique_labels[:20]:
        print(f"    • {lbl!r}")
    page_report["buttons"] = unique_labels

    # 3. Sample Page Content Text
    spans = await page.query_selector_all("main span, main p, main div")
    text_count = 0
    for sp in spans:
        if text_count >= 5:
            break
        try:
            txt = (await sp.inner_text()).strip()
            if 40 < len(txt) < 250 and "Sign in" not in txt and "\n" not in txt[:40]:
                tag = await sp.evaluate("el => el.tagName")
                page_report["sample_texts"].append({"tag": tag, "text": txt})
                text_count += 1
        except Exception:
            pass

    report_data[label] = page_report

async def main():
    publisher = LinkedInPublisher(headless=False)
    async with async_playwright() as p:
        user_data_dir = str(publisher.user_data_dir)
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--new-window", "--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        print("🔍 Verifying LinkedIn Session...")
        await publisher.ensure_logged_in(page)

        pages_to_probe = [
            ("https://www.linkedin.com/feed/", "FEED"),
            ("https://www.linkedin.com/notifications/", "NOTIFICATIONS"),
            ("https://www.linkedin.com/messaging/", "MESSAGING"),
            ("https://www.linkedin.com/mynetwork/", "MY_NETWORK"),
            ("https://www.linkedin.com/jobs/", "JOBS")
        ]

        for url, label in pages_to_probe:
            await probe_page(page, url, label)

        await context.close()

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Comprehensive DOM Analysis complete! Saved data to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
