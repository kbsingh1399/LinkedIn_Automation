from playwright.sync_api import sync_playwright
from utils.stealth_chrome import launch_stealth_chrome_sync
import time
import json

with sync_playwright() as p:
    ctx, page = launch_stealth_chrome_sync(p, profile="linkedin")
    
    print('\n[NOTIFICATIONS] Navigating to notifications...')
    page.goto('https://www.linkedin.com/notifications/', wait_until='domcontentloaded')
    time.sleep(4)
    
    output = page.evaluate('''() => {
      const data = {
        allReplyButtons: Array.from(document.querySelectorAll('button[aria-label="Reply"]')).map(btn => ({
          isVisible: btn.offsetWidth > 0 && btn.offsetHeight > 0,
          containerText: btn.closest('.comment-item, article, [role="article"]')?.innerText?.substring(0, 50) || 'No container'
        }))
      };
      return data;
    }''')
    
    print("OUTPUT:")
    print(json.dumps(output, indent=2))
    
    ctx.close()
