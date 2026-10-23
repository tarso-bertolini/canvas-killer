"""Browser login: the student signs in to Canvas themselves.

canvas-killer never sees a password. It opens a real browser window with a
persistent profile, the student logs in there (SSO and two-factor included),
and once Canvas reports a signed-in user the cookies for the Canvas host are
saved to the session file. Later logins first try the saved profile without a
window, so a still-valid SSO session refreshes silently.
"""

import json
import time
import urllib.parse

from . import config

# Ask Canvas itself, from inside the page, who is signed in: works on every
# Canvas version and theme, unlike reading page globals.
SIGNED_IN_JS = """async () => {
  try {
    const r = await fetch('/api/v1/users/self', {credentials: 'same-origin', headers: {Accept: 'application/json'}});
    if (!r.ok) return null;
    let t = await r.text();
    if (t.startsWith('while(1);')) t = t.slice(9);
    const u = JSON.parse(t);
    return u && u.id ? String(u.id) : null;
  } catch (e) { return null; }
}"""


def _launch(playwright, headless):
    """Prefer an installed Chrome or Edge; fall back to Playwright's Chromium."""
    errors = []
    for channel in ("chrome", "msedge", "chromium"):
        try:
            return playwright.chromium.launch_persistent_context(
                str(config.BROWSER_PROFILE), headless=headless, channel=channel,
                viewport=None if not headless else {"width": 1280, "height": 900})
        except Exception as e:
            errors.append("%s: %s" % (channel, str(e).splitlines()[0]))
    raise RuntimeError("no usable browser found. Run `ck install-browser`.\n  " + "\n  ".join(errors))


def _host_cookies(context, host):
    keep = []
    for c in context.cookies():
        domain = c.get("domain", "").lstrip(".")
        if host == domain or host.endswith("." + domain):
            keep.append({k: c[k] for k in ("name", "value", "domain", "path", "expires", "secure", "httpOnly")})
    return keep


def _signed_in_user(context, host):
    for page in context.pages:
        url = urllib.parse.urlparse(page.url)
        if url.hostname != host or url.path.startswith("/login"):
            continue
        try:
            user_id = page.evaluate(SIGNED_IN_JS)
        except Exception:  # the page is mid-navigation
            continue
        if user_id:
            return user_id
    return None


def login(base_url, timeout_s=600, log=print):
    from playwright.sync_api import sync_playwright

    config.ensure_home()
    host = urllib.parse.urlparse(base_url).hostname
    with sync_playwright() as p:
        for headless in (True, False):
            context = _launch(p, headless)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(base_url + "/", wait_until="domcontentloaded")
            if not headless:
                log("A browser window is open at %s. Log in there (SSO and two-factor are fine); "
                    "this command waits up to %d minutes." % (base_url, timeout_s // 60))
            # a silent SSO round trip (Canvas -> identity provider -> Canvas) takes a few seconds
            deadline = time.time() + (30 if headless else timeout_s)
            user_id, next_report = None, time.time() + 30
            while time.time() < deadline:
                user_id = _signed_in_user(context, host)
                if user_id:
                    break
                if not headless and time.time() >= next_report:
                    where = ", ".join(sorted({urllib.parse.urlparse(pg.url).hostname or "blank" for pg in context.pages}))
                    log("Still waiting for the Canvas login (browser is at: %s)" % where)
                    next_report = time.time() + 30
                time.sleep(2)
            if user_id:
                cookies = _host_cookies(context, host)
                context.close()
                session = {"base_url": base_url, "user_id": user_id, "saved_at": int(time.time()), "cookies": cookies}
                config.write_private(config.SESSION_FILE, json.dumps(session, indent=2))
                log("Signed in as Canvas user %s%s." % (user_id, " (saved session reused)" if headless else ""))
                return user_id
            context.close()
    raise TimeoutError("no Canvas login within %d minutes" % (timeout_s // 60))


def logout():
    """Forget the saved session and the browser profile."""
    import shutil

    if config.SESSION_FILE.exists():
        config.SESSION_FILE.unlink()
    shutil.rmtree(config.BROWSER_PROFILE, ignore_errors=True)
