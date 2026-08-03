import os
from typing import Dict, Any

class LinkedInRewriter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def rewrite_for_linkedin(self, post_data: Dict[str, Any]) -> str:
        raw_text = post_data.get("raw_text", "")
        topic = post_data.get("topic", "Tech & Innovation")
        user = post_data.get("user", "Industry Insight")
        likes = post_data.get("likes", 0)
        retweets = post_data.get("retweets", 0)

        if self.api_key:
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                prompt = f"""
You are an expert LinkedIn ghostwriter specializing in viral, high-converting posts for {topic}.

Rewrite the following tweet into a professional, engagement-optimized LinkedIn post.

Topic: {topic}
Original Tweet Source: {user} (Original engagement: {likes} likes, {retweets} RTs)
Original Text:
\"\"\"
{raw_text}
\"\"\"

CRITICAL REQUIREMENTS FOR VIRAL HOOKS & INDUSTRY FORMATTING:
1. **Viral Hook Styles** (choose one fitting the content): 
   - Bold Question Hook: "What if [surprising insight]?"
   - Contrarian/Controversial Hook: "Most people get [topic] wrong..."
   - Story Hook: "Last week I discovered..."
   - Number/Stat Hook: "Here's the [X] that changed everything..."
   - Authority Hook: "As a [role/expert], here's what actually works..."
2. Short paragraphs (1-2 sentences max) with strategic line breaks.
3. 3-5 industry-specific bullet points with action-oriented insights or frameworks (use emojis sparingly: 🔥 💡 🚀).
4. Conversational professional tone. Add 1-2 relatable analogies if fitting.
5. Strong CTA: Ask a specific question to spark comments (e.g., "What's your biggest challenge with...?").
6. 4-6 trending + niche hashtags at the end (mix of broad + topic-specific).

Output ONLY the full rewritten post text. No intro, no code blocks, no extra explanations.
"""
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[LinkedInRewriter] Gemini API call failed: {e}. Falling back to enhanced template rewriter.")

        # Enhanced Fallback Template Rewriter with viral hooks and industry formatting
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        first_line = lines[0] if lines else raw_text[:80]

        # Generate viral-style hooks
        hook_styles = [
            f"What if the key to mastering {topic} isn't what you think?",
            f"Most professionals completely misunderstand {topic} — here's the truth.",
            f"🚀 I just discovered something game-changing about {topic}...",
            f"The {len(raw_text.split())} word insight that boosted my {topic} results by 3x.",
            f"Here's the exact framework top {topic} leaders use (that no one talks about)."
        ]
        hook = hook_styles[hash(first_line) % len(hook_styles)]

        body_lines = lines[1:6] if len(lines) > 1 else [raw_text]
        body = "\n\n".join(body_lines)

        # Industry-specific formatting with actionable bullets
        hashtag_slug = "".join(e for e in topic if e.isalnum()).lower()
        industry_hashtags = {
            "aiautomation": "#AIAutomation #FutureOfWork",
            "pythondevelopment": "#Python #DevOps",
            "techtrends": "#TechTrends #Innovation",
            "productivitytools": "#Productivity #WorkflowHacks"
        }
        base_hashtags = industry_hashtags.get(hashtag_slug, f"#{hashtag_slug}")
        hashtags = f"{base_hashtags} #LinkedInGrowth #ContentStrategy #ViralPosts #Automation"

        return f"""{hook}

{body}

💡 Here's why this changes everything for {topic} professionals:

• Master the fundamentals first — automation without strategy is just noise.
• Focus on high-ROI actions: Prioritize 20% of tasks delivering 80% results.
• Leverage data-driven insights to iterate faster than competitors.
• Build systems, not just processes — scalability comes from repeatable frameworks.
• Always test, measure, and refine based on real engagement metrics.

What’s the #1 challenge you’re facing with {topic} right now? Drop it in the comments — let’s solve it together! 👇

{hashtags}"""
