"""Locate and drive the RPCS3 binary (install firmware/packages, boot the game)."""
from __future__ import annotations

import glob
import os
import shutil
import signal
import stat
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from . import paths
from .formats import read_sfo

LogFn = Callable[[str], None]


def _clean_env() -> dict[str, str]:
    """Environment for child processes, with PyInstaller / AppImage leakage removed."""
    env = dict(os.environ)
    # PyInstaller (onedir/onefile) prepends its own lib dir; restore the original value.
    for var in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "PYTHONPATH",
                "PYTHONHOME", "GST_PLUGIN_PATH", "SSL_CERT_FILE"):
        orig = env.pop(var + "_ORIG", None)
        if orig is not None:
            env[var] = orig
        elif getattr(sys, "_MEIPASS", None) or os.environ.get("APPDIR"):
            env.pop(var, None)
    # Our own AppImage runtime variables must not confuse RPCS3's AppImage detection.
    for var in ("APPIMAGE", "APPDIR", "ARGV0", "OWD", "APPIMAGE_EXTRACT_AND_RUN"):
        env.pop(var, None)
    # GT6-patched RPCS3 (patch 08): started by the launcher -> no "Experimental Build" question
    env["GT6_LAUNCHER"] = "1"
    if paths.IS_WINDOWS:
        env["RPCS3_CONFIG_DIR"] = paths.rpcs3_config_dir().replace("\\", "/").rstrip("/") + "/"
    else:
        env["XDG_CONFIG_HOME"] = paths.rpcs3_xdg_config_home()
        env["XDG_CACHE_HOME"] = paths.rpcs3_xdg_cache_home()
    return env


def _popen(cmd: list[str], **kw) -> subprocess.Popen:
    """subprocess.Popen without PyInstaller's DLL search dir leaking into the child (Windows).

    The frozen launcher calls SetDllDirectoryW(<_internal>), and child processes inherit it.
    rpcs3.exe ships no VC++ runtime and would then load the launcher's older
    _internal\\VCRUNTIME140*.dll next to the system's newer MSVCP140.dll -> crash at start.
    """
    base = getattr(sys, "_MEIPASS", None)
    if not (paths.IS_WINDOWS and base):
        return subprocess.Popen(cmd, **kw)
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(cmd, **kw)
    finally:
        k32.SetDllDirectoryW(base)


def bundled_rpcs3() -> Optional[str]:
    """RPCS3 shipped inside the launcher bundle (copied to a persistent place on first use)."""
    candidates = []
    appdir = os.environ.get("APPDIR")
    if appdir:
        candidates += glob.glob(os.path.join(appdir, "usr", "share", "gt6-launcher", "rpcs3", "*.AppImage"))
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates += glob.glob(os.path.join(base, "rpcs3", "*.AppImage"))
        candidates += glob.glob(os.path.join(os.path.dirname(sys.executable), "rpcs3", "rpcs3.exe"))
    candidates.sort(key=lambda c: not is_patched_build(c))  # prefer the GT6-patched build
    return candidates[0] if candidates else None


PATCHED_BUILD_NAME = "rpcs3-gt6-x86_64.AppImage"


