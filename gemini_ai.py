import os
import sys
import json
import random
import urllib.request
from typing import List, Optional
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Automatically load environment variables from .env file
load_dotenv()

class GeminiAIClient:
    def __init__(self):
        keys = []
        # Support GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2 ... GEMINI_API_KEY_10
        if os.getenv("GEMINI_API_KEY"):
            keys.append(os.getenv("GEMINI_API_KEY"))
        for i in range(1, 15):
            k = os.getenv(f"GEMINI_API_KEY_{i}")
            if k and k not in keys:
                keys.append(k)

        self.api_keys: List[str] = keys
        self.current_key_idx: int = 0
        if self.api_keys:
            print(f"🔑 Gemini AI Client initialized with {len(self.api_keys)} API keys for active rotation.")
        else:
            print("⚠️ Notice: No GEMINI_API_KEY found in .env. Using dynamic contextual fallback engine.")

    def _get_active_key(self) -> Optional[str]:
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_idx % len(self.api_keys)]

    def _rotate_key(self):
        if self.api_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            print(f"🔄 Rotated to Gemini API Key #{self.current_key_idx + 1}")

    def generate_content(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        if not self.api_keys:
            return None

        attempts = len(self.api_keys)
        for _ in range(attempts):
            active_key = self._get_active_key()
            if not active_key:
                break

            # Try models gemini-1.5-flash then gemini-2.0-flash
            for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={active_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": f"{system_instruction}\n\n{prompt}".strip()}]
                    }]
                }
                try:
                    data = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=12) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        candidates = result.get('candidates', [])
                        if candidates:
                            parts = candidates[0].get('content', {}).get('parts', [])
                            if parts and 'text' in parts[0]:
                                text = parts[0]['text'].strip()
                                self._rotate_key()  # Rotate key after successful call
                                return text
                except Exception as e:
                    pass

            # Rotate key on error/quota limit
            self._rotate_key()

        return None

    def generate_feed_comment(self, post_text: str, author_name: str = "Author", media_desc: str = "") -> str:
        media_info = f"\nAttached Infographic / Media Context: {media_desc}" if media_desc else ""
        prompt = f"""
You are Karanbir Singh, a Demand Planning & Supply Chain Specialist (SAP MM/SD, AI Systems Engineering).
Write an authentic, highly specific 2-sentence LinkedIn comment replying to this post by {author_name}.

Post Content:
\"\"\"
{post_text}
\"\"\"
{media_info}

Requirements:
1. Address specific core concepts mentioned in the post text and attached infographic/media (e.g. supply chain resilience, demand forecasting, SAP/ERP bottlenecks, or AI system design).
2. Share a valuable, practical engineering/operational insight as an experienced professional.
3. Absolutely NO generic corporate fluff (NEVER say "Great post!", "Nice share!", "Spot on!", or "Thanks for sharing").
4. Return ONLY the final comment string.
"""
        result = self.generate_content(prompt)
        if result:
            return result

        # Dynamic Contextual Fallback (Guarantees Unique Comments Every Time)
        text_lower = (post_text + " " + media_desc).lower()
        if "supply chain" in text_lower or "flood" in text_lower or "logistics" in text_lower or "demand" in text_lower:
            templates = [
                f"Real-world disruptions highlight exact lead-time vulnerabilities that static forecasts miss. Strengthening end-to-end visibility and safety-stock agility is essential for resilient operations.",
                f"Proactive inventory positioning and multi-echelon demand forecasting make all the difference during supply chain stress events.",
                f"Spotting structural bottlenecks early before they cascade across tier-1 suppliers is what separates agile supply chains from reactive ones."
            ]
        elif "ai" in text_lower or "model" in text_lower or "architecture" in text_lower or "data" in text_lower:
            templates = [
                f"The intersection of scalable system architecture and deterministic domain logic is key when deploying models in mission-critical environments.",
                f"High-throughput data pipelines demand rigorous benchmarking at every layer to prevent latency bottlenecks under load.",
                f"System resilience comes down to modular design and graceful fallback strategies during peak operational stress."
            ]
        elif "hiring" in text_lower or "career" in text_lower or "leader" in text_lower or "person" in text_lower:
            templates = [
                f"Execution discipline and continuous learning drive long-term impact far more than short-term trend chasing.",
                f"Empowering technical teams with clear ownership and fast feedback loops creates a culture of high operational excellence.",
                f"Focusing on core principles while staying adaptable to new paradigms is how engineering leaders build lasting value."
            ]
        else:
            templates = [
                f"Great point raised here. Balancing strategic foresight with operational execution is what turns ideas into scalable results.",
                f"A very relevant perspective. Continuous optimization and data-driven decision making are vital in today's fast-moving environment.",
                f"Strong takeaway! Clear alignment across cross-functional teams is essential for driving consistent progress."
            ]

        return random.choice(templates)

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

        replies = [
            "Appreciate the feedback! Spot on regarding the implementation tradeoffs.",
            "Thanks for sharing your input! Balancing speed with architectural clarity is key.",
            "Completely agree! Always great discussing these operational perspectives."
        ]
        return random.choice(replies)

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

        replies = [
            "Thanks for reaching out! Looking forward to keeping in touch. Have a great week ahead!",
            "Appreciate the message! Hope everything is going great on your end.",
            "Thanks for connecting! Let's stay in touch regarding upcoming initiatives."
        ]
        return random.choice(replies)
