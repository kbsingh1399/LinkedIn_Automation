import asyncio
from pathlib import Path
from linkedin_publisher import LinkedInPublisher

async def main():
    opt_dir = Path("Posts/2026-08-04/LLM_Token_Cost_Explosion_and_Semantic_Caching/Option_01")
    print(f"🧪 Testing LinkedIn Publisher for package: {opt_dir.resolve()}")
    publisher = LinkedInPublisher(headless=False)
    res = await publisher.publish_post_option(opt_dir, dry_run=True)
    print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(main())