def patched_build_candidates() -> list[str]:
    """Locations of the GT6-optimised RPCS3 build (build/out/ of the project, or bundled)."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    c = [os.path.join(here, "build", "out", PATCHED_BUILD_NAME),
         os.path.join(managed_rpcs3_dir(), PATCHED_BUILD_NAME)]
    if os.environ.get("APPIMAGE"):
        c.append(os.path.join(os.path.dirname(os.environ["APPIMAGE"]), PATCHED_BUILD_NAME))
    return c


def patched_build_ready(path: str) -> bool:
    """The build/ pipeline drops '<AppImage>.ready' next to the file once it has been
    boot-tested; never pick up a half-finished build."""
    return os.path.isfile(path) and os.path.isfile(path + ".ready")


PATCHED_MARKER = "GT6-PATCHED.txt"   # written next to rpcs3.exe by the Windows packaging


def is_patched_build(binary: str) -> bool:
    return "gt6" in os.path.basename(binary).lower() or \
        os.path.isfile(os.path.join(os.path.dirname(binary), PATCHED_MARKER))


STOCK_BUILD_WARNING = ("Stock RPCS3 build: official builds since v0.0.42-20037 freeze for ~1 s during GT6 races "
                       "(rsx USER_COMMAND change #19549). Use the GT6-patched build for smooth races.")


def managed_rpcs3_dir() -> str:
    return paths.rpcs3_windows_dir() if paths.IS_WINDOWS else os.path.join(paths.data_dir(), "rpcs3-bin")


def find_rpcs3(preferred: Optional[str] = None) -> Optional[str]:
    """Resolution order: user setting -> managed copy -> bundled copy -> next to launcher -> PATH."""
    if preferred and os.path.isfile(preferred):
        return preferred
    env = os.environ.get("GT6L_RPCS3")
    if env and os.path.isfile(env):
        return env
    for p in patched_build_candidates():
        if patched_build_ready(p):
            return p
    if paths.IS_WINDOWS:
        exe = os.path.join(paths.rpcs3_windows_dir(), "rpcs3.exe")
        if os.path.isfile(exe):
            return exe
        bundled = os.path.join(os.path.dirname(sys.executable), "rpcs3", "rpcs3.exe")
        if os.path.isfile(bundled):  # shipped inside the launcher folder (GT6L_BUNDLE_RPCS3_DIR)
            return bundled
    else:
        os.makedirs(managed_rpcs3_dir(), exist_ok=True)
        managed = sorted(glob.glob(os.path.join(managed_rpcs3_dir(), "*.AppImage")))
        bundled = bundled_rpcs3()
        if bundled:
            dst = os.path.join(managed_rpcs3_dir(), os.path.basename(bundled))
            sb = os.stat(bundled)
            stale = (not os.path.exists(dst) or os.path.getsize(dst) != sb.st_size
                     or int(os.path.getmtime(dst)) != int(sb.st_mtime))
            if stale:  # first run, or the launcher was updated with a newer emulator build
                shutil.copy2(bundled, dst + ".part")
                os.replace(dst + ".part", dst)
            os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return dst
        if managed:
            return managed[-1]
    # next to the launcher executable / AppImage / source checkout
    here = [os.path.dirname(os.environ.get("APPIMAGE", "")) or None,
            os.path.dirname(sys.executable),
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]
    for d in filter(None, here):
        pats = ["rpcs3.exe"] if paths.IS_WINDOWS else ["rpcs3*.AppImage", "rpcs3*.appimage"]
        hits = sorted(h for pat in pats for h in glob.glob(os.path.join(d, pat)))
        if hits:
            return hits[-1]
    return shutil.which("rpcs3")


# --------------------------------------------------------------------------- GUI settings seed
# RPCS3 shows a blocking "Welcome to RPCS3" dialog on first start (even with --no-gui;
# pressing Exit quits RPCS3 so the game never starts). Seed GuiConfigs/CurrentSettings.ini
# (QSettings ini) before every launch, merging into whatever is there.
THEME_NAME = "GT6 Launcher"
GUI_SEED = {
    "main_window": {"infoBoxEnabledWelcome": "false"},
    "Meta": {"showDebugTab": "true", "currentStylesheet": THEME_NAME},
    # hide the mouse pointer over the game window after 2 s without mouse movement
    "GSFrame": {"hideMouseOnIdle": "true", "hideMouseOnIdleTime": "2000"},
    # in-game home menu (Xbox/PS button menu) on F10; the GT6-patched build also accepts Shift+F10
    "Shortcuts": {"gw_home_menu": "F10"},
}


def theme_qss() -> str:
    """Launcher theme for RPCS3's Qt dialogs, with absolute icon paths filled in."""
    src = paths.resource("rpcs3_gt6.qss")
    out = os.path.join(paths.cache_dir(), "rpcs3_gt6.qss")
    try:
        with open(src, "r", encoding="utf-8") as f:
            text = f.read().replace("@IMG@", paths.resource("img").replace("\\", "/"))
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        return out
    except OSError:
        return src


