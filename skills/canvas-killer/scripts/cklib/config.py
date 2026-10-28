"""Configuration and on-disk state.

Everything canvas-killer keeps lives under one directory (default
``~/.canvas-killer``, overridable with ``CANVAS_KILLER_HOME``) so a user can
inspect or wipe it in one place. The session file holds live Canvas cookies,
so the directory is 0700 and every file in it is 0600.
"""

import json
import os
import re
from pathlib import Path

HOME = Path(os.environ.get("CANVAS_KILLER_HOME", str(Path.home() / ".canvas-killer")))
CONFIG_FILE = HOME / "config.json"
SESSION_FILE = HOME / "session.json"
BROWSER_PROFILE = HOME / "browser-profile"
CACHE_FILE = HOME / "cache" / "tasks.json"

DEFAULT_WORKSPACE = str(Path.home() / "Documents" / "canvas-killer")
DEFAULT_NAMING = "{course}_{task}"

# Whether deliverables carry a declaration of AI use. Schools differ: some require
# one in the work itself, many don't; the student decides how canvas-killer behaves.
AI_DISCLOSURE_MODES = {
    "auto": "only when the course or school requires one",
    "always": "in every deliverable",
    "never": "never (NOTES.md still mentions it once if the course requires one)",
}
DEFAULT_AI_DISCLOSURE = "auto"


class ConfigError(Exception):
    pass


def normalize_base_url(value):
    """Turn what a user types into a Canvas base URL.

    A bare institution slug such as ``pucpr`` means ``https://pucpr.instructure.com``;
    anything with a dot is a host of its own (many schools run Canvas on their
    own domain, such as ``canvas.example.edu``).
    """
    v = (value or "").strip().rstrip("/")
    if not v:
        raise ConfigError("the Canvas address is empty")
    if "://" not in v:
        if "." in v:
            v = "https://" + v
        elif re.fullmatch(r"[A-Za-z0-9-]+", v):
            v = "https://%s.instructure.com" % v.lower()
        else:
            raise ConfigError("%r is neither an institution name nor a web address" % value)
    if not v.startswith("https://"):
        raise ConfigError("the Canvas address must use https://")
    host = v[len("https://"):].split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", host):
        raise ConfigError("%r is not a valid host name" % host)
    return "https://" + host.lower()


def ensure_home():
    HOME.mkdir(parents=True, exist_ok=True)
    os.chmod(HOME, 0o700)


def write_private(path, text):
    """Write a file only the current user can read."""
    ensure_home()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def load_config():
    cfg = load_json(CONFIG_FILE)
    if not cfg or not cfg.get("base_url"):
        raise ConfigError("canvas-killer is not set up yet: run `ck setup --url <your Canvas address>`")
    cfg.setdefault("profile", {})
    cfg.setdefault("workspace", DEFAULT_WORKSPACE)
    return cfg


def ai_disclosure(cfg):
    """The student's AI-use disclosure setting as (mode, custom text or None)."""
    setting = cfg.get("ai_disclosure") or {}
    mode = setting.get("mode", DEFAULT_AI_DISCLOSURE)
    if mode not in AI_DISCLOSURE_MODES:
        mode = DEFAULT_AI_DISCLOSURE
    return mode, setting.get("text") or None


def describe_ai_disclosure(cfg):
    mode, text = ai_disclosure(cfg)
    return "%s, %s%s" % (mode, AI_DISCLOSURE_MODES[mode], "; custom text set" if text else "")


def save_config(cfg):
    write_private(CONFIG_FILE, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
