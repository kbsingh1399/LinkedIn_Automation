import sys
from pathlib import Path
from x_curator import XCurator

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

def main():
    posts_dir = Path("Posts/2026-08-04")
    if not posts_dir.exists():
        posts_dir = Path("Posts/2026-08-03")

    print(f"✨ Running Image Enhancement Engine on exported posts in '{posts_dir}'...\n")
    enhanced_count = 0
    for img_path in posts_dir.rglob("media/*"):
        if img_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            XCurator.enhance_image(img_path)
            enhanced_count += 1

    print(f"\n🎉 Enhanced quality for {enhanced_count} image assets!")

if __name__ == "__main__":
    main()
