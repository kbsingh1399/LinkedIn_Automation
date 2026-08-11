"""
Skill-compliant Chrome launch helper (browser-automation-stealth).

Every production and tool launcher should go through launch_stealth_chrome():
  - channel=\"chrome\" (never raw Chromium)
  - --test-type + AutomationControlled
  - no fixed Playwright viewport
  - CDP Browser.setWindowBounds(maximized)
  - real browser user-agent (do not spoof Chrome/120)
  - init script hides navigator.webdriver
  - split profiles: user_data/linkedin vs user_data/x
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Sequence, Tuple

from playwright.async_api import BrowserContext, Page, Playwright

from config import find_free_port, resolve_linkedin_user_data_dir, resolve_x_user_data_dir

PINNED_TAB_HOSTS = (
    "gemini.google.com",
    "accounts.google.com",
)

STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch (e) {}
  try {
    if (!window.chrome) {
      window.chrome = { runtime: {} };
    }
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
  } catch (e) {}
})();
"""


def stealth_launch_args(debug_port: Optional[int] = None) -> list[str]:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--test-type",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--start-maximized",
    ]
    if debug_port:
        args.append(f"--remote-debugging-port={int(debug_port)}")
        args.append("--remote-debugging-address=127.0.0.1")
    return args


def resolve_profile_dir(
    profile: Literal["linkedin", "x"] = "linkedin",
    override: Optional[Path | str] = None,
) -> Path:
    if override:
        path = Path(override)
    elif profile == "x":
        path = resolve_x_user_data_dir()
    else:
        path = resolve_linkedin_user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_stale_locks(user_data_dir: Path) -> None:
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        sf = Path(user_data_dir) / lock_name
        if sf.exists():
            try:
                sf.unlink()
            except Exception:
                pass


def is_pinned_tab_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return any(host in lower for host in PINNED_TAB_HOSTS)


async def apply_stealth_window(context: BrowserContext, page: Page) -> None:
    """CDP-maximize, hide webdriver, bring tab to front."""
    try:
        await context.add_init_script(STEALTH_INIT_SCRIPT)
    except Exception:
        pass
    try:
        await page.add_init_script(STEALTH_INIT_SCRIPT)
    except Exception:
        pass
    try:
        cdp = await context.new_cdp_session(page)
        window_id = (await cdp.send("Browser.getWindowForTarget"))["windowId"]
        await cdp.send(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "maximized"}},
        )
        try:
            await cdp.detach()
        except Exception:
            pass
    except Exception as exc:
        print(f"⚠️ [Stealth] CDP maximize notice: {exc}")
    try:
        await page.bring_to_front()
    except Exception:
        pass


async def launch_stealth_chrome(
    playwright: Playwright,
    *,
    profile: Literal["linkedin", "x"] = "linkedin",
    user_data_dir: Optional[Path | str] = None,
    headless: bool = False,
    debug_port: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> Tuple[BrowserContext, Page]:
    """
    Launch a persistent branded Chrome context that matches the stealth skill.

    headless=True is ignored — visible Chrome is mandatory.
    """
    if headless:
        print("⚠️ [Stealth] headless=True ignored. Chrome stays visible per stealth skill.")
        headless = False

    data_dir = resolve_profile_dir(profile, user_data_dir)
    clear_stale_locks(data_dir)

    if debug_port is None:
        debug_port = find_free_port(19001 if profile == "linkedin" else 19101)

    args = stealth_launch_args(debug_port)
    if extra_args:
        args.extend(list(extra_args))

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(data_dir),
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=args,
        ignore_default_args=["--enable-automation"],
    )

    try:
        await context.add_init_script(STEALTH_INIT_SCRIPT)
    except Exception:
        pass

    page = context.pages[0] if context.pages else await context.new_page()
    await apply_stealth_window(context, page)

    try:
        ua = await page.evaluate("() => navigator.userAgent")
        print(f"🕵️ [Stealth] profile={profile} dir={data_dir}")
        print(f"🕵️ [Stealth] real UA: {ua}")
    except Exception:
        pass

    return context, page


def launch_stealth_chrome_sync(
    playwright,
    *,
    profile: Literal["linkedin", "x"] = "linkedin",
    user_data_dir: Optional[Path | str] = None,
    debug_port: Optional[int] = None,
):
    """Sync Playwright variant for probe/debug scripts."""
    data_dir = resolve_profile_dir(profile, user_data_dir)
    clear_stale_locks(data_dir)
    if debug_port is None:
        debug_port = find_free_port(19001 if profile == "linkedin" else 19101)
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(data_dir),
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=stealth_launch_args(debug_port),
        ignore_default_args=["--enable-automation"],
    )
    try:
        context.add_init_script(STEALTH_INIT_SCRIPT)
    except Exception:
        pass
    page = context.pages[0] if context.pages else context.new_page()
    try:
        cdp = context.new_cdp_session(page)
        window_id = cdp.send("Browser.getWindowForTarget")["windowId"]
        cdp.send(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "maximized"}},
        )
    except Exception as exc:
        print(f"⚠️ [Stealth] CDP maximize notice: {exc}")
    try:
        page.bring_to_front()
    except Exception:
        pass
    return context, page


async def close_auxiliary_tabs(context: BrowserContext, keep_page: Optional[Page] = None) -> None:
    """Close extra tabs but never Gemini / Google-accounts worker tabs."""
    for p_tab in list(context.pages):
        if keep_page is not None and p_tab == keep_page:
            continue
        if p_tab.is_closed():
            continue
        try:
            url = p_tab.url or ""
        except Exception:
            url = ""
        if is_pinned_tab_url(url):
            print(f"📌 [Tab Safety] Keeping pinned worker tab: {url}")
            continue
        if keep_page is None and context.pages and p_tab == context.pages[0]:
            continue
        try:
            print(f"🧹 [Tab Safety] Closing unwanted auxiliary tab: {url}")
            await p_tab.close()
        except Exception:
            pass
    if keep_page is not None and not keep_page.is_closed():
        try:
            await keep_page.bring_to_front()
        except Exception:
            pass
