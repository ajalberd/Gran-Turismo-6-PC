"""Launcher state + high level operations (UI independent, also used by the CLI)."""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from . import lan, mods, patches, paths
from . import profile as profile_mod
from .formats import GameImage, identify_folder, identify_iso
from .profile import Settings, build_custom_config, desired_patches
from .rpcs3 import RPCS3, find_rpcs3, installed_version, seed_gui_settings
from .updates import DEFAULT_TARGET, install_chain, Downloader
from .yamlio import atomic_write, dump_cfg, load_cfg

GT6_TITLES = {
    "BCES01893": "Europe", "BCES01977": "UK", "BCUS98296": "North America", "BCUS99247": "Latin America",
    "BCJS37016": "Japan", "BCAS25018": "Asia", "BCKS15015": "Korea",
    "NPEA00502": "Europe (PSN)", "NPUA81049": "North America (PSN)", "NPJA00113": "Japan (PSN)",
    "NPHA80269": "Asia (PSN)",
}
FIRMWARE_LIST_URL = "http://fus01.ps3.update.playstation.net/update/ps3/list/us/ps3-updatelist.txt"

LogFn = Callable[[str], None]
ProgressFn = Callable[[str, int, int], None]


@dataclass
class GameEntry:
    image: GameImage
    installed: Optional[str]

    @property
    def title_id(self) -> str:
        return self.image.title_id

    @property
    def label(self) -> str:
        return f"{GT6_TITLES.get(self.title_id, self.image.region)} - {self.title_id}"


