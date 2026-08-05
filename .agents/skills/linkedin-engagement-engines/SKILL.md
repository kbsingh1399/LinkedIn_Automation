---
name: linkedin-engagement-engines
description: Feed card parsing, body-level editor targeting, notification filtering, inbox message reply, and humanized typing rules.
triggers:
  - linkedin_feed
  - linkedin_notifications
  - linkedin_inbox
  - feed
  - notifications
  - inbox
  - comment
  - like
  - message
---

# LinkedIn Engagement Engines Protocol

## 1. DOM Hierarchy Scoping
- **Body-Level Editors**: LinkedIn injects comment textboxes and submit buttons at the `<body>` level, *outside* individual post card containers (`article` / `div.feed-shared-update-v2`). Always scope editor searches to `self.page`, never `card`.

## 2. Notification Filtering Guard
- **Element-Type Check**: Filter out SVG/text nodes from broad class selectors (`[class*='nt-card']`) using `card.evaluate("el => el.tagName")` to avoid `Node is not an HTMLElement` errors.

## 3. Humanized Typing Calibration
- **Mistake Rate**: Keep typo frequency at **1.5% max** (1-2 typos per full comment).
- **Adjacent Key Replacement**: Typos must replace target characters with adjacent QWERTY keyboard keys (`e` $\rightarrow$ `w`/`r`), never random letters.
- **Natural Delays**: Pause 0.5s - 1.2s only at space characters (` `) at a 4% frequency.
