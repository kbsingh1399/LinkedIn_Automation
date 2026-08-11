# LinkedIn Automation — End-to-End Audit & Next-Build Roadmap

**Date:** 2026-08-11  
**Updated:** 2026-08-12 — Sprint A items 1–4 from section 6 are implemented on this branch. The scorecard below is the pre-fix audit.  
**Branch:** `arena/019ff25c-linkedin-automation`  
**Skills applied:** `browser-automation-stealth`, `gemini-web-automation`, `linkedin-engagement-engines`, `data-engineering-data-pipeline`  
**Note:** `LinkedIn_chat_1.txt` was not present in the workspace or GitHub tree. This audit is grounded in the four project skills, the production modules they map to, and live state in `daily_engagement_tracker.txt`.

---

## 1. What we already have (working core)

The engine is a real, multi-module stealth agent — not a prototype:

| Layer | Module | What it does today |
|---|---|---|
| Orchestrator | `LinkedIn_Auto_Agent.py` | Persistent Chrome loop, cycle jitter, security/overlay gates, slot publisher, auto-curator trigger |
| Feed | `linkedin_feed.py` | Card parse, `...more` expand, media extract, like, Gemini comment, 20/day cap |
| Notifications | `linkedin_notifications.py` | Actionable-only filter, thread open, Reply/Comment fallback, last-visible editor |
| Inbox | `linkedin_inbox.py` | Conversation list, last-speaker skip, locked-thread gate, Gemini DM |
| Network | `linkedin_network.py` | Keyword-targeted Connect, weekly-limit modal hold, 20/day + 80/week |
| Publisher | `linkedin_publisher.py` | Quality gate, file-chooser media attach, humanized type, 4 themed slots |
| Gemini | `gemini_ai.py` | Web-only (`gemini.google.com`), shadow-DOM file inputs, stream-stability wait |
| Memory | `engagement_tracker.py` | SQLite dedup + daily/weekly caps + `daily_engagement_tracker.txt` |
| Pipeline | `live_persistent_curator.py` + rewriter/exporter | X.com → rewrite → `Posts/YYYY-MM-DD/.../Option_XX` |

**Live proof (tracker, 2026-08-11 14:21):** feed **20/20**, notifications **12/20**, inbox **2/25**, connections **20/20**. The loop is already running at daily cap.

That is the problem as much as the achievement. The next work should harden the live engine, not add more surface area on top of silent defects.

---

## 2. Skill compliance scorecard

### `browser-automation-stealth` — **partial (production path is the weak one)**

| Rule | Status | Where |
|---|---|---|
| `channel="chrome"` | Pass on agent/publisher; **fail on curators** | `live_persistent_curator.py`, `x_curator.py`, `live_browser_curator.py` launch raw Chromium |
| `--test-type` + `AutomationControlled` | Pass on agent; **missing `--test-type` on curators** | X launch args |
| Visible / `headless=False` | Default good; `--headless` still exists | Agent CLI + collector |
| CDP `Browser.setWindowBounds(maximized)` | **Missing on the production agent** | Present in `run_acceptance.py` / debug scripts only |
| `page.bring_to_front()` before keystrokes | Inconsistent | Feed/Gemini yes; publisher + inbox + network often no |
| Don't rely on `--start-maximized` | Violated | Several launchers still treat it as sufficient |
| Fingerprint consistency | **Fail** | Hardcoded `Chrome/120` UA against a live branded Chrome (likely 130+) + fixed 1440×900 viewport |

### `gemini-web-automation` — **mostly implemented, then sabotaged by the agent**

| Rule | Status | Where |
|---|---|---|
| Zero API keys for comments/replies | Pass in `gemini_ai.py` | Explicitly refuses API fallback |
| Zero API keys for **post rewrite** | **Fail** | `linkedin_rewriter.py` + `config.gemini_api_key` + README still teach API keys |
| Shadow-DOM `input[type=file]` scan | Pass | Approach A in `generate_content_web` |
| `expect_file_chooser()` on Add/Upload | **Missing on Gemini** | Only publisher uses it |
| `h1:has-text('Couldn')` guard | Pass | Load + login paths |
| 2× stability checks (~3.0s) | Pass | `stable_checks >= 2` at 1.5s |
| Long-lived Gemini tab | **Fail** | Agent closes `context.pages[1:]` after feed — kills the Gemini tab every cycle |

