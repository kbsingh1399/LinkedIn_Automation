import json
from pathlib import Path
from typing import Dict, List, Any
from config import settings

class PostAuditor:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or settings.output_dir

    def audit_post_option(self, option_dir: Path) -> Dict[str, Any]:
        """Audits a single post option for text quality, media presence, and topic correlation."""
        source_json = option_dir / "source_info.json"
        post_txt = option_dir / "linkedin_post.txt"
        media_dir = option_dir / "media"

        audit = {
            "path": str(option_dir.resolve()),
            "status": "APPROVED",
            "score": 100,
            "issues": [],
            "correlation_analysis": ""
        }

        if not source_json.exists() or not post_txt.exists():
            audit["status"] = "REJECTED"
            audit["score"] = 0
            audit["issues"].append("Missing post text or source_info.json metadata.")
            return audit

        try:
            meta = json.loads(source_json.read_text(encoding="utf-8"))
            text = post_txt.read_text(encoding="utf-8")
        except Exception as e:
            audit["status"] = "REJECTED"
            audit["score"] = 0
            audit["issues"].append(f"Failed to read post content: {e}")
            return audit

        topic = meta.get("topic", "").lower()
        raw_text = meta.get("raw_text", "").lower()
        author = meta.get("author", "")

        # 1. Check media presence
        media_files = list(media_dir.glob("*")) if media_dir.exists() else []
        valid_media = [f for f in media_files if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]

        if not valid_media:
            audit["score"] -= 40
            audit["issues"].append("No valid attached image file found in media/.")
            audit["status"] = "NEEDS_REVIEW"

        # 2. Check text correlation with topic
        topic_keywords = [w for w in topic.replace("-", " ").split() if len(w) > 3]
        text_matches = [w for w in topic_keywords if w in text.lower() or w in raw_text]

        if topic_keywords and not text_matches:
            audit["score"] -= 30
            audit["issues"].append(f"Text content has low keyword correlation with topic '{topic}'.")
            audit["status"] = "NEEDS_REVIEW"

        # 3. Check text length and quality
        if len(text.strip()) < 100:
            audit["score"] -= 20
            audit["issues"].append("LinkedIn rewritten post copy is too short (< 100 chars).")
            audit["status"] = "NEEDS_REVIEW"

        # Correlation verdict synthesis
        if audit["score"] >= 80:
            audit["correlation_analysis"] = f"✅ High correlation between topic '{topic}', original tweet by {author}, and attached visual media ({len(valid_media)} image)."
        else:
            audit["correlation_analysis"] = f"⚠️ Quality review flagged issues: {', '.join(audit['issues'])}"

        return audit

    def audit_all_posts(self, date_str: str = None) -> List[Dict[str, Any]]:
        """Audits all post directories under Posts/date_str."""
        if not date_str:
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")

        day_dir = self.base_dir / date_str
        if not day_dir.exists():
            print(f"⚠️ Directory {day_dir} does not exist.")
            return []

        results = []
        for topic_dir in day_dir.iterdir():
            if topic_dir.is_dir():
                for option_dir in topic_dir.iterdir():
                    if option_dir.is_dir() and option_dir.name.startswith("Option_"):
                        audit_res = self.audit_post_option(option_dir)
                        audit_res["topic"] = topic_dir.name
                        audit_res["option"] = option_dir.name
                        results.append(audit_res)

                        # Write audit result inside the option folder
                        audit_file = option_dir / "audit_result.json"
                        audit_file.write_text(json.dumps(audit_res, indent=2), encoding="utf-8")

        # Save summary report
        summary_file = day_dir / "audit_summary.json"
        summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

        return results
