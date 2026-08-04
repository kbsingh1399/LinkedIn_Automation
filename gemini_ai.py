import os
from typing import List, Optional

class GeminiAIClient:
    def __init__(self):
        # Gather all configured Gemini API keys from environment
        keys = []
        if os.getenv("GEMINI_API_KEY"):
            keys.append(os.getenv("GEMINI_API_KEY"))
        for i in range(1, 10):
            k = os.getenv(f"GEMINI_API_KEY_{i}")
            if k and k not in keys:
                keys.append(k)

        self.api_keys: List[str] = keys
        self.current_key_idx: int = 0

    def _get_active_key(self) -> Optional[str]:
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_idx % len(self.api_keys)]

    def _rotate_key(self):
        if self.api_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            print(f"🔄 Rotating to Gemini API Key #{self.current_key_idx + 1}")

    def generate_content(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        if not self.api_keys:
            return None

        attempts = len(self.api_keys)
        for _ in range(attempts):
            active_key = self._get_active_key()
            try:
                from google import genai
                client = genai.Client(api_key=active_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"{system_instruction}\n\n{prompt}".strip()
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"⚠️ Gemini API error (Key #{self.current_key_idx + 1}): {e}")
                self._rotate_key()

        return None

    def generate_feed_comment(self, post_text: str, author_name: str = "Author") -> str:
        prompt = f"""
You are an influential tech leader & software architect on LinkedIn.
Generate a concise, insightful, professional comment (2-3 sentences) replying to this post by {author_name}.

Post Content:
\"\"\"
{post_text}
\"\"\"

Requirements:
1. Add genuine professional value or a thought-provoking perspective.
2. Polite, constructive tone.
3. No generic fluff like "Great post!" or "Thanks for sharing!".
4. Return ONLY the comment text.
"""
        result = self.generate_content(prompt)
        if result:
            return result

        # Intelligent Fallback
        return f"Great perspective on this! The balance between clean architecture and operational execution is crucial for scaling systems effectively."

    def generate_notification_reply(self, notification_text: str, parent_comment: str = "") -> str:
        prompt = f"""
You are a senior tech professional on LinkedIn replying to a user's notification/comment reply.

Notification: {notification_text}
Comment Context: {parent_comment}

Write a friendly, insightful 1-2 sentence response. Keep it engaging and professional. Return ONLY the reply text.
"""
        result = self.generate_content(prompt)
        if result:
            return result

        return "Appreciate the feedback! Spot on regarding the implementation tradeoffs."

    def generate_inbox_reply(self, chat_history: str, partner_name: str = "Connection") -> str:
        prompt = f"""
You are Karanbir Singh, a software engineer & AI tech lead. Reply to this LinkedIn private message conversation with {partner_name}.

Recent Conversation History:
\"\"\"
{chat_history}
\"\"\"

Write a warm, concise, professional reply (1-2 sentences) maintaining business relationship context. Return ONLY the reply text.
"""
        result = self.generate_content(prompt)
        if result:
            return result

        return "Thanks for reaching out! Looking forward to keeping in touch. Have a great week ahead!"
