"""PDIPFS mod manager.

GT6 keeps its (updated) game data in ``dev_hdd0/game/<TITLE>/USRDIR/PDIPFS``.
Mods such as Spec II and the GT6 Career Mod are drop-in replacements for files
in that tree. The manager:

* accepts the archive exactly as downloaded (outer zip with nested zips, the
  inner zips, or an extracted folder),
* installs mods as an ordered *stack* (Spec II first, Career mod on top),
* backs up every file it overwrites and records every file it adds, so
  uninstalling restores the original game byte-for-byte.
"""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import paths

ProgressFn = Callable[[str, int, int], None]


@dataclass
class ModDef:
    id: str
    name: str
    description: str
    # glob (case-insensitive) matched against zip names / folders inside the download
    payload_glob: str
    requires_version: str = "01.22"
    depends: list[str] = field(default_factory=list)
    page: str = ""
    author: str = ""


KNOWN_MODS: list[ModDef] = [
    ModDef(
        id="spec2",
        name="Spec II Mod (Beta 7)",
        description="Debug & secret options, custom engine sounds, Top Gear test track, seasonal events, "
                    "GT4 missions, course maker tracks. Base for the Career mod.",
        payload_glob="*spec 2 mod pdipfs*",
        author="Nenkai, TheAdmiester",
        page="https://www.gtplanet.net/forum/downloads/gran-turismo-6-career-mod.7049/",
    ),
    ModDef(
        id="career",
        name="GT6 Career Mod",
        description="Reworked career: 33 extra GT mode events, endurance races, classic tests, fixed chase cam, "
                    "engine sounds, better payouts, extra tracks, unused Masahiro Ando music.",
        payload_glob="*career mod pdipfs*",
        depends=["spec2"],
        author="Lunard (+ Nenkai, TheAdmiester, Emivebe, Plunke)",
        page="https://www.gtplanet.net/forum/downloads/gran-turismo-6-career-mod.7049/",
    ),
]
CAREER_PAGE = "https://www.gtplanet.net/forum/downloads/gran-turismo-6-career-mod.7049/"
CAREER_ARCHIVE_GLOBS = ["gt6 career mod*.zip", "gt6careermod*.zip", "*career*mod*.zip"]


CAREER_DOWNLOAD = CAREER_PAGE + "download"


