import os
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
POSTS_DIR = BASE_DIR / "Posts"

class Settings(BaseModel):
    topics: list[str] = Field(
        default=["AI Automation", "Python Development", "Tech Trends", "Productivity Tools"]
    )
    posts_per_run: int = 4
    output_dir: Path = POSTS_DIR
    headless_browser: bool = False
    browser_timeout_ms: int = 30000
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    # X.com curation enhancements
    min_likes: int = 50
    min_retweets: int = 10
    min_engagement_score: int = 100  # likes + retweets*2 threshold for ranking
    x_search_filters: str = "min_faves:30 min_retweets:5 filter:safe -filter:replies lang:en"  # Advanced search operators for viral content
    max_scrolls: int = 5
    user_data_dir: Path = BASE_DIR / "x_user_data"

settings = Settings()
