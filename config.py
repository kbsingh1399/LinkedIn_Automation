import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "LinkedIn Post Automation Engine"
    env: str = "production"

    # Base Paths
    BASE_DIR: Path = Path(__file__).parent.resolve()
    output_dir: Path = BASE_DIR / "Posts"
    user_data_dir: Path = BASE_DIR / "x_user_data"

    # X.com Credentials
    x_username: str = os.getenv("X_USERNAME", "Kbsingh1399")
    x_password: str = os.getenv("X_PASSWORD", "Lu$er2hero")

    # Scraper & Curation Settings
    max_scrolls: int = 6
    browser_timeout_ms: int = 30000

    # Topic-to-Keyword Search Mapping for X.com
    topic_search_map: dict = {
        "MCP Architecture": '"MCP architecture" diagram filter:images',
        "Multi-Agent Orchestration": 'LangGraph OR CrewAI OR AutoGen "architecture diagram"',
        "Agentic RAG": '"agentic RAG" flowchart OR "decision tree"',
        "AI Agent Memory Architecture": '"agent memory" architecture vector filter:images',
        "Python 3.13 No-GIL": '"free-threading" Python benchmark filter:images',
        "Asyncio vs Multiprocessing": 'asyncio "vs" multiprocessing cheat sheet',
        "FastAPI Async Benchmarks": 'FastAPI benchmark latency throughput table',
        "Vector DB Showdown": 'Pinecone OR Qdrant OR Weaviate "comparison table"',
        "LLMOps Observability": 'Langfuse OR LangSmith "observability stack" diagram',
        "RAG Pipeline Architecture": 'RAG pipeline "chunking" "embedding" architecture'
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()
