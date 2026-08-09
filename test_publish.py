import asyncio
from pathlib import Path
from linkedin_publisher import LinkedInPublisher

async def main():
    options = list(Path("Posts").glob("**/Option_*"))
    valid_options = [p for p in options if (p / "linkedin_post.txt").exists()]
    if not valid_options:
        print("❌ Error: No valid post option packages found in Posts/ directory.")
        return
    
    opt_dir = valid_options[0]
    print(f"🧪 Testing LinkedIn Publisher for package: {opt_dir.resolve()}")
    publisher = LinkedInPublisher(headless=False)
    res = await publisher.publish_post_option(opt_dir, dry_run=True)
    print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(main())
