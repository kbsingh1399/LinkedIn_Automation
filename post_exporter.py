import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont
from config import settings
from x_curator import XCurator

class PostExporter:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or settings.output_dir

    def export_post(self, post_index: int, original_post: Dict[str, Any], rewritten_text: str) -> Path:
        today_str = datetime.now().strftime("%Y-%m-%d")
        topic = original_post.get('topic', 'General').replace(' ', '_')
        folder_name = f"Post_{post_index:02d}_{topic}"
        post_dir = self.base_dir / today_str / folder_name
        post_dir.mkdir(parents=True, exist_ok=True)
        media_dir = post_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save formatted LinkedIn post text & markdown
        txt_path = post_dir / "linkedin_post.txt"
        txt_path.write_text(rewritten_text, encoding="utf-8")

        md_path = post_dir / "linkedin_post.md"
        md_content = f"# LinkedIn Post ({original_post.get('topic', 'General')})\n\n{rewritten_text}\n\n---\n*Original Source: [{original_post.get('user', 'X.com')}]({original_post.get('url', '')})*"
        md_path.write_text(md_content, encoding="utf-8")

        # 2. Download media from tweet if available
        media_urls = original_post.get("media_urls", [])
        downloaded_media = []
        if media_urls:
            downloaded_media = XCurator.download_media(media_urls, media_dir)

        # 3. Always guarantee a clean, generic high-res tech graphic banner in media/
        banner_path = media_dir / "generic_tech_banner.png"
        self.generate_generic_tech_graphic(
            topic=original_post.get("topic", "Tech Insights"),
            summary_text=original_post.get("raw_text", "")[:120],
            save_path=banner_path
        )
        if not downloaded_media:
            # Copy/link generic banner as image_1.png
            img1_path = media_dir / "image_1.png"
            img1_path.write_bytes(banner_path.read_bytes())

        # 4. Save metadata
        meta_path = post_dir / "source_info.json"
        meta_data = {
            "timestamp": datetime.now().isoformat(),
            "topic": original_post.get("topic"),
            "author": original_post.get("user"),
            "original_url": original_post.get("url"),
            "likes": original_post.get("likes", 0),
            "retweets": original_post.get("retweets", 0),
            "engagement_score": original_post.get("engagement_score", 0),
            "raw_text": original_post.get("raw_text"),
            "media_urls": media_urls,
            "has_images": True,
            "generated_banner": str(banner_path.name)
        }
        meta_path.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

        return post_dir

    @staticmethod
    def generate_generic_tech_graphic(topic: str, summary_text: str, save_path: Path):
        """Generates a professional, generic dark-mode 1200x630 visual banner for LinkedIn (No personal photos)."""
        width, height = 1200, 630
        img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Dark slate background
        draw = ImageDraw.Draw(img)

        # Draw futuristic gradient accent bar on top
        for x in range(width):
            r = int(14 + (99 - 14) * (x / width))
            g = int(165 + (102 - 165) * (x / width))
            b = int(233 + (241 - 233) * (x / width))
            draw.line([(x, 0), (x, 12)], fill=(r, g, b))

        # Try loading standard font or default
        try:
            title_font = ImageFont.truetype("arial.ttf", 46)
            subtitle_font = ImageFont.truetype("arial.ttf", 26)
            badge_font = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            badge_font = ImageFont.load_default()

        # Draw Topic Badge Pill
        badge_text = f"  {topic.upper()} • TECH DIGEST  "
        draw.rectangle([(80, 70), (420, 110)], fill=(30, 41, 59), outline=(56, 189, 248), width=2)
        draw.text((95, 80), badge_text, fill=(56, 189, 248), font=badge_font)

        # Main Title Headline
        headline = f"Key Insights & Future Trends in {topic}"
        draw.text((80, 150), headline, fill=(248, 250, 252), font=title_font)

        # Clean Summary Box
        draw.rectangle([(80, 240), (1120, 500)], fill=(30, 41, 59), outline=(71, 85, 105), width=1)

        # Wrap summary text into multi-line preview
        words = summary_text.replace("\n", " ").split()
        lines = []
        curr = ""
        for word in words:
            if len(curr + " " + word) < 65:
                curr += " " + word
            else:
                lines.append(curr.strip())
                curr = word
        if curr:
            lines.append(curr.strip())

        y_offset = 270
        for line in lines[:5]:
            draw.text((120, y_offset), f"• {line}", fill=(226, 232, 240), font=subtitle_font)
            y_offset += 42

        # Branding Footer
        draw.text((80, 550), "LINKEDIN GROWTH & AUTOMATION INSIGHTS", fill=(148, 163, 184), font=badge_font)

        img.save(save_path)