class Core:
    def __init__(self, log: Optional[LogFn] = None):
        self.log = log or print
        self.data = self._load()
        self.fresh_install = "profile" not in self.data
        self.settings = Settings.from_dict(self.data.get("profile", {}))
        # Resolve RPCS3 early so path helpers (game data, patches, controller
        # profiles, logs) agree with the selected executable's portable/ folder.
        if paths.IS_WINDOWS:
            self.rpcs3_path()
        self._migrate()

    PROFILE_REV = 4

    def _migrate(self) -> None:
        rev = int(self.data.get("profile_rev", 1))
        if rev < 2 and "profile" in self.data:
            # rev 2: audio time stretching on by default (fixes crackle during FPS dips)
            self.settings.audio_time_stretch = True
            self.settings.audio_buffer_ms = max(self.settings.audio_buffer_ms, 50)
        if rev < 3 and "profile" in self.data:
            # rev 3: RSX memory tiling on (noise over race name strip / HUD text)
            self.settings.handle_tiled_memory = True
        if rev < 4 and paths.IS_WINDOWS:
            # rev 4: up to v1.1.2 the Windows launcher wrote RPCS3's settings next to the "config"
            # sub-folder, where RPCS3 never reads them. Remove those stale copies (the correct
            # files are written on every start).
            base = paths.rpcs3_config_dir()
            for rel in ("custom_configs", "input_configs"):
                shutil.rmtree(os.path.join(base, rel), ignore_errors=True)
            for rel in ("patch_config.yml", "config.yml"):
                try:
                    os.unlink(os.path.join(base, rel))
                except OSError:
                    pass
        if rev != self.PROFILE_REV:
            self.data["profile_rev"] = self.PROFILE_REV
            self.save()

    # ------------------------------------------------------------------ persistence
    def _load(self) -> dict:
        try:
            with open(paths.settings_file(), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save(self) -> None:
        self.data["profile"] = self.settings.to_dict()
        atomic_write(paths.settings_file(), json.dumps(self.data, indent=1))

    # ------------------------------------------------------------------ rpcs3
    def rpcs3_path(self) -> Optional[str]:
        # resolved once per session (the first call may copy the bundled emulator)
        key = self.data.get("rpcs3_path") or None
        cached_key, cached = getattr(self, "_rpcs3_cache", (object(), None))
        if cached_key != key or not cached or not os.path.isfile(cached):
            cached = find_rpcs3(key)
            self._rpcs3_cache = (key, cached)
        paths.set_rpcs3_binary(cached)
        return cached

    def rpcs3(self) -> RPCS3:
        p = self.rpcs3_path()
        if not p:
            raise RuntimeError("RPCS3 was not found. Set its location in Advanced.")
        return RPCS3(p, self.log)

    # ------------------------------------------------------------------ games
    def games(self) -> list[GameEntry]:
        out = []
        for tid, g in sorted(self.data.get("games", {}).items()):
            p = g.get("path", "")
            if not os.path.exists(p):
                continue
            img = GameImage(p, tid, g.get("title", "Gran Turismo 6"), g.get("disc_version", "01.00"))
            out.append(GameEntry(img, installed_version(tid)))
        return out

    def active(self) -> Optional[GameEntry]:
        games = self.games()
        tid = self.data.get("active")
        return next((g for g in games if g.title_id == tid), games[0] if games else None)

    def set_active(self, title_id: str) -> None:
        self.data["active"] = title_id
        self.save()

    def add_game(self, path: str) -> GameEntry:
        path = os.path.abspath(path)
        if os.path.isdir(path):
            if os.path.basename(path.rstrip("/\\")).upper() == "PS3_GAME":
                path = os.path.dirname(path.rstrip("/\\"))
            img = identify_folder(path)
        else:
            img = identify_iso(path)
        if img.title_id not in GT6_TITLES:
            raise RuntimeError(f"{os.path.basename(path)} is {img.title_id} ({img.title}), not a supported "
                               f"Gran Turismo 6 disc.")
        self.data.setdefault("games", {})[img.title_id] = {"path": path, "title": img.title,
                                                          "disc_version": img.disc_version}
        self.data.setdefault("active", img.title_id)
        self.save()
        return GameEntry(img, installed_version(img.title_id))

    def scan_for_games(self, extra_dirs: Optional[list[str]] = None) -> list[GameEntry]:
        dirs = list(extra_dirs or [])
        here = os.environ.get("APPIMAGE") and os.path.dirname(os.environ["APPIMAGE"])
        dirs += [d for d in (here, os.path.expanduser("~/Downloads"), os.path.expanduser("~/Games"),
                             os.path.expanduser("~")) if d]
        found = []
        seen = set()
        for d in dirs:
            for pat in ("*.iso", "*/*.iso", "*/*/*.iso"):
                for f in glob.glob(os.path.join(d, pat)):
                    rf = os.path.realpath(f)
                    if rf in seen:
                        continue
                    seen.add(rf)
                    try:
                        if os.path.getsize(f) < 1 << 30:
                            continue
                        img = identify_iso(f)
                    except Exception:
                        continue
                    if img.title_id in GT6_TITLES and img.title_id not in self.data.get("games", {}):
                        found.append(self.add_game(f))
        return found

    # ------------------------------------------------------------------ firmware
    def find_local_firmware(self) -> Optional[str]:
        cands = []
        here = os.environ.get("APPIMAGE") and os.path.dirname(os.environ["APPIMAGE"])
        for d in filter(None, [here, os.path.expanduser("~/Downloads"), paths.downloads_dir()]):
            cands += glob.glob(os.path.join(d, "**", "PS3UPDAT.PUP"), recursive=True)[:5]
        cands = [c for c in cands if os.path.getsize(c) > 100 << 20]
        return cands[0] if cands else None

    def download_firmware(self, progress: Optional[ProgressFn] = None) -> str:
        with urllib.request.urlopen(FIRMWARE_LIST_URL, timeout=30) as r:
            text = r.read().decode("ascii", "replace")
        m = re.search(r"CDN=(http[^;]+PS3UPDAT\.PUP)", text)
        if not m:
            raise RuntimeError("Could not find the firmware download in Sony's update list.")
        url = m.group(1)
        dest = os.path.join(paths.downloads_dir("firmware"), "PS3UPDAT.PUP")
        with urllib.request.urlopen(url, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(dest + ".part", "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress("Downloading PS3 firmware", done, total)
        os.replace(dest + ".part", dest)
        return dest

    def ensure_firmware(self, progress: Optional[ProgressFn] = None) -> None:
        rp = self.rpcs3()
        if rp.firmware_installed():
            return
        pup = self.data.get("firmware_path") or self.find_local_firmware()
        if not pup or not os.path.exists(pup):
            pup = self.download_firmware(progress)
        if progress:
            progress("Installing PS3 firmware (compiles system modules on first game boot)", 0, 0)
        if not rp.install_firmware(pup):
            raise RuntimeError(f"Firmware install failed - see {paths.rpcs3_log_file()}")

    # ------------------------------------------------------------------ updates
    def target_version(self, title_id: str) -> str:
        return self.data.get("target_versions", {}).get(title_id, DEFAULT_TARGET)

    def set_target_version(self, title_id: str, v: str) -> None:
        self.data.setdefault("target_versions", {})[title_id] = v
        self.save()

    def install_updates(self, title_id: str, progress: Optional[ProgressFn] = None,
                        downloader: Optional[Downloader] = None) -> str:
        cur = installed_version(title_id)
        target = self.target_version(title_id)
        if cur and cur > target:
            raise RuntimeError(f"Installed version {cur} is newer than the selected {target}. "
                               f"Use 'Reset game data' in Advanced to downgrade.")
        return install_chain(self.rpcs3(), title_id, target, parallel=int(self.data.get("parallel", 4)),
                             delete_after=bool(self.data.get("delete_pkgs", False)), progress=progress,
                             log=self.log, downloader=downloader)

    def reset_game_data(self, title_id: str) -> None:
        """Remove installed updates + mods (keeps saves in dev_hdd0/home).

        Never touches RPCS3's compile caches (<cache>/rpcs3/{cache,ppu_progs,spu_progs}) so a
        reinstall of the same version does not recompile."""
        d = paths.hdd_game_dir(title_id)
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.rmtree(os.path.join(paths.backups_dir(), title_id), ignore_errors=True)

    # ------------------------------------------------------------------ boot
    def prepare(self, entry: GameEntry) -> list[str]:
        """Write RPCS3 config, patch files and patch selection for this game. Returns
        the list of enabled patch names (for display)."""
        tid, ver = entry.title_id, entry.installed
        cfg_dir = paths.rpcs3_config_dir()
        self.log(f"RPCS3 config directory: {cfg_dir}")
        seed_gui_settings(cfg_dir)
        if self.sync_ingame_color_grading(tid):
            self.log("color grading: using the values saved in the in-game home menu")
        eff = self.effective_settings(tid, ver)
        # global config: make sure the LAN-relevant parts agree with the custom config
        lan.apply_global_network(eff.lan_enabled or eff.online_enabled, eff.lan_bind_address)
        custom = build_custom_config(eff, ver, tid)
        # The launcher owns this file: write it fresh (a merge would keep stale keys such as
        # Process ARGV "lanmode" or a previously chosen GPU adapter after they were switched off).
        atomic_write(paths.custom_config_file(tid), dump_cfg(custom))
        self.data.setdefault("cg_written", {})[tid] = profile_mod.color_grading_from_config(
            custom["Video"]["Color Grading"])
        self.save()
        # patches
        for msg in patches.ensure_sources():  # first start: fetch the patch databases
            self.log(msg)
        patches.install_patch_files(cfg_dir, lan.title_patch_files(tid, ver))
        avail = {p.name: p for p in self.available_patches(tid, ver)}
        want = desired_patches(eff, ver)
        selection = []
        for name, values in want.items():
            p = avail.get(name)
            if p:
                valid = {c.name for c in p.config}
                selection.append((p, {k: v for k, v in values.items() if k in valid}))
        patches.write_patch_config(paths.rpcs3_settings_dir(cfg_dir), selection)
        self.log(f"config written for {tid} {ver}: {len(selection)} patches")
        return [p.name for p, _ in selection]

    def sync_ingame_color_grading(self, tid: str) -> bool:
        """Adopt color grading saved from the in-game home menu (Settings -> Color, Save).

        RPCS3 saves it into the per-game config, which the launcher regenerates on every start.
        Values that differ from what the launcher last wrote there were changed in game and win;
        returns True when settings changed."""
        written = self.data.get("cg_written", {}).get(tid)
        if written is None:
            return False
        try:
            cfg = load_cfg(paths.custom_config_file(tid))
        except Exception:  # noqa: BLE001 - a broken file is simply rewritten
            return False
        found = profile_mod.color_grading_from_config((cfg.get("Video") or {}).get("Color Grading"))
        if not found or found == written:
            return False
        # only the values changed in game: a slider moved in the launcher since then keeps its value
        changed = {k: v for k, v in found.items() if written.get(k) != v and getattr(self.settings, k) != v}
        for k, v in changed.items():
            setattr(self.settings, k, v)
        self.data["cg_written"][tid] = found
        self.save()
        return bool(changed)

    # ------------------------------------------------------------------ compile-cache tracking
    COMPILE_NOTICE = ("First start of a game version compiles GT6's code for your PC. This can take several "
                      "minutes and happens once. It repeats only after a game update, a different RPCS3 build, "
                      "or changed CPU settings (PPU/SPU decoder, SPU Block Size). Shaders also build up during "
                      "the first races, so brief stutter in new tracks is normal.")
    FIRST_122_NOTICE = ("The very first start of 1.22 takes about 30 minutes (measured on a 16-thread CPU): "
                        "~8 min compiling, then the game's own one-time \"Installing... approx. 20 mins left\" "
                        "screen while it assembles its update data. It runs at a steady 60 FPS there - it is "
                        "working, not hung. Do not close the game during this step.")

    def startup_notice(self, entry: "GameEntry") -> str:
        msg = self.COMPILE_NOTICE
        if entry.installed and entry.installed > "01.05" and not self.data.get("installed_once", {}).get(
                f"{entry.title_id}|{entry.installed}"):
            msg += "\n\n" + self.FIRST_122_NOTICE
        return msg

    def compile_fingerprint(self, entry: GameEntry) -> str:
        """Everything that invalidates RPCS3's PPU/SPU caches for this game."""
        rp = os.path.basename(self.rpcs3_path() or "")
        return "|".join([entry.title_id, entry.installed or "01.00", rp, self.settings.spu_block_size])

    def needs_compile(self, entry: GameEntry) -> bool:
        return self.compile_fingerprint(entry) not in self.data.get("compiled", [])

    def mark_compiled(self, entry: GameEntry) -> None:
        self.data.setdefault("installed_once", {})[f"{entry.title_id}|{entry.installed}"] = True
        done = self.data.setdefault("compiled", [])
        fp = self.compile_fingerprint(entry)
        if fp not in done:
            done.append(fp)
            self.save()

    @staticmethod
    def vulkan_available() -> bool:
        """RPCS3 needs the Vulkan loader (vulkan-1.dll / libvulkan.so.1), installed by every GPU driver."""
        if paths.IS_WINDOWS:
            root = os.environ.get("SystemRoot", r"C:\Windows")
            return any(os.path.isfile(os.path.join(root, d, "vulkan-1.dll")) for d in ("System32", "SysWOW64"))
        import ctypes.util
        return bool(ctypes.util.find_library("vulkan")) or any(
            os.path.exists(p) for p in ("/usr/lib/libvulkan.so.1", "/usr/lib64/libvulkan.so.1",
                                        "/usr/lib/x86_64-linux-gnu/libvulkan.so.1"))

    def launch(self, entry: GameEntry) -> subprocess.Popen:
        if not self.vulkan_available():
            raise RuntimeError("Vulkan was not found on this PC. Install or update your graphics driver "
                               "(NVIDIA, AMD or Intel) - it includes Vulkan - then start again.")
        rp = self.rpcs3()
        self.prepare(entry)
        try:
            from . import gamepad
            self.log(gamepad.configure(self.settings.controller_mode, self.settings.controller_device, self.log))
            m = self.settings.wheel_mapping or {}
            on = bool(self.settings.wheel_enabled and m.get("steering"))
            gamepad.write_g27_config(m, on, ffb_device=int(m["steering"]["device_type_id"]) if on else 0)
            if on:
                self.log(f"racing wheel: {self.settings.wheel_name} as Logitech G27")
        except Exception as e:  # never block a launch on controller detection
            self.log(f"controller setup skipped: {e}")
        wrapper = []
        env = {}
        if self.settings.use_mangohud and shutil.which("mangohud"):
            env["MANGOHUD"] = "1"
        if self.settings.use_gamemode and shutil.which("gamemoderun"):
            wrapper = ["gamemoderun"]
        return rp.boot(entry.image.path, fullscreen=self.settings.fullscreen, extra_env=env, wrapper=wrapper)

    def effective_settings(self, tid: str, ver: Optional[str]) -> Settings:
        """Settings as they are applied for this game: LAN/online only where supported, and the
        developer (cheat) menu never together with online play."""
        s = self.settings
        lan_on = s.lan_enabled and lan.supported(tid, ver)
        online_on = s.online_enabled and not lan_on and tid in profile_mod.ONLINE_TITLES and ver == "01.22"
        dev_on = s.dev_menu and not online_on and ver == "01.22"
        return Settings.from_dict({**s.to_dict(), "lan_enabled": lan_on, "online_enabled": online_on,
                                   "dev_menu": dev_on})

    @staticmethod
    def available_patches(tid: str, ver: Optional[str], index: Optional[list] = None) -> list:
        """All patches for serial+version: launcher LAN file first, then AlexHaust, then official."""
        own = [p for fn, text in lan.title_patch_files(tid, ver).items()
               for p in patches.extract_from_text(text, fn)]
        return patches.patches_for(tid, ver or "01.00", own + (index if index is not None else patches.load_index()))

    # ------------------------------------------------------------------ system checks
    MEMLOCK_WANT = 2 << 30

    @staticmethod
    def memlock_limit() -> Optional[int]:
        """Soft RLIMIT_MEMLOCK in bytes (None on Windows / unknown / unlimited)."""
        try:
            import resource
            soft, _hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
            return None if soft == resource.RLIM_INFINITY else soft
        except (ImportError, OSError, ValueError, AttributeError):
            return None

    def memlock_too_low(self) -> bool:
        lim = self.memlock_limit()
        return lim is not None and lim < self.MEMLOCK_WANT

    def ensure_rpcs3_windows(self, progress=None) -> str:
        from .rpcs3 import install_windows_rpcs3
        return install_windows_rpcs3(progress=progress)

    # ------------------------------------------------------------------ misc
    def gpu_adapters(self) -> list[str]:
        """Vulkan adapters RPCS3 found (parsed from its last log)."""
        out = []
        try:
            with open(paths.rpcs3_log_file(), "r", errors="replace") as f:
                for i, line in enumerate(f):
                    m = re.search(r"Found Vulkan-compatible GPU: '([^']+)'", line)
                    if m and m.group(1) not in out:
                        out.append(m.group(1))
                    if i > 400:
                        break
        except OSError:
            pass
        return out
