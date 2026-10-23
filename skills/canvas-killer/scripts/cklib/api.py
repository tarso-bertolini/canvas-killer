"""Minimal Canvas REST API client (standard library only).

Authenticates with either the cookies of a browser session (see session.py)
or a personal access token from the ``CANVAS_TOKEN`` environment variable.
Credentials are attached as *unredirected* headers, so urllib never forwards
them when Canvas redirects to another host (file downloads redirect to signed
storage URLs) or to its own login page.
"""

import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import uuid

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
        self.cookies = cookies or []
        self.cookie_header = "; ".join("%s=%s" % (c["name"], c["value"]) for c in self.cookies)
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

    def _authorize(self, req):
        if self.token:
            req.add_unredirected_header("Authorization", "Bearer " + self.token)
            return
        req.add_unredirected_header("Cookie", self.cookie_header)
        if req.data is not None:
            # session-authenticated writes must echo Canvas's CSRF cookie in a header
            csrf = next((c["value"] for c in self.cookies if c["name"] == "_csrf_token"), None)
            if csrf:
                req.add_unredirected_header("X-CSRF-Token", urllib.parse.unquote(csrf))

    def _open(self, url, accept="application/json", data=None, content_type=None):
        if urllib.parse.urlparse(url).hostname != self.host:
            raise CanvasError("refusing to send Canvas credentials to %s" % url)
        req = urllib.request.Request(url, data=data, headers={"Accept": accept, "User-Agent": USER_AGENT})
        if content_type:
            req.add_header("Content-Type", content_type)
        self._authorize(req)
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise SessionExpired("the Canvas session expired: run `ck login`")
            detail = e.read(500).decode("utf-8", "replace").replace("while(1);", "")
            raise CanvasError("Canvas answered %s %s for %s %s" % (e.code, e.reason, url, detail.strip()))
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

    def post(self, path, fields):
        """POST form fields, given as (name, value) pairs, to the Canvas API."""
        body = urllib.parse.urlencode(fields).encode("utf-8")
        resp = self._open(self._url(path), data=body, content_type="application/x-www-form-urlencoded")
        return _json_body(resp.read(), resp.geturl())

    def upload(self, upload_url, upload_params, path):
        """Second step of a Canvas file upload: send the file where Canvas said to.

        That URL authorizes the upload by itself, so credentials go along only
        when it is on the Canvas host. Storage answers either with the file
        object or with a location to confirm it at; returns the file object.
        """
        boundary = "----canvaskiller" + uuid.uuid4().hex
        parts = []
        for name, value in upload_params.items():
            parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                          % (boundary, name, value)).encode("utf-8"))
        parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
                      'Content-Type: application/octet-stream\r\n\r\n' % (boundary, os.path.basename(path))).encode("utf-8"))
        with open(path, "rb") as f:
            parts.append(f.read())
        parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
        req = urllib.request.Request(upload_url, data=b"".join(parts), method="POST", headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary, "User-Agent": USER_AGENT})
        if urllib.parse.urlparse(upload_url).hostname == self.host:
            self._authorize(req)
        try:
            resp = urllib.request.build_opener(_NoRedirect).open(req, timeout=600)
            location, body = resp.headers.get("Location"), resp.read()
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308):
                raise CanvasError("file upload failed: HTTP %s %s" % (e.code, e.read(300).decode("utf-8", "replace")))
            location, body = e.headers.get("Location"), b""
        data = {}
        if body:
            try:
                data = _json_body(body, upload_url)
            except CanvasError:
                data = {}
        if data.get("id") and data.get("display_name"):
            return data
        location = data.get("location") or location
        if not location:
            raise CanvasError("the upload finished without telling where the file is")
        return self.get(location)

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
        return _json_body(resp.read(), url), resp.headers.get("Link", "")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface redirects instead of following them (see Canvas.upload)."""

    def redirect_request(self, *args, **kwargs):
        return None


def _json_body(raw, url):
    body = raw.decode("utf-8")
    # Canvas guards session-authenticated JSON against hijacking with this prefix
    if body.startswith("while(1);"):
        body = body[len("while(1);"):]
    try:
        return json.loads(body)
    except ValueError:
        raise CanvasError("Canvas did not return JSON for %s (is the address right?)" % url)