### `linkedin-engagement-engines` — **the three rules that defined the last session are not fully in production**

| Rule | Status | Where |
|---|---|---|
| Body-level editors (`self.page`, never `card`) | Partial | Feed still queries the card first, page only as fallback |
| Notification `el.tagName` HTMLElement filter | **Missing in production** | Exists in debug/DOM probes, not in `linkedin_notifications.py` |
| Typo rate ≤ 1.5%, adjacent QWERTY | **Missing** | `human_type_with_mistakes` types perfectly |
| Space pause 4% × 0.5–1.2s | **Wrong** | Implemented as 3% × 0.3–0.8s |

### `data-engineering-data-pipeline` — **gates exist, data layer is leaky**

| Rule | Status | Where |
|---|---|---|
| AST parse of pipeline modules | Pass | All 11+ modules parse |
| Import gate | Would fail on publisher | `Union` used, never imported |
| `--live` required for real clicks | Pass | `preproduction = not args.live` |
| Dry-run must not mutate production state | **Fail** | Dry-run publish still `mark_engaged`s the option + slot |
| Audit `⚠️` in *this* project's log | **Fail** | `engine_log.txt` is a leftover Coinglass/Binance trading log |

---

## 3. Defects to fix before any new feature

These are ordered by “will this get the account restricted, republish junk, or crash a live cycle?”

### P0 — correctness / account safety

1. **Dry-run consumes the post queue**  
   `_ensure_todays_posts_and_publish_due_slots` marks `publisher_slot` + `published_option` whenever `publish_post_option` returns True. Dry-run *always* returns True after the quality gate. One preprod cycle burns the day's content.

2. **Publish records expire in 24h**  
   `published_option` / `publisher_slot` / `connection_request_weekly_limit` are not in `COOLDOWN`, so they default to 86400s. Already-published options become eligible again tomorrow. The weekly invite hold lifts after one day.

3. **Night-time slot burst**  
   Slots are `if now.hour >= slot.hour`. A 21:00 start fires slots 1–4 in one cycle. Four posts in ~2 minutes is a restriction signature.

4. **Gemini tab is murdered every cycle**  
   After feed, the agent closes every page except `pages[0]`. Gemini lives on a second tab. Notifications/inbox then reopen Gemini, re-hit Google bot-detection, and lose image/session warmth.

5. **Unbounded likes after the comment cap**  
   Once `feed_comment` hits 20, the loop `continue`s without incrementing `engaged`. It will like every remaining card in the viewport. Combined with today's 20/20 comments + 20/20 connects, that is a lot of graph activity.

6. **`linkedin_publisher.ContentQualityGate` crashes on import**  
   `Optional[Union[Path, list[Path]]]` but `Union` is never imported. First publish after a cold start dies in class body evaluation.

7. **`x_curator.search_and_curate_posts` crashes**  
   `settings.topic_search_map` does not exist on `Settings`. Auto-curator / collector path is broken.

8. **Shared Chrome profile for LinkedIn + X**  
   `settings.user_data_dir == settings.linkedin_user_data_dir == user_data/`. Cookies, logins, and fingerprint mix. X login challenges can poison the LinkedIn session.

9. **Inbox “You:” skip is broken**  
   `"\\\\nyou:" in card_text` looks for the literal two-char sequence `\n` + `you:` (backslash + n), not a newline. Last-speaker detection depends on the other two weaker checks.

### P1 — stealth / skill drift (the last session's unfinished work)

10. **Production launch is not skill-compliant**  
    `LinkedIn_Auto_Agent.run_forever` / `run_cycle` never call CDP maximize, pin viewport to 1440×900, and pin UA to Chrome/120. Acceptance scripts already do this correctly — production does not.

