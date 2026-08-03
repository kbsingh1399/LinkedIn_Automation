import os
from typing import Dict, Any

class LinkedInRewriter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def rewrite_for_linkedin(self, post_data: Dict[str, Any]) -> str:
        raw_text = post_data.get("raw_text", "")
        topic = post_data.get("topic", "Tech & Innovation")
        user = post_data.get("user", "Industry Insight")

        if self.api_key:
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                prompt = f"""
You are an expert LinkedIn ghostwriter. Rewrite the following tweet into a high-performing, professional LinkedIn post.

Topic: {topic}
Original Tweet Source: {user}
Original Text:
\"\"\"
{raw_text}
\"\"\"

Requirements:
1. Strong, attention-grabbing opening hook line.
2. Short paragraphs with line breaks for optimal readability.
3. 3-5 bullet points expanding on the core insight or action steps.
4. Professional yet conversational tone.
5. Engaging call-to-action (CTA) asking for thoughts or comments.
6. 3-5 relevant, trending hashtags at the bottom.

Output ONLY the rewritten post text. Do not include markdown code block backticks around the post.
"""
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[LinkedInRewriter] Gemini API call failed: {e}. Falling back to template rewriter.")

        # Fallback template rewriter
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        hook = lines[0] if lines else f"Key insights on {topic}"
        body = "\n\n".join(lines[1:]) if len(lines) > 1 else raw_text

        hashtag_slug = "".join(e for e in topic if e.isalnum())
        hashtags = f"#{hashtag_slug} #Automation #TechTrends #Innovation #LinkedInGrowth"

        return f"""🚀 {hook}

Here is why this matters for the future of {topic}:

{body}

💡 Key Takeaways:
• Always innovate and automate repetitive workflows.
• Leverage real-time insights to stay ahead.
• Continuous learning is key in modern tech.

What are your thoughts on this? Let me know in the comments below! 👇

{hashtags}"""
