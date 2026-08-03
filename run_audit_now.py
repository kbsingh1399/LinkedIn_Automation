import sys
import json
from post_auditor import PostAuditor

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

def main():
    auditor = PostAuditor()
    print("🔍 Auditing all exported post options for 2026-08-03...\n")
    results = auditor.audit_all_posts("2026-08-03")

    approved_count = sum(1 for r in results if r["status"] == "APPROVED")
    review_count = sum(1 for r in results if r["status"] != "APPROVED")

    print(f"📊 Audit Complete: {len(results)} total options reviewed")
    print(f"  ├── ✅ Approved (High Correlation & Quality): {approved_count}")
    print(f"  └── ⚠️ Flagged for Review: {review_count}\n")

    print("Detailed Topic Breakdown:")
    for r in results:
        status_icon = "✅" if r["status"] == "APPROVED" else "⚠️"
        print(f"  {status_icon} [{r['topic']} / {r['option']}] Score: {r['score']}/100")
        print(f"      {r['correlation_analysis']}")

if __name__ == "__main__":
    main()
