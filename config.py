import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
POSTS_DIR = BASE_DIR / "Posts"
_LEGACY_USER_DATA = BASE_DIR / "user_data"
_LINKEDIN_USER_DATA = BASE_DIR / "user_data" / "linkedin"
_X_USER_DATA = BASE_DIR / "user_data" / "x"


def _looks_like_chrome_profile(path: Path) -> bool:
    return (path / "Local State").exists() or (path / "Default").exists()


def resolve_linkedin_user_data_dir() -> Path:
    """
    Prefer user_data/linkedin. If a live Chrome profile already sits at
    the legacy user_data/ root, keep using it so the logged-in session survives.
    """
    if _looks_like_chrome_profile(_LINKEDIN_USER_DATA):
        return _LINKEDIN_USER_DATA
    if _looks_like_chrome_profile(_LEGACY_USER_DATA):
        return _LEGACY_USER_DATA
    return _LINKEDIN_USER_DATA


def resolve_x_user_data_dir() -> Path:
    """Isolated X.com profile — never share cookies with the LinkedIn/Gemini session."""
    return _X_USER_DATA


class Settings(BaseModel):
    topics: list[str] = Field(
        default=[
            "S&OP leadership decision making",
            "Power BI meme Excel vs Power BI",
            "Python supply chain automation",
            "side project while working indie hacker",
            "AI agent fail AI vs Excel",
            "demand planning meme S&OP humor",
            "Power BI career advice data",
            "building in public reality corporate to indie",
            "Python career switch automation",
            "supply chain quant alternative data",
            "corporate product building innovation",
            "decision making under uncertainty supply chain"
        ]
    )
    posts_per_run: int = 4
    output_dir: Path = POSTS_DIR
    headless_browser: bool = False
    browser_timeout_ms: int = 30000

    # LinkedIn Automation Settings — split Chrome profiles
    user_data_dir: Path = Field(default_factory=resolve_linkedin_user_data_dir)
    linkedin_user_data_dir: Path = Field(default_factory=resolve_linkedin_user_data_dir)
    x_user_data_dir: Path = Field(default_factory=resolve_x_user_data_dir)
    linkedin_username: str = Field(default_factory=lambda: os.getenv("LINKEDIN_USERNAME", ""))
    linkedin_password: str = Field(default_factory=lambda: os.getenv("LINKEDIN_PASSWORD", ""))
    gemini_google_email: str = Field(default_factory=lambda: os.getenv("GEMINI_GOOGLE_EMAIL", ""))
    gemini_google_password: str = Field(default_factory=lambda: os.getenv("GEMINI_GOOGLE_PASSWORD", ""))

    # X.com Curation Settings
    x_username: str = Field(default_factory=lambda: os.getenv("X_USERNAME", ""))
    x_password: str = Field(default_factory=lambda: os.getenv("X_PASSWORD", ""))
    min_likes: int = 50
    min_retweets: int = 10
    min_engagement_score: int = 100
    x_search_filters: str = "min_faves:30 min_retweets:5 filter:safe -filter:replies lang:en"
    max_scrolls: int = 5
    topic_search_map: dict[str, str] = Field(default_factory=dict)

settings = Settings()

def find_free_port(preferred_port: int = 19001, max_attempts: int = 50) -> int:
    """Check if preferred_port is free. If occupied, scan for the next available port dynamically."""
    import socket
    for p in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
