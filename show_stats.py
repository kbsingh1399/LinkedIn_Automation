"""
Engagement Analytics Dashboard & Daily Rate Limit Checker
Run via: python show_stats.py
"""

import sys
import sqlite3
import datetime
import time
from pathlib import Path
from engagement_tracker import DB_PATH, COOLDOWN, get_today_count

# Ensure UTF-8 output encoding for Windows terminal console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def print_dashboard():
    print("\n" + "="*60)
    print(" 📊 LINKEDIN AUTOMATION - ENGAGEMENT ANALYTICS & DASHBOARD ")
    print("="*60)
    print(f" 🕒 Current Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 📂 Database:     {DB_PATH}")
    print("-" * 60)

    if not DB_PATH.exists():
        print(" ⚠️ No engagement database found yet. Run a cycle first!")
        return

    with sqlite3.connect(str(DB_PATH)) as c:
        # 1. Today's Activity Breakdown
        midnight_ts = int(datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        today_rows = c.execute(
            "SELECT type, COUNT(*) FROM engagements WHERE engaged_at >= ? GROUP BY type", (midnight_ts,)
        ).fetchall()
        today_stats = {r[0]: r[1] for r in today_rows}

        print("\n 📈 TODAY'S ENGAGEMENT ACTIVITY (Since Midnight):")
        print(f"   • Feed Comments Posted:     {today_stats.get('feed_comment', 0)} / 15 (Daily Cap)")
        print(f"   • Notification Replies:     {today_stats.get('notification_reply', 0)} / 20 (Daily Cap)")
        print(f"   • Inbox DMs Responded:      {today_stats.get('inbox_reply', 0)} / 25 (Daily Cap)")
        print(f"   ------------------------------------------------")
        print(f"   • TOTAL TODAY:              {sum(today_stats.values())} engagements")

        # 2. Lifetime Activity Breakdown
        all_rows = c.execute(
            "SELECT type, COUNT(*) FROM engagements GROUP BY type"
        ).fetchall()
        all_stats = {r[0]: r[1] for r in all_rows}

        print("\n 🌐 LIFETIME ENGAGEMENT SUMMARY:")
        print(f"   • Total Feed Comments:       {all_stats.get('feed_comment', 0)}")
        print(f"   • Total Notification Replies:{all_stats.get('notification_reply', 0)}")
        print(f"   • Total Inbox Conversations: {all_stats.get('inbox_reply', 0)}")
        print(f"   ------------------------------------------------")
        print(f"   • TOTAL RECORDED:           {sum(all_stats.values())} engagements")

        # 3. Active Cooldown Window Targets
        print("\n ⏳ ACTIVE DEDUPLICATION COOLDOWN WINDOWS:")
        for eng_type, seconds in COOLDOWN.items():
            days = seconds // 86400
            cutoff = int(time.time()) - seconds
            active_count = c.execute(
                "SELECT COUNT(*) FROM engagements WHERE type=? AND engaged_at >= ?", (eng_type, cutoff)
            ).fetchone()[0]
            print(f"   • {eng_type:<20}: {active_count} targets locked ({days} day cooldown)")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    print_dashboard()
