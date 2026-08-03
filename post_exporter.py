import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
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

        # 2. Download media directly from tweet
        media_urls = original_post.get("media_urls", [])
        downloaded_media = []
        if media_urls:
            downloaded_media = XCurator.download_media(media_urls, media_dir)

        # 3. Save source metadata
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
            "has_images": len(downloaded_media) > 0,
            "downloaded_media": [str(m.name) for m in downloaded_media]
        }
        meta_path.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

        return post_dir