def window_icon() -> str:
    return paths.resource("img/icon.png")


def seed_gui_settings(cfg_dir: Optional[str] = None) -> str:
    base = cfg_dir or paths.rpcs3_config_dir()
    if paths.IS_WINDOWS:
        os.makedirs(os.path.join(base, "log"), exist_ok=True)
        exe = paths._RPCS3_BINARY
        if exe and os.path.isfile(exe):
            exe_dir = os.path.dirname(exe)
            if os.path.abspath(exe_dir) != os.path.abspath(base):
                db_src = os.path.join(exe_dir, "config", "input_configs", "gamecontrollerdb.txt")
                db_dst = os.path.join(paths.rpcs3_settings_dir(base), "input_configs", "gamecontrollerdb.txt")
                if os.path.isfile(db_src) and not os.path.exists(db_dst):
                    os.makedirs(os.path.dirname(db_dst), exist_ok=True)
                    shutil.copy2(db_src, db_dst)
                for fn in ("config_database.dat", "compat_database.dat"):
                    s = os.path.join(exe_dir, "GuiConfigs", fn)
                    d = os.path.join(base, "GuiConfigs", fn)
                    if os.path.isfile(s) and not os.path.exists(d):
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(s, d)
    f = os.path.join(base, "GuiConfigs", "CurrentSettings.ini")
    os.makedirs(os.path.dirname(f), exist_ok=True)
    try:  # launcher colour scheme as RPCS3's GUI theme (used when RPCS3's own window is opened)
        shutil.copy2(theme_qss(), os.path.join(os.path.dirname(f), THEME_NAME + ".qss"))
    except OSError:
        pass
    try:
        with open(f, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []
    for section, kv in GUI_SEED.items():
        hdr = f"[{section}]"
        if hdr not in lines:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(hdr)
        start = lines.index(hdr) + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("[") and lines[i].rstrip().endswith("]")),
                   len(lines))
        for key, val in kv.items():
            for i in range(start, end):
                if lines[i].split("=", 1)[0] == key:
                    lines[i] = f"{key}={val}"
                    break
            else:
                lines.insert(end, f"{key}={val}")
                end += 1
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, f)
    return f


@dataclass
class RunResult:
    code: int
    output: str