11. **Human typing is too clean**  
    Recalibrate `human_type_with_mistakes` to the skill: ≤1.5% typos, adjacent QWERTY only, 4% space pauses of 0.5–1.2s, plus rare backspace-correct. Right now it is a metronome.

12. **Notification cards are unfiltered**  
    Broad `[class*='nt-card']` will again hit SVG/text nodes (`Node is not an HTMLElement`) the moment LinkedIn shuffles the DOM. The skill exists because this already burned a cycle.

13. **Comment editor scoped to the card**  
    LinkedIn injects TipTap at `<body>`. Card-first search is the exact failure mode the engagement skill documents.

14. **Gemini image attach missing file-chooser path**  
    Approach B clicks Add/Upload but never wraps it in `expect_file_chooser()`. Images get deleted in `finally` even when attach failed.

15. **Post rewriter still uses the Gemini API**  
    Violates Zero-API policy. Template fallback is generic (“Most professionals completely misunderstand {topic}”) and will publish as Karanbir if the API key is absent.

16. **Curators launch unbranded Chromium**  
    Highest-risk bot surface on X, which is stricter than LinkedIn.

### P2 — architecture / hygiene

17. **Three overlapping X curators** (`live_persistent_curator.py`, `x_curator.py`, `live_browser_curator.py`) with divergent login, scoring, and export signatures. `live_browser_curator.export_post(idx, post_data, rewritten)` does not match `PostExporter.export_post(topic, option_index, ...)`.

18. **Config search filters are dead**  
    `min_likes`, `min_retweets`, `x_search_filters` (`min_faves:30 ...`) are never applied by the persistent curator. Ranking is “whatever loaded in 6 `scrollBy(1000)` calls.”

19. **~25 debug/probe/inspect/agentic scripts in repo root** plus a crypto `engine_log.txt`. Noise hides real ⚠️s. Pipeline skill cannot be executed as written.

20. **Windows-only process kill**  
    `Get-CimInstance Win32_Process` in `run_forever` is a no-op (or error) on Linux/Arena. Stale `SingletonLock` deletion is the only recovery, and that corrupts profiles.

21. **`show_stats.py` is stale** (feed cap printed as 15 vs 20). `test_e2e_verification_protocol.py` still reads `ai.api_keys`. README still documents `GEMINI_API_KEY`.

22. **Quality gate CTA is a no-op**  
    It prints “Appending engagement question CTA” and never appends.

23. **No circuit breaker**  
    Consecutive `TargetClosedError` / checkpoint / Gemini-block just log ⚠️ and start the next cycle. After a checkpoint, the right move is sleep-for-hours, not retry.

24. **`requirements.txt` incomplete**  
    `x_curator` imports `PIL` but Pillow is not listed.

---

## 4. Recommended next build (highest leverage first)

Do these in order. Each item is one focused change-set.

### Sprint A — Make the live loop safe (do this next)

1. **Engagement ledger v2**  
   - Permanent types: `published_option`, `publisher_slot` (cooldown = forever).  
   - `connection_request_weekly_limit` cooldown = 7 days.  
   - Never `mark_engaged` on dry-run.  
   - Slot windows: fire only inside `[hour, hour+2)`, never “all due slots at 21:00.”  
   - Daily **like** cap (e.g. 40) independent of comments.  
   - Skip own posts, promoted, “Suggested,” company pages on feed.

2. **Gemini as a pinned worker tab**  
   - Create once, reuse, never close in the `pages[1:]` sweeper (whitelist `gemini.google.com`).  
   - Click “New chat” before every generation (stops context bleed across feed/notif/inbox).  
   - Add `expect_file_chooser()` as Approach B.  
   - Delete temp images only after a successful model-response.  
   - Move `linkedin_rewriter` onto `generate_content_web` and delete the API path.

