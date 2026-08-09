"""
Engagement tracker -- SQLite-backed deduplication.
Ensures we never comment, reply, or message the same target twice
within the configured cooldown window.
"""
import hashlib
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "engagement_history.db"

# Cooldown in seconds before the same target is eligible again
COOLDOWN = {
    "feed_comment":       7 * 24 * 3600,   # 7 days  -- same post
    "notification_reply": 3 * 24 * 3600,   # 3 days  -- same notification
    "inbox_reply":        1 * 24 * 3600,   # 1 day   -- same DM partner
}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.execute("""
        CREATE TABLE IF NOT EXISTS engagements (
            type        TEXT NOT NULL,
            identifier  TEXT NOT NULL,
            engaged_at  INTEGER NOT NULL,
            PRIMARY KEY (type, identifier)
        )
    """)
    c.commit()
    return c


def _make_id(text: str) -> str:
    """SHA-1 hash of normalized text."""
    return hashlib.sha1(text.strip().lower().encode()).hexdigest()


def already_engaged(eng_type: str, raw_identifier: str) -> bool:
    """
    Returns True if we already engaged with this target within cooldown.
    eng_type: "feed_comment" | "notification_reply" | "inbox_reply"
    raw_identifier: post text / notification text / partner name
    """
    ident = _make_id(raw_identifier)
    cooldown = COOLDOWN.get(eng_type, 86400)
    cutoff = int(time.time()) - cooldown
    with _conn() as c:
        row = c.execute(
            "SELECT engaged_at FROM engagements WHERE type=? AND identifier=?",
            (eng_type, ident)
        ).fetchone()
    return bool(row and row[0] > cutoff)


def mark_engaged(eng_type: str, raw_identifier: str) -> None:
    """Record that we just engaged with this target and update daily txt tracker."""
    ident = _make_id(raw_identifier)
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO engagements (type, identifier, engaged_at) VALUES (?,?,?)",
            (eng_type, ident, int(time.time()))
        )
    update_daily_tracker_file()


def engagement_summary() -> dict:
    """Return counts by type for logging."""
    with _conn() as c:
        rows = c.execute(
            "SELECT type, COUNT(*) FROM engagements GROUP BY type"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def clear_old_records() -> int:
    """Purge records older than the longest cooldown. Returns deleted count."""
    max_cooldown = max(COOLDOWN.values())
    cutoff = int(time.time()) - max_cooldown
    with _conn() as c:
        deleted = c.execute(
            "DELETE FROM engagements WHERE engaged_at < ?", (cutoff,)
        ).rowcount
    return deleted


def get_today_count(eng_type: str = None) -> int:
    """Return total engagements completed today (since midnight local time)."""
    import datetime
    midnight_ts = int(datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    with _conn() as c:
        if eng_type:
            row = c.execute(
                "SELECT COUNT(*) FROM engagements WHERE type=? AND engaged_at >= ?", (eng_type, midnight_ts)
            ).fetchone()
            return row[0] if row else 0
        else:
            row = c.execute(
                "SELECT COUNT(*) FROM engagements WHERE engaged_at >= ?", (midnight_ts,)
            ).fetchone()
            return row[0] if row else 0


DAILY_CAPS = {
    "feed_comment": 20,
    "notification_reply": 20,
    "inbox_reply": 25,
}

TXT_TRACKER_PATH = Path(__file__).parent / "daily_engagement_tracker.txt"


def get_pacing_multiplier() -> float:
    """
    Returns delay multiplier based on time of day and remaining quota.
    Accelerates pacing near end of day (8 PM - 11:59 PM) if quota remains.
    """
    import datetime
    now = datetime.datetime.now()
    hour = now.hour
    feed_done = get_today_count("feed_comment")
    feed_cap = DAILY_CAPS["feed_comment"]
    feed_left = max(0, feed_cap - feed_done)

    # Day-End Catchup (8 PM onwards): if remaining quota > 3, speed up delays (0.4x - 0.6x)
    if hour >= 20 and feed_left > 3:
        print(f"⚡ [Day-End Catchup] Hour {hour}:00 with {feed_left} comments remaining. Accelerating pacing!")
        return 0.5
    return 1.0


def update_daily_tracker_file() -> None:
    """Write real-time daily activity and remaining counts to daily_engagement_tracker.txt. Resets automatically every midnight."""
    import datetime
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    feed_done = get_today_count("feed_comment")
    feed_cap = DAILY_CAPS["feed_comment"]
    feed_left = max(0, feed_cap - feed_done)

    notif_done = get_today_count("notification_reply")
    notif_cap = DAILY_CAPS["notification_reply"]
    notif_left = max(0, notif_cap - notif_done)

    inbox_done = get_today_count("inbox_reply")
    inbox_cap = DAILY_CAPS["inbox_reply"]
    inbox_left = max(0, inbox_cap - inbox_done)

    status_text = "ACTIVE (Within Safe Daily Caps)" if (feed_left > 0 or notif_left > 0 or inbox_left > 0) else "ALL DAILY CAPS COMPLETED TILL MIDNIGHT"

    content = f"""====================================================
LINKEDIN AUTOMATION - DAILY TRACKER ({today_str})
====================================================
Last Updated: {timestamp_str}

• Feed Comments:
  - Done Today: {feed_done} / {feed_cap}
  - Remaining:  {feed_left}

• Notification Replies:
  - Done Today: {notif_done} / {notif_cap}
  - Remaining:  {notif_left}

• Inbox DM Replies:
  - Done Today: {inbox_done} / {inbox_cap}
  - Remaining:  {inbox_left}

STATUS: {status_text}
====================================================
"""
    try:
        with open(TXT_TRACKER_PATH, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"⚠️ Could not update daily_engagement_tracker.txt: {e}")


def check_daily_limit(eng_type: str, max_limit: int = 15) -> bool:
    """Returns True if daily limit has been reached or exceeded."""
    update_daily_tracker_file()
    current = get_today_count(eng_type)
    if current >= max_limit:
        print(f"🛑 [Rate Limit] Daily cap reached for {eng_type} ({current}/{max_limit}). Skipping.")
        return True
    return False

# Initialize txt tracker on module load
update_daily_tracker_file()


