---
name: browser-automation-stealth
description: Browser automation, stealth techniques, Chrome launch configuration, and CDP window controls.
triggers:
  - browser
  - playwright
  - stealth
  - chrome
  - launch_persistent_context
  - fullscreen
  - bring_to_front
  - LinkedIn_Auto_Agent.py
  - linkedin_publisher.py
---

# Browser Automation & Stealth Protocol

## 1. Window & Screen Control
- **OS Maximize**: Always call CDP `Browser.setWindowBounds` (`windowState: "maximized"`) right after creating the page context. `--start-maximized` alone is intercepted by Playwright.
- **Tab Focus**: Always call `await page.bring_to_front()` before initiating keystrokes or element interactions to prevent keystrokes landing on background tabs.

## 2. Chrome Launch Configuration
- **Browser Channel**: Always launch with `channel="chrome"`. Never launch raw unbranded Chromium (triggers Google sign-in bot detection).
- **Banner Suppression**: Include `--test-type` and `--disable-blink-features=AutomationControlled` in browser launch `args` to suppress unsupported flag warning bars.
- **Visible Mode**: Always run with `headless=False` so browser execution remains visible to the user.