3. **Production stealth parity with the skill**  
   Single `launch_stealth_chrome()` helper used by agent, publisher, curator:  
   `channel="chrome"` · `--test-type` · `AutomationControlled` · **no fixed viewport** · CDP maximize · `bring_to_front` · UA read from the real browser (`navigator.userAgent`) instead of Chrome/120 · init script to hide `navigator.webdriver` / consistent `languages` / `plugins`.  
   Separate `user_data/linkedin/` and `user_data/x/`.

4. **Typing + DOM skill lock-in**  
   Recalibrate `human_type_with_mistakes`.  
   Feed/notif/inbox editors: **page-scoped, last visible**.  
   Notification cards: `tagName` ∈ `{ARTICLE, DIV, LI, SECTION}` before `inner_text()`.

### Sprint B — Pipeline that can be trusted

5. **One curator, real filters**  
   Merge the three X curators. Apply `settings.x_search_filters` + `min_engagement_score`. Dedup by tweet URL against previously exported `source_info.json`. Keep image-required, but parse `K`/`M` correctly (persistent curator currently turns `1.2K` into `1` via `float('1.2K')` except when it doesn't crash).

6. **Publisher confirmation**  
   After Post click: wait for “Post successful” toast **or** the text to appear on `/in/me/recent-activity/`. Screenshot + write `publish_receipt.json` into the Option folder. Only then mark published.

7. **Observability that matches the pipeline skill**  
   Replace `engine_log.txt` with a real rotating agent log.  
   Add `scripts/preflight.py`: AST parse + import check + skill-assert (channel, CDP maximize, no `GEMINI_API_KEY` path).  
   Move debug/probe/inspect scripts to `tools/`. Align `show_stats` caps with `DAILY_CAPS`.

### Sprint C — Capabilities worth adding (only after A+B)

8. **Working-hours brain**  
   No cycles 00:00–07:30 local. Morning warm-up is feed-browse + 1–2 likes only. Connections only 10:00–17:00 weekdays. This is the single highest-ROI anti-restrict change after Sprint A.

9. **Comment-quality critic**  
   Second Gemini pass: “Does this sound like Karanbir, ≤2 sentences, no name, no ‘Great post’?” Reject and regenerate once. Today's 20 comments/day makes one robotic phrase very visible.

10. **Own-thread reply engine**  
    Notifications already open threads. Add a dedicated “replies to *my* comments / *my* posts” path with a tighter prompt and a lower daily cap (5). This is how LinkedIn's algo actually rewards accounts.

11. **Personalized connection notes (opt-in, 2–3/day)**  
    Only for keyword-strong prospects. Generic Connect-without-note at 20/day is how weekly limits get hit — and today's tracker already sat at 20/20.

12. **Topic feedback loop**  
    Nightly scrape of post analytics (impressions / reactions on the 4 published slots) → write `analytics.json` → bias next day's curator topics and slot keywords. The slot scorer already wants `engagement_score`; feed it LinkedIn reality, not just X likes.

13. **Session doctor**  
    On checkpoint / “Couldn't sign you in” / authwall: freeze the loop, keep Chrome open, write `PAUSE_REQUIRED.txt`, do not relaunch. Manual-solve then `--resume`. Beats the current “log and continue.”

---

## 5. What I would *not* build yet

- Multi-account / multi-profile orchestration  
- Headless production mode  
- API Gemini “just in case”  
- Auto-follow, auto-endorse, profile-view blasting  
- CDP raw-protocol rewrite of the engines (the Playwright engines work; they need discipline, not a second stack)  
- More root-level `debug_*.py` / `analyze_*.py`

The agentic/CDP scripts (`agentic_cdp_control.py`, `multi_tab_cdp_agent.js`, etc.) were useful for DOM discovery. They should not become a parallel production runtime.

---

## 6. Suggested immediate next step

Implement **Sprint A items 1–4 as one hardening PR** on this branch:

`fix: engagement ledger, pinned Gemini tab, stealth launch helper, skill-accurate typing/DOM`

That PR makes the engine that already hit 20/20 today harder to detect, incapable of republishing or dry-run-burning the queue, and compliant with the four skills that are supposed to govern it.

After that, Sprint B (one curator + publish receipts + preflight), then working-hours + critic.
