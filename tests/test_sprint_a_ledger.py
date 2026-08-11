"""Sprint A ledger + skill-lock unit checks (no browser required)."""
import ast
import tempfile
from pathlib import Path

import engagement_tracker as et


def _isolate_db():
    tmp = Path(tempfile.mkdtemp()) / "engagement_history.db"
    et.DB_PATH = tmp
    return tmp


def test_published_option_is_permanent():
    _isolate_db()
    key = "/abs/Posts/2026-08-11/topic/Option_01"
    assert et.already_engaged("published_option", key) is False
    et.mark_engaged("published_option", key)
    assert et.already_engaged("published_option", key) is True
    et.clear_old_records()
    assert et.already_engaged("published_option", key) is True


def test_publisher_slot_is_permanent():
    _isolate_db()
    key = "published_slot_2026-08-11_1"
    et.mark_engaged("publisher_slot", key)
    assert et.already_engaged("publisher_slot", key) is True
    et.clear_old_records()
    assert et.already_engaged("publisher_slot", key) is True


def test_weekly_invite_hold_is_seven_days():
    _isolate_db()
    et.mark_engaged("connection_request_weekly_limit", "system")
    assert et.already_engaged("connection_request_weekly_limit", "system") is True
    assert et.COOLDOWN["connection_request_weekly_limit"] == 7 * 24 * 3600


def test_feed_like_cap_exists():
    assert et.DAILY_CAPS["feed_like"] == 40
    assert et.WEEKLY_CAPS["feed_like"] == 200


def test_human_type_adjacent_qwerty():
    src = (Path(__file__).resolve().parents[1] / "utils" / "playwright_utils.py").read_text(encoding="utf-8")
    assert "ADJACENT_KEYS" in src
    assert '"e": "wrsd"' in src
    assert "find_last_visible_editor" in src
    assert "ALLOWED_CARD_TAGS" in src
    assert "random.random() < 0.015" in src
    assert "random.random() < 0.04" in src


def test_pipeline_modules_ast_parse():
    root = Path(__file__).resolve().parents[1]
    modules = [
        "LinkedIn_Auto_Agent.py",
        "linkedin_publisher.py",
        "linkedin_feed.py",
        "linkedin_notifications.py",
        "linkedin_inbox.py",
        "linkedin_network.py",
        "gemini_ai.py",
        "engagement_tracker.py",
        "live_persistent_curator.py",
        "x_curator.py",
        "linkedin_rewriter.py",
        "post_exporter.py",
        "config.py",
        "utils/playwright_utils.py",
        "utils/stealth_chrome.py",
    ]
    for name in modules:
        ast.parse((root / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    test_published_option_is_permanent()
    test_publisher_slot_is_permanent()
    test_weekly_invite_hold_is_seven_days()
    test_feed_like_cap_exists()
    test_human_type_adjacent_qwerty()
    test_pipeline_modules_ast_parse()
    print("Sprint A ledger + AST checks passed.")