def try_download_career(progress: Optional[ProgressFn] = None) -> Optional[str]:
    """Plain download of the Career mod archive from GTPlanet. Returns the file path, or
    None if the site refuses non-browser downloads (then the UI opens the page instead).
    No cookie/anti-bot workarounds are attempted on purpose."""
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(CAREER_DOWNLOAD, headers={"User-Agent": "GT6-Launcher/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            name = os.path.basename(urllib.request.url2pathname(r.geturl().split("key=")[-1]))
            name = name.split("-")[-1] if name.lower().endswith(".zip") else "GT6CareerMod.zip"
            ctype = r.headers.get("Content-Type", "")
            if "zip" not in ctype and "octet" not in ctype:
                return None
            total = int(r.headers.get("Content-Length") or 0)
            dest = os.path.join(paths.downloads_dir("mods"), name)
            done = 0
            with open(dest + ".part", "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress("Downloading GT6 Career Mod", done, total)
        os.replace(dest + ".part", dest)
        return dest
    except (urllib.error.URLError, OSError, ValueError):
        return None


def mod_by_id(mod_id: str) -> Optional[ModDef]:
    return next((m for m in KNOWN_MODS if m.id == mod_id), None)


# --------------------------------------------------------------------------- archive handling

def _safe_extract(zf: zipfile.ZipFile, dest: str, progress: Optional[ProgressFn] = None, label: str = "") -> None:
    dest_real = os.path.realpath(dest)
    members = zf.infolist()
    total = sum(m.file_size for m in members) or 1
    done = 0
    for m in members:
        name = m.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/") or ":" in name.split("/")[0]:
            raise RuntimeError(f"unsafe path in archive: {m.filename}")
        target = os.path.realpath(os.path.join(dest, name))
        if not (target == dest_real or target.startswith(dest_real + os.sep)):
            raise RuntimeError(f"unsafe path in archive: {m.filename}")
        if m.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(m) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out, 1 << 20)
        done += m.file_size
        if progress:
            progress(label or "Extracting", done, total)


def _ci_match(name: str, pattern: str) -> bool:
    return fnmatch.fnmatch(name.lower(), pattern.lower())


def find_pdipfs_root(folder: str) -> Optional[str]:
    """Return the folder that *is* the PDIPFS tree inside an extracted payload."""
    for root, dirs, _files in os.walk(folder):
        for d in dirs:
            if d.upper().startswith("PDIPFS") and d.upper() != "PDIPFS_ORIGINAL":
                return os.path.join(root, d)
    return None


def stage_download(source: str, progress: Optional[ProgressFn] = None) -> dict[str, str]:
    """Unpack a downloaded mod archive/folder into the launcher's mod library.

    Returns {mod_id: path_to_PDIPFS_folder} for every known mod found."""
    lib = paths.mods_dir()
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(dir=lib, prefix=".stage-") as tmp:
        if os.path.isdir(source):
            work = source
        else:
            with zipfile.ZipFile(source) as zf:
                _safe_extract(zf, tmp, progress, f"Extracting {os.path.basename(source)}")
            work = tmp
        # candidates: nested zips or folders matching each mod's glob
        for mod in KNOWN_MODS:
            hit: Optional[str] = None
            for root, dirs, files in os.walk(work):
                for fn in files:
                    if fn.lower().endswith(".zip") and _ci_match(fn, mod.payload_glob):
                        hit = os.path.join(root, fn)
                        break
                if not hit:
                    for d in dirs:
                        if _ci_match(d, mod.payload_glob):
                            hit = os.path.join(root, d)
                            break
                if hit:
                    break
            if not hit and os.path.isfile(source) and _ci_match(os.path.basename(source), mod.payload_glob):
                hit = source
            if not hit:
                continue
            dest = os.path.join(lib, mod.id)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            if os.path.isdir(hit):
                shutil.copytree(hit, os.path.join(dest, os.path.basename(hit)))
            else:
                with zipfile.ZipFile(hit) as zf:
                    _safe_extract(zf, dest, progress, f"Extracting {mod.name}")
            root = find_pdipfs_root(dest)
            if root:
                found[mod.id] = root
                _write_json(os.path.join(dest, ".source.json"), {"source": os.path.abspath(source)})
        # keep the readme/changelog around for the UI
        for root, _dirs, files in os.walk(work):
            for fn in files:
                if fn.lower().endswith(".txt"):
                    shutil.copy2(os.path.join(root, fn), os.path.join(lib, fn))
    return found


def staged(mod_id: str) -> Optional[str]:
    d = os.path.join(paths.mods_dir(), mod_id)
    return find_pdipfs_root(d) if os.path.isdir(d) else None


def find_archive_in(folder: str) -> Optional[str]:
    """Look for an already downloaded Career mod archive (e.g. in ~/Downloads)."""
    try:
        entries = sorted(os.listdir(folder), key=lambda f: -os.path.getmtime(os.path.join(folder, f)))
    except OSError:
        return None
    for fn in entries:
        p = os.path.join(folder, fn)
        if any(_ci_match(fn, g) for g in CAREER_ARCHIVE_GLOBS) and os.path.isfile(p) \
                and not fn.endswith((".part", ".crdownload")):
            return p
        if os.path.isdir(p) and fn.lower().startswith("gt6 career mod"):
            return p
    return None


# --------------------------------------------------------------------------- install stack

def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(path + ".tmp", path)


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def pdipfs_dir(title_id: str) -> str:
    return os.path.join(paths.hdd_game_dir(title_id), "USRDIR", "PDIPFS")


def _state_file(title_id: str) -> str:
    return os.path.join(paths.backups_dir(), title_id, "stack.json")


def installed_stack(title_id: str) -> list[str]:
    return [e["id"] for e in _read_json(_state_file(title_id), [])]


def game_data_ready(title_id: str) -> bool:
    """True once the game has merged its update data into USRDIR/PDIPFS
    (happens on the first boot after installing updates)."""
    d = pdipfs_dir(title_id)
    try:
        # A fresh PKG install only contains an initial skeleton (1-2 dirs like '9' and 'K').
        # After GT6 completes its one-time in-game installation, PDIPFS has 25+ root directories
        # and thousands of unpacked files.
        return os.path.isdir(d) and len(os.listdir(d)) >= 20
    except OSError:
        return False


def install(title_id: str, mod_id: str, progress: Optional[ProgressFn] = None) -> int:
    mod = mod_by_id(mod_id)
    if not mod:
        raise ValueError(mod_id)
    src = staged(mod_id)
    if not src:
        raise RuntimeError(f"{mod.name} has not been imported yet.")
    stack = _read_json(_state_file(title_id), [])
    ids = [e["id"] for e in stack]
    if mod_id in ids:
        raise RuntimeError(f"{mod.name} is already installed.")
    missing = [d for d in mod.depends if d not in ids]
    if missing:
        raise RuntimeError(f"{mod.name} needs {', '.join(mod_by_id(m).name for m in missing)} installed first.")
    dst_root = pdipfs_dir(title_id)
    if not game_data_ready(title_id):
        raise RuntimeError("Start the game once after installing the updates (it unpacks its update data "
                           "on first boot), then install mods.")
    backup_root = os.path.join(paths.backups_dir(), title_id, mod_id)
    if os.path.exists(backup_root):
        shutil.rmtree(backup_root)
    files = []
    for root, _dirs, fns in os.walk(src):
        for fn in fns:
            files.append(os.path.relpath(os.path.join(root, fn), src))
    added, replaced = [], []
    for i, rel in enumerate(files):
        s = os.path.join(src, rel)
        d = os.path.join(dst_root, rel)
        if os.path.exists(d):
            b = os.path.join(backup_root, rel)
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.copy2(d, b)
            replaced.append(rel)
        else:
            added.append(rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        if progress and (i % 25 == 0 or i == len(files) - 1):
            progress(f"Installing {mod.name}", i + 1, len(files))
    stack.append({"id": mod_id, "added": added, "replaced": replaced})
    _write_json(_state_file(title_id), stack)
    return len(files)


def uninstall_top(title_id: str, progress: Optional[ProgressFn] = None) -> Optional[str]:
    """Remove the most recently installed mod. Returns its id."""
    stack = _read_json(_state_file(title_id), [])
    if not stack:
        return None
    top = stack[-1]
    dst_root = pdipfs_dir(title_id)
    backup_root = os.path.join(paths.backups_dir(), title_id, top["id"])
    items = top["added"] + top["replaced"]
    for i, rel in enumerate(top["added"]):
        try:
            os.unlink(os.path.join(dst_root, rel))
        except FileNotFoundError:
            pass
    for rel in top["replaced"]:
        b = os.path.join(backup_root, rel)
        if os.path.exists(b):
            shutil.copy2(b, os.path.join(dst_root, rel))
    if progress:
        progress("Removing mod", len(items), len(items))
    shutil.rmtree(backup_root, ignore_errors=True)
    stack.pop()
    _write_json(_state_file(title_id), stack)
    return top["id"]


def uninstall(title_id: str, mod_id: str, progress: Optional[ProgressFn] = None) -> list[str]:
    """Uninstall ``mod_id`` and everything stacked on top of it."""
    removed = []
    while mod_id in installed_stack(title_id):
        r = uninstall_top(title_id, progress)
        if r is None:
            break
        removed.append(r)
    return removed
