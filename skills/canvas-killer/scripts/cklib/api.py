"""Minimal Canvas REST API client (standard library only).

Authenticates with either the cookies of a browser session (see session.py)
or a personal access token from the ``CANVAS_TOKEN`` environment variable.
Credentials are attached as *unredirected* headers, so urllib never forwards
them when Canvas redirects to another host (file downloads redirect to signed
storage URLs) or to its own login page.
"""

import json
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request

from . import config

USER_AGENT = "canvas-killer/0.1 (+https://github.com/tarso-bertolini/canvas-killer)"


class CanvasError(Exception):
    pass


class SessionExpired(CanvasError):
    pass


def _next_link(link_header):
    for part in (link_header or "").split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"', part)
        if m:
            return m.group(1)
    return None


def probe(base_url):
    """Check, without credentials, that base_url serves the Canvas API.

    An anonymous call to /api/v1/users/self answers 401 with a JSON error on
    any Canvas instance, which tells a Canvas apart from a typo'd address.
    """
    req = urllib.request.Request(base_url + "/api/v1/users/self",
                                 headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        body = e.read(2000).decode("utf-8", "replace")
        if e.code == 401 and ("unauthenticated" in body or "errors" in body):
            return "Canvas found"
        raise CanvasError("%s does not look like Canvas (HTTP %s)" % (base_url, e.code))
    except urllib.error.URLError as e:
        raise CanvasError("could not reach %s: %s" % (base_url, e.reason))
    raise CanvasError("%s answered an anonymous API call; it does not look like Canvas" % base_url)


class Canvas:
    def __init__(self, base_url, cookies=None, token=None):
        self.base_url = base_url.rstrip("/")
        self.host = urllib.parse.urlparse(self.base_url).hostname
        self.token = token
        self.cookie_header = "; ".join("%s=%s" % (c["name"], c["value"]) for c in (cookies or []))
        if not self.token and not self.cookie_header:
            raise SessionExpired("no Canvas session: run `ck login`")

    @classmethod
    def from_disk(cls, cfg, token=None):
        if token:
            return cls(cfg["base_url"], token=token)
        session = config.load_json(config.SESSION_FILE) or {}
        if session.get("base_url") != cfg["base_url"]:
            raise SessionExpired("no Canvas session for %s: run `ck login`" % cfg["base_url"])
        return cls(cfg["base_url"], cookies=session.get("cookies"))

    def _url(self, path, params=None):
        url = path if path.startswith("https://") else self.base_url + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
        return url

    def _open(self, url, accept="application/json"):
        if urllib.parse.urlparse(url).hostname != self.host:
            raise CanvasError("refusing to send Canvas credentials to %s" % url)
        req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
        if self.token:
            req.add_unredirected_header("Authorization", "Bearer " + self.token)
        else:
            req.add_unredirected_header("Cookie", self.cookie_header)
        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise SessionExpired("the Canvas session expired: run `ck login`")
            raise CanvasError("Canvas answered %s %s for %s" % (e.code, e.reason, url))
        except urllib.error.URLError as e:
            raise CanvasError("could not reach %s: %s" % (self.host, e.reason))
        if "/login" in urllib.parse.urlparse(resp.geturl()).path:
            raise SessionExpired("the Canvas session expired: run `ck login`")
        return resp

    def download(self, url, dest):
        """Save a file. Canvas file URLs carry a verifier and redirect to storage;
        credentials go only to the Canvas host and are dropped on the redirect."""
        if urllib.parse.urlparse(url).hostname == self.host:
            resp = self._open(url, accept="*/*")
        else:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            resp = urllib.request.urlopen(req, timeout=300)
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)

    def get(self, path, params=None):
        data, _ = self._get_page(self._url(path, params))
        return data

    def get_all(self, path, params=None):
        """GET every page of a paginated endpoint."""
        params = dict(params or {})
        params.setdefault("per_page", 100)
        url, items = self._url(path, params), []
        while url:
            data, link = self._get_page(url)
            items.extend(data if isinstance(data, list) else [data])
            url = _next_link(link)
        return items

    def _get_page(self, url):
        resp = self._open(url)
        body = resp.read().decode("utf-8")
        # Canvas guards session-authenticated JSON against hijacking with this prefix
        if body.startswith("while(1);"):
            body = body[len("while(1);"):]
        try:
            return json.loads(body), resp.headers.get("Link", "")
        except ValueError:
            raise CanvasError("Canvas did not return JSON for %s (is the address right?)" % url)
