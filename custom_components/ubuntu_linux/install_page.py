"""Short-lived installer command page with a real clipboard button.

The URL is a bearer capability: it contains a random enrollment token and only
exposes the *public* SSH key and the remote installation command. No private
keys are stored or served by this endpoint.
"""
from datetime import timedelta
from html import escape
import secrets
from time import monotonic

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN

STORE_KEY = f"{DOMAIN}_install_pages"
VIEW_KEY = f"{DOMAIN}_install_view_registered"
TOKEN_LIFETIME = timedelta(minutes=30).total_seconds()


def register_install_view(hass):
    """Register the endpoint once, including during initial config flow setup."""
    if hass.data.get(VIEW_KEY):
        return
    hass.http.register_view(UbuntuInstallPage(hass))
    hass.data[VIEW_KEY] = True


def create_install_page(hass, command):
    """Register a command in memory and return an unguessable URL path."""
    store = hass.data.setdefault(STORE_KEY, {})
    now = monotonic()
    for key, record in list(store.items()):
        if record["expires"] <= now:
            store.pop(key, None)
    token = secrets.token_urlsafe(32)
    store[token] = {"command": command, "expires": now + TOKEN_LIFETIME}
    return f"/api/ubuntu_linux/install/{token}", token


def remove_install_page(hass, token):
    """Revoke a command page when configuration finishes."""
    hass.data.get(STORE_KEY, {}).pop(token, None)


class UbuntuInstallPage(HomeAssistantView):
    """Minimal standalone install-command page accessible via an expiring token."""

    url = "/api/ubuntu_linux/install/{token}"
    name = "api:ubuntu_linux:install"
    requires_auth = False

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request, token):
        record = self.hass.data.get(STORE_KEY, {}).get(token)
        if record is None or record["expires"] <= monotonic():
            self.hass.data.get(STORE_KEY, {}).pop(token, None)
            raise web.HTTPNotFound(text="Installation link expired. Start setup again.")

        nonce = secrets.token_urlsafe(16)
        command = escape(record["command"])
        html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ubuntu Linux SSH — Install monitoring</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ margin: 0; background: #f5f5f5; color: #222; }}
main {{ box-sizing: border-box; margin: 6vh auto; max-width: 760px;
  padding: 28px; border-radius: 16px; background: white;
  box-shadow: 0 4px 24px #0001; }}
h1 {{ font-size: 1.4rem; margin-top: 0; }}
p {{ line-height: 1.6; }}
pre {{ overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere;
  background: #f0f2f5; color: #18212b; padding: 20px; border-radius: 8px;
  user-select: all; }}
button {{ cursor: pointer; font: inherit; color: white; background: #0879b9;
  padding: 12px 20px; border: none; border-radius: 8px; font-weight: 600; }}
button:hover {{ background: #076496; }}
#status {{ margin-left: 12px; }}
.note {{ font-size: .9rem; color: #606060; }}
@media (prefers-color-scheme: dark) {{
  body {{ background: #121212; color: #eee; }}
  main {{ background: #242424; box-shadow: none; }}
  pre {{ background: #333; color: #eee; }}
  .note {{ color: #bbb; }}
}}
</style>
</head>
<body>
<main>
<h1>Install Ubuntu monitoring</h1>
<p>Copy this command and run it on your Ubuntu server.</p>
<pre id="command">{command}</pre>
<button type="button" id="copy">Copy command</button>
<span id="status" role="status" aria-live="polite"></span>
<p class="note">After installation, return to the Home Assistant setup dialog and
click <strong>Submit</strong> to verify the SSH connection.</p>
<p class="note">This link expires after 30 minutes. It contains a public SSH key
only; the private key remains in Home Assistant.</p>
</main>
<script nonce="{nonce}">
document.getElementById("copy").addEventListener("click", async () => {{
  const text = document.getElementById("command").textContent;
  const status = document.getElementById("status");
  try {{
    if (!navigator.clipboard || !navigator.clipboard.writeText) {{
      throw new Error("Clipboard API is unavailable");
    }}
    await navigator.clipboard.writeText(text);
    status.textContent = "Copied to clipboard";
  }} catch (_) {{
    const range = document.createRange();
    range.selectNodeContents(document.getElementById("command"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = "Automatic copying is unavailable. Press Ctrl+C (or Cmd+C).";
  }}
}});
</script>
</body>
</html>"""
        return web.Response(
            text=html,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    f"default-src 'none'; script-src 'nonce-{nonce}'; "
                    "style-src 'unsafe-inline'; base-uri 'none'; "
                    "frame-ancestors 'none'; form-action 'none'"
                ),
            },
        )
