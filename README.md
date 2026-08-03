# LinkedIn Post Automation System

An automated Python system that curates viral & high-value posts from **X.com (Twitter)** based on custom topics, downloads media assets, rewrites text into engagement-optimized **LinkedIn post formats**, and organizes everything inside `Posts/`.

---

## 🌟 Features

- **X.com Post Curator**: Uses Playwright browser automation to search topics, scroll feeds, and capture top posts with media. **Enhanced**: Advanced X search filters (`min_faves`, `min_retweets`), engagement thresholding (likes/retweets), ranking by engagement score, and robust count parsing.
- **AI LinkedIn Rewriter**: Uses Google Gemini (or high-converting fallback prompts) to reformat posts with hooks, structured value bullets, calls to action, and hashtags. **Enhanced**: Viral hook templates (Question/Contrarian/Stat/Story/Authority), industry-specific bullet frameworks, niche hashtag generation, and richer prompts.
- **Structured Storage**: Organizes exported posts by date (`Posts/YYYY-MM-DD/Post_XX/`) with `.txt`, `.md`, source metadata, and downloaded high-res images.
- **Git & Arena.ai Sync**: Integrated with GitHub repo [`kbsingh1399/LinkedIn_Automation`](https://github.com/kbsingh1399/LinkedIn_Automation) for seamless multi-AI collaboration between Antigravity and Arena.ai.

---

## 🚀 Quick Start

### 1. Installation

Install required dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set Up API Key (Optional for AI Rewriting)

Set your Gemini API key:

```powershell
$env:GEMINI_API_KEY="your-gemini-api-key"
```

*(If omitted, the built-in structured template rewriter will be used as a fallback)*

---

## 💡 Usage

### Run Default Post Curation (4 Posts)

```bash
python LinkedIn_Post_Collector.py
```

### Run with Custom Topics & Headless Mode

```bash
python LinkedIn_Post_Collector.py --topics "AI Automation, Python, Growth Hacking" --count 4 --headless
```

### Run and Automatically Push to GitHub

```bash
python LinkedIn_Post_Collector.py --topics "AI, Tech Trends" --count 4 --push-git
```

---

## 📁 Output Directory Structure

```
LinkedIn_Automation/
├── Posts/
│   └── 2026-08-03/
│       ├── Post_01_AI_Automation/
│       │   ├── linkedin_post.txt
│       │   ├── linkedin_post.md
│       │   ├── source_info.json
│       │   └── media/
│       │       └── image_1.jpg
│       └── Post_02_Python/
│           └── ...
```

---

## 🔄 GitHub Synchronization (Arena.ai Collaboration)

Repository: [kbsingh1399/LinkedIn_Automation](https://github.com/kbsingh1399/LinkedIn_Automation)

To sync local changes with Arena.ai:

```bash
git add .
git commit -m "Update post generation pipeline"
git push origin main
```