class RPCS3:
    def __init__(self, binary: str, log: Optional[LogFn] = None):
        self.binary = binary
        self.log = log or (lambda s: None)
        paths.set_rpcs3_binary(binary)

    # ------------------------------------------------------------------ helpers
    def _cmd(self, *args: str) -> list[str]:
        return [self.binary, *args]

    def _run(self, args: list[str], timeout: Optional[float] = None) -> RunResult:
        seed_gui_settings()
        self.log("$ " + " ".join(f'"{a}"' if " " in a else a for a in args))
        kw = {}
        if paths.IS_WINDOWS:
            kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        p = _popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_clean_env(),
                             stdin=subprocess.DEVNULL, text=True, errors="replace", **kw)
        try:
            out, _ = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            out, _ = p.communicate()
        return RunResult(p.returncode, out or "")

    def version(self) -> str:
        r = self._run(self._cmd("--version"), timeout=60)
        for line in r.output.splitlines():
            if "RPCS3" in line and ("0.0." in line or "v0" in line):
                return line.strip()
        return os.path.basename(self.binary)

    # ------------------------------------------------------------------ install
    def firmware_installed(self) -> bool:
        mod = os.path.join(paths.rpcs3_config_dir(), "dev_flash", "vsh", "module")
        return os.path.isdir(mod) and len(os.listdir(mod)) > 50

    def firmware_version(self) -> Optional[str]:
        f = os.path.join(paths.rpcs3_config_dir(), "dev_flash", "vsh", "etc", "version.txt")
        try:
            with open(f, "r", errors="replace") as fh:
                for line in fh:
                    if line.startswith("release:"):
                        return line.split(":", 1)[1].split(":")[0].strip()
        except OSError:
            pass
        return None

    def install_firmware(self, pup: str) -> bool:
        # RPCS3 parses "--headless" badly when it is the first option, so keep it last.
        self._run(self._cmd("--installfw", os.path.abspath(pup), "--headless"), timeout=1800)
        return self.firmware_installed()

    def install_pkg(self, pkg: str, title_id: str, expect_version: Optional[str]) -> bool:
        self._run(self._cmd("--installpkg", os.path.abspath(pkg), "--headless"), timeout=7200)
        if expect_version:
            return installed_version(title_id) == expect_version
        return True

    # ------------------------------------------------------------------ boot
    def boot(self, game_path: str, fullscreen: bool = True, extra_env: Optional[dict[str, str]] = None,
             wrapper: Optional[list[str]] = None, args: Optional[list[str]] = None) -> subprocess.Popen:
        cmd = self._cmd("--no-gui")
        if fullscreen:
            cmd.append("--fullscreen")
        if os.path.isfile(theme_qss()):
            # Qt applies this to every RPCS3 dialog (e.g. "Exit Game?"), also in --no-gui mode
            cmd += ["--stylesheet", theme_qss()]
        cmd.append(os.path.abspath(game_path))
        if args:
            cmd += args
        if wrapper:
            cmd = list(wrapper) + cmd
        seed_gui_settings()
        env = _clean_env()
        env["GT6_WINDOW_ICON"] = window_icon()  # honoured by the GT6-patched RPCS3 build
        if extra_env:
            env.update(extra_env)
        self.log("$ " + " ".join(cmd))
        kw = {}
        if not paths.IS_WINDOWS:
            kw["start_new_session"] = True
        return _popen(cmd, env=env, stdin=subprocess.DEVNULL, **kw)

    def open_gui(self) -> subprocess.Popen:
        seed_gui_settings()
        kw = {} if paths.IS_WINDOWS else {"start_new_session": True}
        env = _clean_env()
        env["GT6_WINDOW_ICON"] = window_icon()
        return _popen(self._cmd(), env=env, stdin=subprocess.DEVNULL, **kw)

    @staticmethod
    def stop(p: subprocess.Popen) -> None:
        if p.poll() is not None:
            return
        try:
            if paths.IS_WINDOWS:
                p.terminate()
            else:
                os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def installed_version(title_id: str) -> Optional[str]:
    """APP_VER of the installed update (dev_hdd0/game/<id>/PARAM.SFO) or None."""
    sfo = os.path.join(paths.hdd_game_dir(title_id), "PARAM.SFO")
    if not os.path.exists(sfo):
        return None
    try:
        return str(read_sfo(sfo).get("APP_VER") or "") or None
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- Windows: managed RPCS3
# Same build as the Linux AppImage the launcher ships with (keeps behaviour identical across OSes).
WINDOWS_PINNED = {
    "version": "0.0.43-20565",
    "url": "https://github.com/RPCS3/rpcs3-binaries-win/releases/download/"
           "build-eee3f0f7c285f2b8aa18fec278a2146c5cd874eb/rpcs3-v0.0.43-20565-eee3f0f7_win64_msvc.7z",
    "size": 37210593,
    "sha256": "FDEC321625C856DCF2D84EDA128F75F24A428230A233F1B2BF12C490882870E7",
}
UPDATE_API = "https://update.rpcs3.net/?api=v3&c={commit}&os_type=windows&os_arch=x64&os_version=10.0.0"


def latest_windows_build(commit: str = "eee3f0f7c285f2b8aa18fec278a2146c5cd874eb") -> dict:
    """Ask RPCS3's update server for the newest Windows build (optional 'update RPCS3' button)."""
    import json
    import urllib.request
    with urllib.request.urlopen(UPDATE_API.format(commit=commit), timeout=30) as r:
        data = json.load(r)
    if data.get("return_code") not in (0, 1):
        raise RuntimeError(f"update server returned {data.get('return_code')}")
    b = data["latest_build"]
    return {"version": b["version"], "url": b["windows"]["download"], "size": int(b["windows"]["size"]),
            "sha256": b["windows"]["checksum"]}


