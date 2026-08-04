import asyncio
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright
from config import settings
from gemini_ai import GeminiAIClient
from linkedin_publisher import LinkedInPublisher
from linkedin_feed import LinkedInFeedEngine
from linkedin_notifications import LinkedInNotificationsEngine
from linkedin_inbox import LinkedInInboxEngine

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class VerificationReport:
    def __init__(self):
        self.results = {}

    def log_result(self, step_name: str, passed: bool, evidence: str):
        status = "PASSED" if passed else "FAILED"
        self.results[step_name] = {"status": status, "evidence": evidence}
        icon = "✅" if passed else "❌"
        print(f"{icon} [{status}] {step_name}")
        print(f"   Evidence: {evidence[:150]}\n")

async def run_e2e_verification():
    report = VerificationReport()
    print("=====================================================")
    print(" 🛡️  EXECUTING 4-SKILL E2E VERIFICATION PROTOCOL  🛡️ ")
    print("=====================================================\n")

    # Step 1: Gemini AI Key Loading & Dynamic Fallback Verification
    print("--- [Step 1: Gemini AI Client & Key Rotation Audit] ---")
    ai = GeminiAIClient()
    num_keys = len(ai.api_keys)
    sample_comment = await ai.generate_feed_comment(post_text="Testing supply chain resilience and lead time optimization during flood disruptions.", author_name="Verification Suite")
    ai_passed = sample_comment is not None and len(sample_comment) > 20
    report.log_result(
        step_name="Gemini AI Key Rotation & Content Generation",
        passed=ai_passed,
        evidence=f"API Keys Loaded: {num_keys} | Generated Comment: '{sample_comment}'"
    )

    # Step 2: Browser Session & Persistent Login Verification
    print("--- [Step 2: Playwright Chromium & Persistent Login Audit] ---")
    publisher = LinkedInPublisher(headless=False)
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(publisher.user_data_dir),
            channel="chrome",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--start-maximized", "--remote-debugging-port=9223", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # Check Login Status
        logged_in = await publisher.ensure_logged_in(page)
        report.log_result(
            step_name="LinkedIn Session & Automated Authentication",
            passed=logged_in,
            evidence=f"Current URL: {page.url} | Session Active: {logged_in}"
        )

        if not logged_in:
            print("❌ Authentication failed. Aborting further verification steps.")
            await context.close()
            return report

        # Step 3: Feed DOM Inspection, Dwell, Media Extraction, Like & TipTap Editor Audit
        print("--- [Step 3: Feed DOM Inspection, Dwell Reading & Action Bar Audit] ---")
        feed_engine = LinkedInFeedEngine(page=page, preproduction=True)
        feed_posts = await feed_engine.process_feed_posts(max_posts=2)
        feed_passed = len(feed_posts) > 0
        report.log_result(
            step_name="Feed Post Detection & Media/Text Content Extraction",
            passed=feed_passed,
            evidence=f"Processed Posts Count: {len(feed_posts)} | Sample Author: {feed_posts[0]['author'] if feed_posts else 'N/A'}"
        )

        # Step 4: Notifications DOM Inspection & Unread Actionable Audit
        print("--- [Step 4: Notifications DOM Inspection & Thread Audit] ---")
        notif_engine = LinkedInNotificationsEngine(page=page, preproduction=True)
        notifs = await notif_engine.process_top_20_notifications()
        notif_passed = isinstance(notifs, list)
        report.log_result(
            step_name="Notifications Top-20 Audit & Unread Filter",
            passed=notif_passed,
            evidence=f"Audited Notifications Count: {len(notifs)}"
        )

        # Step 5: Messaging Inbox DOM Inspection & Full Conversation History Audit
        print("--- [Step 5: Inbox DOM Inspection & Full Chat History Audit] ---")
        inbox_engine = LinkedInInboxEngine(page=page, preproduction=True)
        convs = await inbox_engine.process_top_20_messages()
        inbox_passed = len(convs) > 0
        report.log_result(
            step_name="Inbox Conversation Parsing & Full Thread Context Reading",
            passed=inbox_passed,
            evidence=f"Processed Conversations Count: {len(convs)} | Sample Connection: {convs[0]['partner_name'] if convs else 'N/A'}"
        )

        await context.close()

    print("=====================================================")
    print(" 📊 VERIFICATION PROTOCOL SUMMARY REPORT 📊 ")
    print("=====================================================")
    total_steps = len(report.results)
    passed_steps = sum(1 for v in report.results.values() if v['status'] == "PASSED")
    print(f"Passed: {passed_steps}/{total_steps} Steps ({passed_steps/total_steps*100:.1f}% DoD Pass Rate)")
    return report

if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
