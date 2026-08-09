from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir='user_data',
        channel='chrome',
        headless=False,
        args=['--start-maximized','--disable-blink-features=AutomationControlled','--test-type'],
        no_viewport=True
    )
    page = ctx.pages[0]
    
    # === FEED ===
    print('\n[FEED] Navigating to feed...')
    page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded')
    time.sleep(3)
    
    # Click comment button to open editor
    btn = page.query_selector('button[aria-label="Comment"]')
    if btn:
        btn.click()
        time.sleep(2)
        
        # Type into the editor to enable the post button
        editor = page.query_selector("div.ql-editor[contenteditable='true']")
        if not editor:
            editor = page.query_selector("div[contenteditable='true']")
        if editor:
            editor.type("Test comment")
            time.sleep(1)
        
        buttons = page.evaluate('''() => {
            return Array.from(document.querySelectorAll("button")).map(b => ({
                text: b.innerText.trim().substring(0,40),
                aria: b.getAttribute("aria-label") || "",
                cls: b.className.substring(0,80),
                disabled: b.disabled,
                visible: b.offsetParent !== null && b.offsetWidth > 0,
                type: b.type
            })).filter(b => b.visible && (
                b.aria.toLowerCase().includes("post") ||
                b.aria.toLowerCase().includes("comment") ||
                b.text.toLowerCase().includes("post") ||
                b.cls.includes("submit")
            ))
        }''')
        print('=== FEED BUTTONS ===')
        for b in buttons:
            print(f"  aria={b['aria']!r} text={b['text']!r} disabled={b['disabled']} cls={b['cls']!r}")
    
    # === INBOX ===
    print('\n[INBOX] Navigating to inbox...')
    page.goto('https://www.linkedin.com/messaging/', wait_until='domcontentloaded')
    time.sleep(3)
    
    conv = page.query_selector("li.msg-conversations-container__convo-item")
    if conv:
        conv.click()
        time.sleep(2)
        
        # Type into the editor to enable the send button
        editor = page.query_selector("div.msg-form__contenteditable[contenteditable='true']")
        if editor:
            editor.type("Test message")
            time.sleep(1)
            
        buttons = page.evaluate('''() => {
            return Array.from(document.querySelectorAll("button")).map(b => ({
                text: b.innerText.trim().substring(0,40),
                aria: b.getAttribute("aria-label") || "",
                cls: b.className.substring(0,80),
                disabled: b.disabled,
                visible: b.offsetParent !== null && b.offsetWidth > 0,
                type: b.type
            })).filter(b => b.visible && (
                b.aria.toLowerCase().includes("send") ||
                b.text.toLowerCase().includes("send") ||
                b.cls.includes("send")
            ))
        }''')
        print('=== INBOX BUTTONS ===')
        for b in buttons:
            print(f"  aria={b['aria']!r} text={b['text']!r} disabled={b['disabled']} cls={b['cls']!r}")
    
    ctx.close()
