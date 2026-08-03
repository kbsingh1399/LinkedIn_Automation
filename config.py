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

settings = Settings()