def _extract_7z(archive: str, dest: str) -> None:
    """RPCS3's .7z uses the BCJ2 filter, which py7zr cannot decode. Try, in order: libarchive
    'tar' (built into Windows 10 1803+/11 and most Linux distros), a bundled/installed 7-Zip, py7zr."""
    import subprocess as sp
    cands = []
    if paths.IS_WINDOWS:
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        cands.append([os.path.join(sysroot, "System32", "tar.exe"), "-xf", archive, "-C", dest])
    elif shutil.which("bsdtar"):
        cands.append(["bsdtar", "-xf", archive, "-C", dest])
    base = getattr(sys, "_MEIPASS", None)
    for exe in filter(None, [base and os.path.join(base, "tools", "7zr.exe"),
                             r"C:\Program Files\7-Zip\7z.exe", shutil.which("7z"), shutil.which("7zr")]):
        if os.path.isfile(exe):
            cands.append([exe, "x", "-y", f"-o{dest}", archive])
    for cmd in cands:
        try:
            r = sp.run(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, timeout=600,
                       creationflags=0x08000000 if paths.IS_WINDOWS else 0)
            if r.returncode == 0 and os.path.isfile(os.path.join(dest, "rpcs3.exe")):
                return
        except (OSError, sp.SubprocessError):
            continue
    try:
        import py7zr
        with py7zr.SevenZipFile(archive, "r") as z:
            z.extractall(dest)
        if os.path.isfile(os.path.join(dest, "rpcs3.exe")):
            return
    except Exception:
        pass
    raise RuntimeError("Could not extract the RPCS3 archive (needs Windows tar.exe or 7-Zip).")


def install_windows_rpcs3(build: Optional[dict] = None, progress=None) -> str:
    """Download + verify + extract RPCS3 for Windows into the launcher's portable RPCS3 dir.
    User data (dev_hdd0, config.yml, caches) in that dir is left untouched."""
    import hashlib
    import urllib.request
    build = build or WINDOWS_PINNED
    dest_dir = paths.rpcs3_windows_dir()
    archive = os.path.join(paths.downloads_dir("rpcs3"), os.path.basename(build["url"]))
    if not (os.path.exists(archive) and os.path.getsize(archive) == build["size"]):
        req = urllib.request.Request(build["url"], headers={"User-Agent": "GT6-Launcher/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(archive + ".part", "wb") as f:
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(f"Downloading RPCS3 {build['version']}", done, build["size"])
        os.replace(archive + ".part", archive)
    h = hashlib.sha256()
    with open(archive, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest().upper() != build["sha256"].upper():
        os.unlink(archive)
        raise RuntimeError("RPCS3 download is corrupt (SHA-256 mismatch) - try again.")
    if progress:
        progress("Extracting RPCS3", 0, 0)
    import tempfile
    with tempfile.TemporaryDirectory(dir=paths.downloads_dir("rpcs3"), prefix=".x-") as tmp:
        _extract_7z(archive, tmp)
        # copy over, keeping the user's own files in config/ and GuiConfigs/
        for root, _dirs, files in os.walk(tmp):
            rel_root = os.path.relpath(root, tmp)
            for fn in files:
                rel = os.path.normpath(os.path.join(rel_root, fn))
                dst = os.path.join(dest_dir, rel)
                top = rel.replace("\\", "/").split("/")[0]
                if top in ("config", "GuiConfigs") and os.path.exists(dst):
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(root, fn), dst)
    exe = os.path.join(dest_dir, "rpcs3.exe")
    if not os.path.isfile(exe):
        raise RuntimeError("rpcs3.exe missing after extraction")
    with open(os.path.join(dest_dir, ".gt6-launcher-build"), "w") as f:
        f.write(build["version"])
    return exe
