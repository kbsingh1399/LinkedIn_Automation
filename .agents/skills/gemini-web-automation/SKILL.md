---
name: gemini-web-automation
description: Web-only Gemini AI automation, Shadow DOM image attachment, bot detection bypass, and prompt response streaming.
triggers:
  - gemini
  - gemini_ai.py
  - web-only
  - prompt
  - image attach
  - generate_content_web
---

# Gemini Web Automation Protocol

## 1. Zero API Keys Policy
- All AI content generation must strictly use the Web interface (`gemini.google.com`). Never fall back to Gemini API keys.

## 2. Robust Image Attachment
- **Shadow DOM Locator Scan**: Iterate over `locator("input[type='file']").all()` across all shadow roots to attach image files directly.
- **FileChooser Interceptor**: Use `expect_file_chooser()` while clicking upload/add buttons (`button[aria-label*='Add']`, `button[aria-label*='Upload']`) to bind files when pickers open.

## 3. Bot Detection Guard
- Immediately inspect for `h1:has-text('Couldn')` ("Couldn't sign you in") on Gemini tab load. If detected, halt cleanly with manual login instructions for the persistent Chrome profile.

## 4. Response Streaming Stability
- Monitor `model-response` text length across 2 consecutive stability checks (3.0 seconds total) before extracting generated text.
