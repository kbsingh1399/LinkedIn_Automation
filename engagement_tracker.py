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

# None = permanent (never eligible again, never purged)
COOLDOWN = {
    "feed_comment":                     7 * 24 * 3600,
    "feed_like":                        7 * 24 * 3600,
    "notification_reply":               3 * 24 * 3600,
    "inbox_reply":                      1 * 24 * 3600,
    "connection_request":               30 * 24 * 3600,
    "connection_request_weekly_limit":  7 * 24 * 3600,
    "published_option":                 None,
    "publisher_slot":                   None,
}

PERMANENT_TYPES = {k for k, v in COOLDOWN.items() if v is None}


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
    Permanent types (published_option, publisher_slot) stay locked forever.
    """
    ident = _make_id(raw_identifier)
    cooldown = COOLDOWN.get(eng_type, 86400)
    with _conn() as c:
        row = c.execute(
            "SELECT engaged_at FROM engagements WHERE type=? AND identifier=?",
            (eng_type, ident)
        ).fetchone()
    if not row:
        return False
    if eng_type in PERMANENT_TYPES or cooldown is None:
        return True
    cutoff = int(time.time()) - int(cooldown)
    return bool(row[0] > cutoff)


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
    """Purge records older than the longest finite cooldown. Never delete permanent types."""
    finite = [v for k, v in COOLDOWN.items() if v is not None and k not in PERMANENT_TYPES]
    max_cooldown = max(finite) if finite else 30 * 24 * 3600
    cutoff = int(time.time()) - max_cooldown
    placeholders = ",".join("?" * len(PERMANENT_TYPES)) if PERMANENT_TYPES else ""
    with _conn() as c:
        if placeholders:
            deleted = c.execute(
                f"DELETE FROM engagements WHERE engaged_at < ? AND type NOT IN ({placeholders})",
                (cutoff, *sorted(PERMANENT_TYPES)),
            ).rowcount
        else:
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


def get_weekly_count(eng_type: str = None) -> int:
    """Return total engagements completed in the last 7 days (rolling 168 hours)."""
    seven_days_ago_ts = int(time.time()) - (7 * 24 * 3600)
    with _conn() as c:
        if eng_type:
            row = c.execute(
                "SELECT COUNT(*) FROM engagements WHERE type=? AND engaged_at >= ?", (eng_type, seven_days_ago_ts)
            ).fetchone()
            return row[0] if row else 0
        else:
            row = c.execute(
                "SELECT COUNT(*) FROM engagements WHERE engaged_at >= ?", (seven_days_ago_ts,)
            ).fetchone()
            return row[0] if row else 0


DAILY_CAPS = {
    "feed_comment": 20,
    "feed_like": 40,
    "notification_reply": 20,
    "inbox_reply": 25,
    "connection_request": 20,
}

WEEKLY_CAPS = {
    "feed_comment": 100,
    "feed_like": 200,
    "notification_reply": 100,
    "inbox_reply": 120,
    "connection_request": 80,
}


def is_weekly_limit_reached(eng_type: str) -> bool:
    """Check if weekly safety limit for the engagement type has been reached."""
    cap = WEEKLY_CAPS.get(eng_type, 100)
    count = get_weekly_count(eng_type)
    return count >= cap


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

    like_done = get_today_count("feed_like")
    like_cap = DAILY_CAPS["feed_like"]
    like_left = max(0, like_cap - like_done)

    notif_done = get_today_count("notification_reply")
    notif_cap = DAILY_CAPS["notification_reply"]
    notif_left = max(0, notif_cap - notif_done)

    inbox_done = get_today_count("inbox_reply")
    inbox_cap = DAILY_CAPS["inbox_reply"]
    inbox_left = max(0, inbox_cap - inbox_done)

    conn_done = get_today_count("connection_request")
    conn_cap = DAILY_CAPS["connection_request"]
    conn_left = max(0, conn_cap - conn_done)

    remaining = feed_left + like_left + notif_left + inbox_left + conn_left
    status_text = "ACTIVE (Within Safe Daily Caps)" if remaining > 0 else "ALL DAILY CAPS COMPLETED TILL MIDNIGHT"

    content = f"""====================================================
LINKEDIN AUTOMATION - DAILY TRACKER ({today_str})
====================================================
Last Updated: {timestamp_str}

• Feed Comments:
  - Done Today: {feed_done} / {feed_cap}
  - Remaining:  {feed_left}

• Feed Likes:
  - Done Today: {like_done} / {like_cap}
  - Remaining:  {like_left}

• Notification Replies:
  - Done Today: {notif_done} / {notif_cap}
  - Remaining:  {notif_left}

• Inbox DM Replies:
  - Done Today: {inbox_done} / {inbox_cap}
  - Remaining:  {inbox_left}

• Connection Requests:
  - Done Today: {conn_done} / {conn_cap}
  - Remaining:  {conn_left}

STATUS: {status_text}
====================================================
"""
    try:
        with open(TXT_TRACKER_PATH, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"⚠️ Could not update daily_engagement_tracker.txt: {e}")


def check_daily_limit(eng_type: str, max_limit: int = None) -> bool:
    """Returns True if daily limit has been reached or exceeded."""
    update_daily_tracker_file()
    cap = max_limit if max_limit is not None else DAILY_CAPS.get(eng_type, 15)
    current = get_today_count(eng_type)
    if current >= cap:
        print(f"🛑 [Rate Limit] Daily cap reached for {eng_type} ({current}/{cap}). Skipping.")
        return True
    return False

# Initialize txt tracker on module load
update_daily_tracker_file()
