"""Check GitHub for a newer launcher release.

Every user is told about any newer published release, beta or stable (e.g. a 1.2-beta3
build is told about 1.2-beta4, 1.2, 1.3 or 2.0). ``__version__`` must match the release
tag (``1.2-beta3`` for tag ``v1.2-beta3``). Drafts and tags that are not version numbers
are ignored. Network errors are silent: the check must never get in the way of starting
the game.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Optional

REPO = "Mabec-games/Gran-Turismo-6-PC"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"

_STAGES = {"alpha": 0, "beta": 1, "rc": 2}
_STABLE = 3
_VERSION_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-_. ]?(alpha|beta|rc)[-_. ]?(\d*))?$", re.IGNORECASE)


def parse_version(text: str) -> Optional[tuple[int, int, int, int, int]]:
    """'v1.2-beta2' -> (1, 2, 0, 1, 2); '1.1.3' -> (1, 1, 3, 3, 0). None if not a version.
    A stable release sorts after every pre-release of the same number; a bare 'beta'
    counts as beta 1."""
    m = _VERSION_RE.match((text or "").strip())
    if not m:
        return None
    major, minor, patch, stage, num = m.groups()
    rank = _STAGES[stage.lower()] if stage else _STABLE
    n = int(num) if num else (1 if stage else 0)
    return int(major), int(minor or 0), int(patch or 0), rank, n


def is_prerelease_version(text: str) -> bool:
    v = parse_version(text)
    return v is not None and v[3] != _STABLE


def newer_release(current: str, releases: list[dict]) -> Optional[dict]:
    """The newest published release (beta or stable) newer than ``current``, or None."""
    cur = parse_version(current)
    if cur is None:
        return None
    best, best_key = None, cur
    for r in releases:
        if r.get("draft"):
            continue
        key = parse_version(r.get("tag_name", ""))
        if key is None:
            continue
        if key > best_key:
            best, best_key = r, key
    if best is None:
        return None
    return {"tag": best.get("tag_name", ""), "name": best.get("name") or best.get("tag_name", ""),
            "url": best.get("html_url") or RELEASES_PAGE, "prerelease": bool(best.get("prerelease"))}


def fetch_releases(timeout: float = 10.0) -> list[dict]:
    from . import __version__
    req = urllib.request.Request(RELEASES_API, headers={
        "User-Agent": f"GT6-Launcher/{__version__}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data if isinstance(data, list) else []


def check(current: Optional[str] = None, timeout: float = 10.0) -> Optional[dict]:
    """Newer release for this launcher, or None (also None on any network or parse error)."""
    if current is None:
        from . import __version__ as current
    try:
        return newer_release(current, fetch_releases(timeout))
    except Exception:  # offline, rate limited, GitHub down: never bother the user
        return None
