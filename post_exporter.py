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
        folder_name = f"Post_{post_index:02d}_{original_post.get('topic', 'General').replace(' ', '_')}"
        post_dir = self.base_dir / today_str / folder_name
        post_dir.mkdir(parents=True, exist_ok=True)

        # Save formatted LinkedIn post
        txt_path = post_dir / "linkedin_post.txt"
        txt_path.write_text(rewritten_text, encoding="utf-8")

        md_path = post_dir / "linkedin_post.md"
        md_content = f"# LinkedIn Post ({original_post.get('topic', 'General')})\n\n{rewritten_text}\n\n---\n*Original Source: [{original_post.get('user', 'X.com')}]({original_post.get('url', '')})*"
        md_path.write_text(md_content, encoding="utf-8")

        # Save metadata
        meta_path = post_dir / "source_info.json"
        meta_data = {
            "timestamp": datetime.now().isoformat(),
            "topic": original_post.get("topic"),
            "author": original_post.get("user"),
            "original_url": original_post.get("url"),
            "raw_text": original_post.get("raw_text"),
            "media_urls": original_post.get("media_urls", [])
        }
        meta_path.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

        # Download media
        media_urls = original_post.get("media_urls", [])
        if media_urls:
            media_dir = post_dir / "media"
            XCurator.download_media(media_urls, media_dir)

        return post_dir
