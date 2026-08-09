from playwright.sync_api import sync_playwright
import time
import json

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir='user_data',
        channel='chrome',
        headless=False,
        args=['--start-maximized','--disable-blink-features=AutomationControlled','--test-type'],
        no_viewport=True
    )
    page = ctx.pages[0]
    
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
