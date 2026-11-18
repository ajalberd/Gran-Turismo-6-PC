"""Gamepad detection + RPCS3 input configuration.

RPCS3 binds a player to a device by exact name. For its SDL handler the name is
"<SDL gamepad name> <n>" (n counts devices with the same name, starting at 1 -
see rpcs3/Input/sdl_pad_handler.cpp). We ask SDL3 itself (ctypes, no Python
bindings needed) so the names match RPCS3 exactly.

RPCS3 first applies the handler's default button mapping and then overlays the
file, so writing only Handler + Device gives a fully mapped pad.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys
from typing import Optional

from . import paths
from .yamlio import atomic_write, dump_cfg, load_cfg

SDL_INIT_GAMEPAD = 0x00002000
SDL_INIT_JOYSTICK = 0x00000200
SDL_JOYSTICK_TYPE_WHEEL = 2


def _load_sdl3() -> Optional[ctypes.CDLL]:
    names = []
    base = getattr(sys, "_MEIPASS", None)
    if paths.IS_WINDOWS:
        exe_dir = os.path.dirname(sys.executable)
        if base:
            names += [os.path.join(base, "SDL3.dll"), os.path.join(base, "_internal", "SDL3.dll")]
        names += [
            os.path.join(exe_dir, "_internal", "SDL3.dll"),
            os.path.join(exe_dir, "SDL3.dll"),
            os.path.join(exe_dir, "rpcs3", "SDL3.dll"),
            os.path.join(paths.rpcs3_windows_dir(), "SDL3.dll"),
            "SDL3.dll",
        ]
    else:
        if base:
            names += glob.glob(os.path.join(base, "libSDL3.so*"))
        names += [
            "libSDL3.so.0",
            "libSDL3.so",
            "/usr/lib/x86_64-linux-gnu/libSDL3.so.0",
            "/usr/lib64/libSDL3.so.0",
            "/usr/lib/libSDL3.so.0",
            ctypes.util.find_library("SDL3") or "",
        ]
    for n in filter(None, names):
        try:
            return ctypes.CDLL(n)
        except OSError:
            continue
    return None


def _load_sdl2() -> Optional[ctypes.CDLL]:
    names = []
    base = getattr(sys, "_MEIPASS", None)
    if paths.IS_WINDOWS:
        exe_dir = os.path.dirname(sys.executable)
        if base:
            names += [os.path.join(base, "SDL2.dll"), os.path.join(base, "_internal", "SDL2.dll")]
        names += [
            os.path.join(exe_dir, "_internal", "SDL2.dll"),
            os.path.join(exe_dir, "SDL2.dll"),
            os.path.join(exe_dir, "rpcs3", "SDL2.dll"),
            os.path.join(paths.rpcs3_windows_dir(), "SDL2.dll"),
            "SDL2.dll",
        ]
    else:
        if base:
            names += glob.glob(os.path.join(base, "libSDL2*.so*"))
        names += [
            "libSDL2-2.0.so.0",
            "libSDL2.so",
            "/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0",
            "/usr/lib64/libSDL2-2.0.so.0",
            "/usr/lib/libSDL2-2.0.so.0",
            ctypes.util.find_library("SDL2-2.0") or "",
            ctypes.util.find_library("SDL2") or "",
        ]
    for n in filter(None, names):
        try:
            return ctypes.CDLL(n)
        except OSError:
            continue
    return None


XINPUT_PREFIX = "XInput Pad #"   # RPCS3 xinput_pad_handler device names: "XInput Pad #1".."#4"


def _xinput_pads() -> list[str]:
    """Windows: XInput slots with a connected pad (Xbox pads, 8BitDo in X-input mode...)."""
    if not paths.IS_WINDOWS:
        return []

    class _State(ctypes.Structure):
        _fields_ = [("packet", ctypes.c_uint32), ("buttons", ctypes.c_uint16), ("lt", ctypes.c_uint8),
                    ("rt", ctypes.c_uint8), ("lx", ctypes.c_int16), ("ly", ctypes.c_int16),
                    ("rx", ctypes.c_int16), ("ry", ctypes.c_int16)]
    for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            get = getattr(ctypes.windll, dll).XInputGetState
            break
        except (OSError, AttributeError):
            continue
    else:
        return []
    get.argtypes = [ctypes.c_uint32, ctypes.POINTER(_State)]
    get.restype = ctypes.c_uint32
    out = []
    for i in range(4):
        st = _State()
        if get(i, ctypes.byref(st)) == 0:  # ERROR_SUCCESS
            out.append(f"{XINPUT_PREFIX}{i + 1}")
    return out


def _sdl_hints() -> tuple[tuple[bytes, bytes], ...]:
    """Match RPCS3's platform-specific hints so both processes see the same devices."""
    hints = [(b"SDL_JOYSTICK_THREAD", b"1")]
    if paths.IS_WINDOWS:
        hints.extend(((b"SDL_JOYSTICK_HIDAPI_PS3_SIXAXIS_DRIVER", b"1"),
                      # Match RPCS3's Windows workaround for Logitech wheel HIDAPI issues.
                      (b"SDL_JOYSTICK_HIDAPI_LG4FF", b"0")))
    else:
        hints.append((b"SDL_JOYSTICK_HIDAPI_PS3", b"1"))
    return tuple(hints)


def _sdl_init(sdl: ctypes.CDLL, flags: int) -> bool:
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    sdl.SDL_SetHint.restype = ctypes.c_bool
    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_bool
    for k, v in _sdl_hints():
        sdl.SDL_SetHint(k, v)
    return bool(sdl.SDL_Init(flags))


def _sdl_pump(sdl: ctypes.CDLL, rounds: int = 8) -> None:
    """Let SDL discover devices. On Windows XInput/RawInput/DirectInput devices arrive
    asynchronously after SDL_Init; RPCS3 keeps pumping, so must we before listing."""
    import time
    sdl.SDL_PumpEvents.argtypes, sdl.SDL_PumpEvents.restype = [], None
    sdl.SDL_UpdateJoysticks.argtypes, sdl.SDL_UpdateJoysticks.restype = [], None
    for _ in range(rounds):
        sdl.SDL_PumpEvents()
        sdl.SDL_UpdateJoysticks()
        time.sleep(0.04)


def _sdl2_init(sdl: ctypes.CDLL, flags: int) -> bool:
    sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    sdl.SDL_SetHint.restype = ctypes.c_int
    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_int
    for k, v in _sdl_hints():
        sdl.SDL_SetHint(k, v)
    return sdl.SDL_Init(flags) == 0


def _sdl2_pump(sdl: ctypes.CDLL, rounds: int = 8) -> None:
    import time
    sdl.SDL_PumpEvents.argtypes, sdl.SDL_PumpEvents.restype = [], None
    sdl.SDL_JoystickUpdate.argtypes, sdl.SDL_JoystickUpdate.restype = [], None
    for _ in range(rounds):
        sdl.SDL_PumpEvents()
        sdl.SDL_JoystickUpdate()
        time.sleep(0.04)


HANDHELD_CONTROLLER_NAMES = (
    "steam deck", "steam virtual gamepad", "rog ally", "legion go", "legion controller", "msi claw",
    "claw controller", "gpd win", "ayaneo", "onexplayer", "aokzoe", "zotac zone", "handheld",
)
WHEEL_NAME_HINTS = ("wheel", "rs50", "g pro", "pro racing", "logitech rs",
                    "g923", "g29", "g920", "g27", "g25", "thrustmaster", "fanatec", "moza",
                    "simucube", "cammus", "logitech driving force", "pedal", "shifter")


def is_handheld_controller(name: str) -> bool:
    """Return True if the controller name matches a handheld PC integrated controller."""
    name_l = name.lower()
    return any(h in name_l for h in HANDHELD_CONTROLLER_NAMES)


def is_wheel_name(name: str) -> bool:
    name_l = name.lower()
    return any(w in name_l for w in WHEEL_NAME_HINTS)


SYNTH_MARKER = "# --- GT6 Launcher: synthesized handheld mappings (kept across updates) ---"


def ensure_gamecontrollerdb() -> str:
    """Install the bundled SDL_GameControllerDB as <rpcs3 config>/input_configs/gamecontrollerdb.txt
    (RPCS3 loads it from there, "Load SDL GameController Mappings" is on by default).

    The file is rewritten whenever the bundled copy changes; mappings the launcher synthesized for
    unrecognised handheld controllers (below SYNTH_MARKER) are preserved."""
    target_dir = os.path.join(paths.rpcs3_settings_dir(), "input_configs")
    target_path = os.path.join(target_dir, "gamecontrollerdb.txt")
    source_path = paths.resource("gamecontrollerdb.txt")
    try:
        if os.path.isfile(source_path):
            with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                bundled = f.read().rstrip("\n") + "\n"
            current = ""
            if os.path.isfile(target_path):
                with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                    current = f.read()
            synth = current.split(SYNTH_MARKER, 1)[1].strip("\n") if SYNTH_MARKER in current else ""
            wanted = bundled + (f"\n{SYNTH_MARKER}\n{synth}\n" if synth else "")
            if current != wanted:
                os.makedirs(target_dir, exist_ok=True)
                atomic_write(target_path, wanted)
    except Exception:
        pass
    os.environ["SDL_GAMECONTROLLERCONFIG_FILE"] = target_path
    return target_path


def _synth_mapping(guid: str, name: str, axes: int, hats: int, buttons: int) -> Optional[str]:
    """Xbox-360-layout mapping for a handheld that SDL does not recognise (Linux xpad/XInput order).
    Wheels and anything that is not a named handheld are never turned into gamepads: a wheel mapped
    as a pad would become Player 1 in 'Automatic' mode and send its axes twice (pad + G27)."""
    if not guid or not is_handheld_controller(name) or is_wheel_name(name) or axes < 4 or buttons < 8:
        return None
    clean = name.replace(",", " ").strip() or "Handheld Controller"
    parts = [guid, clean, "a:b0", "b:b1", "x:b2", "y:b3", "leftshoulder:b4", "rightshoulder:b5",
             "back:b6", "start:b7", "leftx:a0", "lefty:a1"]
    if buttons >= 11:
        parts += ["guide:b8", "leftstick:b9", "rightstick:b10"]
    if axes >= 6:
        parts += ["lefttrigger:a2", "rightx:a3", "righty:a4", "righttrigger:a5"]
    else:
        parts += ["rightx:a2", "righty:a3"]
    if hats >= 1:
        parts += ["dpup:h0.1", "dpright:h0.2", "dpdown:h0.4", "dpleft:h0.8"]
    parts.append(f"platform:{'Windows' if paths.IS_WINDOWS else 'Linux'}")
    return ",".join(parts) + ","


def _remember_synth(db: str, mapping: str) -> None:
    """Persist a synthesized mapping once (so RPCS3 sees the same pad), never duplicating a GUID."""
    guid = mapping.split(",", 1)[0]
    try:
        with open(db, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        if any(line.startswith(guid + ",") for line in text.splitlines()):
            return
        if SYNTH_MARKER not in text:
            text = text.rstrip("\n") + f"\n\n{SYNTH_MARKER}\n"
        atomic_write(db, text.rstrip("\n") + "\n" + mapping + "\n")
    except Exception:
        pass


def list_gamepads() -> Optional[list[str]]:
    """Connected gamepads as RPCS3 device names, or None if no detection backend is available.

    Windows: XInput pads first (RPCS3's XInput handler), then SDL devices. Elsewhere: SDL.
    Handheld controllers are prioritized so 'Automatic' mode instantly selects the integrated controls."""
    ensure_gamecontrollerdb()
    xi = _xinput_pads()
    sdl_pads = _sdl_gamepads()
    if sdl_pads is None and not paths.IS_WINDOWS:
        return None
    all_pads = [p for p in (xi + (sdl_pads or [])) if not is_wheel_name(p)]
    # Prioritize handheld controllers if connected
    handhelds = [p for p in all_pads if is_handheld_controller(p)]
    others = [p for p in all_pads if not is_handheld_controller(p)]
    return handhelds + others


def _sdl_gamepads() -> Optional[list[str]]:
    """RPCS3-style SDL device names of connected gamepads, or None if SDL3/SDL2 is unavailable."""
    sdl = _load_sdl3()
    if sdl is None:
        return _sdl2_gamepads()
    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    sdl.SDL_free.argtypes = [ctypes.c_void_p]
    if not _sdl_init(sdl, SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK):
        return _sdl2_gamepads()
    try:
        db = ensure_gamecontrollerdb()
        if os.path.isfile(db) and hasattr(sdl, "SDL_AddGamepadMappingsFromFile"):
            sdl.SDL_AddGamepadMappingsFromFile.argtypes = [ctypes.c_char_p]
            sdl.SDL_AddGamepadMappingsFromFile.restype = ctypes.c_int
            sdl.SDL_AddGamepadMappingsFromFile(db.encode("utf-8"))
        _sdl_pump(sdl)

        # Unrecognised handheld controllers (never wheels): synthesize an Xbox-layout mapping
        if all(hasattr(sdl, fn) for fn in ("SDL_GetJoysticks", "SDL_IsGamepad", "SDL_AddGamepadMapping",
                                           "SDL_GetJoystickGUID", "SDL_GUIDToString")):
            try:
                sdl.SDL_GetJoysticks.argtypes = [ctypes.POINTER(ctypes.c_int)]
                sdl.SDL_GetJoysticks.restype = ctypes.POINTER(ctypes.c_uint32)
                sdl.SDL_IsGamepad.argtypes = [ctypes.c_uint32]
                sdl.SDL_IsGamepad.restype = ctypes.c_bool
                sdl.SDL_OpenJoystick.argtypes = [ctypes.c_uint32]
                sdl.SDL_OpenJoystick.restype = ctypes.c_void_p
                sdl.SDL_CloseJoystick.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetJoystickName.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetJoystickName.restype = ctypes.c_char_p
                sdl.SDL_GetJoystickType.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetJoystickType.restype = ctypes.c_int
                sdl.SDL_GetNumJoystickAxes.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetNumJoystickAxes.restype = ctypes.c_int
                sdl.SDL_GetNumJoystickHats.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetNumJoystickHats.restype = ctypes.c_int
                sdl.SDL_GetNumJoystickButtons.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetNumJoystickButtons.restype = ctypes.c_int

                class _GUID3(ctypes.Structure):
                    _fields_ = [("data", ctypes.c_uint8 * 16)]
                sdl.SDL_GetJoystickGUID.argtypes = [ctypes.c_void_p]
                sdl.SDL_GetJoystickGUID.restype = _GUID3
                sdl.SDL_GUIDToString.argtypes = [_GUID3, ctypes.c_char_p, ctypes.c_int]
                sdl.SDL_GUIDToString.restype = None
                sdl.SDL_AddGamepadMapping.argtypes = [ctypes.c_char_p]
                sdl.SDL_AddGamepadMapping.restype = ctypes.c_int

                j_count = ctypes.c_int(0)
                j_ids = sdl.SDL_GetJoysticks(ctypes.byref(j_count))
                for j_idx in range(j_count.value):
                    jid = j_ids[j_idx]
                    if sdl.SDL_IsGamepad(jid):
                        continue
                    jh = sdl.SDL_OpenJoystick(jid)
                    if not jh:
                        continue
                    try:
                        if sdl.SDL_GetJoystickType(jh) == SDL_JOYSTICK_TYPE_WHEEL:
                            continue
                        raw_name = sdl.SDL_GetJoystickName(jh)
                        j_name = raw_name.decode("utf-8", "replace") if raw_name else ""
                        buf = ctypes.create_string_buffer(64)
                        sdl.SDL_GUIDToString(sdl.SDL_GetJoystickGUID(jh), buf, 64)
                        synth = _synth_mapping(buf.value.decode("ascii", "replace"), j_name,
                                               sdl.SDL_GetNumJoystickAxes(jh), sdl.SDL_GetNumJoystickHats(jh),
                                               sdl.SDL_GetNumJoystickButtons(jh))
                        if synth and sdl.SDL_AddGamepadMapping(synth.encode("utf-8")) >= 0:
                            _remember_synth(db, synth)
                    finally:
                        sdl.SDL_CloseJoystick(jh)
                if j_ids:
                    sdl.SDL_free(j_ids)
            except Exception:
                pass

        # Name each pad the way RPCS3 does (sdl_pad_handler.cpp: SDL_OpenGamepad + SDL_GetGamepadName).
        # SDL_GetGamepadNameForID is NOT equivalent: under Steam (SteamOS Game Mode, or any game
        # launched through Steam) the pad is Steam's virtual gamepad, and only an *opened* gamepad
        # takes the real controller's name from Steam's SteamVirtualGamepadInfo file. By ID it is
        # "Steam Virtual Gamepad", but RPCS3 sees "Steam Deck" - Player 1 then matched no device (#54).
        can_open = all(hasattr(sdl, fn) for fn in ("SDL_OpenGamepad", "SDL_GetGamepadName", "SDL_CloseGamepad"))
        if can_open:
            sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
            sdl.SDL_OpenGamepad.restype = ctypes.c_void_p
            sdl.SDL_GetGamepadName.argtypes = [ctypes.c_void_p]
            sdl.SDL_GetGamepadName.restype = ctypes.c_char_p
            sdl.SDL_CloseGamepad.argtypes = [ctypes.c_void_p]
            sdl.SDL_CloseGamepad.restype = None

        def pad_name(jid: int) -> Optional[bytes]:
            if can_open:
                pad = sdl.SDL_OpenGamepad(jid)
                if pad:
                    try:
                        raw = sdl.SDL_GetGamepadName(pad)
                        if raw:
                            return raw
                    finally:
                        sdl.SDL_CloseGamepad(pad)
            return sdl.SDL_GetGamepadNameForID(jid)

        count = ctypes.c_int(0)
        ids = sdl.SDL_GetGamepads(ctypes.byref(count))
        seen: dict[str, int] = {}
        out = []
        for i in range(count.value):
            raw = pad_name(ids[i])
            name = raw.decode("utf-8", "replace") if raw else "Gamepad"
            seen[name] = seen.get(name, 0) + 1
            out.append(f"{name} {seen[name]}")
        if ids:
            sdl.SDL_free(ids)
        return out
    finally:
        sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
        sdl.SDL_QuitSubSystem(SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK)


def _sdl2_gamepads() -> Optional[list[str]]:
    """SDL2 fallback for distros with libSDL2-2.0.so.0 instead of SDL3."""
    sdl = _load_sdl2()
    if sdl is None:
        return None
    sdl.SDL_NumJoysticks.argtypes = []
    sdl.SDL_NumJoysticks.restype = ctypes.c_int
    sdl.SDL_IsGameController.argtypes = [ctypes.c_int]
    sdl.SDL_IsGameController.restype = ctypes.c_int
    sdl.SDL_GameControllerNameForIndex.argtypes = [ctypes.c_int]
    sdl.SDL_GameControllerNameForIndex.restype = ctypes.c_char_p
    sdl.SDL_JoystickNameForIndex.argtypes = [ctypes.c_int]
    sdl.SDL_JoystickNameForIndex.restype = ctypes.c_char_p
    if not _sdl2_init(sdl, SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK):
        return None
    try:
        db = ensure_gamecontrollerdb()
        if os.path.isfile(db) and hasattr(sdl, "SDL_RWFromFile") and hasattr(sdl, "SDL_GameControllerAddMappingsFromRW"):
            sdl.SDL_RWFromFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            sdl.SDL_RWFromFile.restype = ctypes.c_void_p
            sdl.SDL_GameControllerAddMappingsFromRW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            sdl.SDL_GameControllerAddMappingsFromRW.restype = ctypes.c_int
            rw = sdl.SDL_RWFromFile(db.encode("utf-8"), b"rb")
            if rw:
                sdl.SDL_GameControllerAddMappingsFromRW(rw, 1)
        _sdl2_pump(sdl)

        # Unrecognised handheld controllers (never wheels): synthesize an Xbox-layout mapping
        if all(hasattr(sdl, fn) for fn in ("SDL_JoystickOpen", "SDL_JoystickGetGUID",
                                           "SDL_JoystickGetGUIDString", "SDL_GameControllerAddMapping")):
            try:
                sdl.SDL_JoystickOpen.argtypes = [ctypes.c_int]
                sdl.SDL_JoystickOpen.restype = ctypes.c_void_p
                sdl.SDL_JoystickClose.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickGetType.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickGetType.restype = ctypes.c_int
                sdl.SDL_JoystickNumAxes.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickNumAxes.restype = ctypes.c_int
                sdl.SDL_JoystickNumHats.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickNumHats.restype = ctypes.c_int
                sdl.SDL_JoystickNumButtons.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickNumButtons.restype = ctypes.c_int

                class _GUID2(ctypes.Structure):
                    _fields_ = [("data", ctypes.c_uint8 * 16)]
                sdl.SDL_JoystickGetGUID.argtypes = [ctypes.c_void_p]
                sdl.SDL_JoystickGetGUID.restype = _GUID2
                sdl.SDL_JoystickGetGUIDString.argtypes = [_GUID2, ctypes.c_char_p, ctypes.c_int]
                sdl.SDL_JoystickGetGUIDString.restype = None
                sdl.SDL_GameControllerAddMapping.argtypes = [ctypes.c_char_p]
                sdl.SDL_GameControllerAddMapping.restype = ctypes.c_int

                for i in range(sdl.SDL_NumJoysticks()):
                    if sdl.SDL_IsGameController(i):
                        continue
                    jh = sdl.SDL_JoystickOpen(i)
                    if not jh:
                        continue
                    try:
                        if sdl.SDL_JoystickGetType(jh) == SDL_JOYSTICK_TYPE_WHEEL:
                            continue
                        raw_name = sdl.SDL_JoystickNameForIndex(i)
                        j_name = raw_name.decode("utf-8", "replace") if raw_name else ""
                        buf = ctypes.create_string_buffer(64)
                        sdl.SDL_JoystickGetGUIDString(sdl.SDL_JoystickGetGUID(jh), buf, 64)
                        synth = _synth_mapping(buf.value.decode("ascii", "replace"), j_name,
                                               sdl.SDL_JoystickNumAxes(jh), sdl.SDL_JoystickNumHats(jh),
                                               sdl.SDL_JoystickNumButtons(jh))
                        if synth and sdl.SDL_GameControllerAddMapping(synth.encode("utf-8")) >= 0:
                            _remember_synth(db, synth)
                    finally:
                        sdl.SDL_JoystickClose(jh)
            except Exception:
                pass

        count = sdl.SDL_NumJoysticks()
        seen: dict[str, int] = {}
        out = []
        for i in range(count):
            if not sdl.SDL_IsGameController(i):
                continue
            raw = None
            # Opened controller name, as in the SDL3 path (Steam virtual gamepad -> real controller name)
            if all(hasattr(sdl, fn) for fn in ("SDL_GameControllerOpen", "SDL_GameControllerName", "SDL_GameControllerClose")):
                sdl.SDL_GameControllerOpen.argtypes = [ctypes.c_int]
                sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
                sdl.SDL_GameControllerName.argtypes = [ctypes.c_void_p]
                sdl.SDL_GameControllerName.restype = ctypes.c_char_p
                sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
                sdl.SDL_GameControllerClose.restype = None
                gc = sdl.SDL_GameControllerOpen(i)
                if gc:
                    try:
                        raw = sdl.SDL_GameControllerName(gc)
                    finally:
                        sdl.SDL_GameControllerClose(gc)
            raw = raw or sdl.SDL_GameControllerNameForIndex(i) or sdl.SDL_JoystickNameForIndex(i)
            name = raw.decode("utf-8", "replace") if raw else "Gamepad"
            seen[name] = seen.get(name, 0) + 1
            out.append(f"{name} {seen[name]}")
        return out
    finally:
        sdl.SDL_QuitSubSystem.argtypes = [ctypes.c_uint32]
        sdl.SDL_QuitSubSystem(SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK)


def input_config_path() -> str:
    # global profile "Default" (system_utils.cpp: get_config_dir(true)/input_configs/global/Default.yml)
    return os.path.join(paths.rpcs3_settings_dir(), "input_configs", "global", "Default.yml")


def current_player1() -> tuple[str, str]:
    cfg = load_cfg(input_config_path())
    p = cfg.get("Player 1 Input", {}) or {}
    return str(p.get("Handler", "")), str(p.get("Device", ""))


# RPCS3's keyboard handler defaults (keyboard_pad_handler::init_config) and what each PS3 button does in GT6.
# Read-only: used to show the key table; the launcher never writes these keys.
KEYBOARD_KEYS = (
    ("Cross", "X", "Confirm / accelerate"),
    ("Circle", "C", "Back"),
    ("Square", "Z", "Brake"),
    ("Triangle", "V", ""),
    ("Start", "Enter", "Pause / start race"),
    ("Select", "Space", ""),
    ("Left Stick Left", "A", "Steer left"),
    ("Left Stick Right", "D", "Steer right"),
    ("Up", "Up", "Menu up"),
    ("Down", "Down", "Menu down"),
    ("Left", "Left", "Menu left"),
    ("Right", "Right", "Menu right"),
    ("L1", "Q", ""),
    ("R1", "E", ""),
    ("L2", "R", ""),
    ("R2", "T", ""),
    ("PS Button", "Backspace", ""),
)


def keyboard_key_table() -> tuple[bool, list[tuple[str, str, str]]]:
    """(keyboard_active, rows of (PS3 button, key(s), GT6 action)). Keys come from Player 1's saved
    RPCS3 keyboard map when it has one, else RPCS3's defaults. Never modifies the config."""
    try:
        p1 = load_cfg(input_config_path()).get("Player 1 Input", {}) or {}
    except Exception:  # noqa: BLE001 - display only
        p1 = {}
    active = p1.get("Handler") == "Keyboard"
    saved = (p1.get("Config") or {}) if active else {}
    rows = []
    for button, default, action in KEYBOARD_KEYS:
        key = str(saved.get(button) or default)
        rows.append((button, key.replace(",", " / "), action))
    return active, rows


def configure(mode: str, device: str = "", log=print) -> str:
    """mode: 'auto' (first gamepad, else keyboard), 'pad' (given device), 'keyboard',
    'manual' (leave RPCS3's own input config alone). Returns a description."""
    if mode == "manual":
        return "Controller setup managed in RPCS3"
    pads = list_gamepads()
    cfg = load_cfg(input_config_path())
    p1 = dict(cfg.get("Player 1 Input", {}) or {})
    if mode == "auto":
        if pads:
            device = pads[0]
            mode = "pad"
        elif pads is None:
            return "SDL3 not found - controller config unchanged"
        elif p1 and p1.get("Handler") != "Keyboard":
            # A failed/empty device scan must not silently replace a user's
            # existing pad or wheel mapping with Keyboard.
            return f"Player 1: {p1.get('Device', 'gamepad')} (no gamepad detected - kept existing)"
        else:
            mode = "keyboard"
    elif mode == "pad" and pads and device not in pads and device.lower().startswith("steam virtual gamepad"):
        # Saved by launchers <= 1.2-beta4, which named Steam's virtual pad differently from RPCS3 (#54)
        device = pads[0]
    if mode == "pad" and device:
        new = {"Handler": "XInput" if device.startswith(XINPUT_PREFIX) else "SDL", "Device": device}
    else:
        new = {"Handler": "Keyboard", "Device": "Keyboard"}
    changed = False
    if p1.get("Handler") != new["Handler"] or p1.get("Device") != new["Device"]:
        # handler changed -> drop the old button map so RPCS3 applies the new handler's defaults
        cfg["Player 1 Input"] = new
        changed = True
        log(f"controller: player 1 -> {new['Handler']} / {new['Device']}")
    # Player 2 for GT6's 2-player split screen (Arcade): the next physical pad, if any.
    # Only written when a second pad is found, so a single-pad setup is left untouched.
    p2_dev = second_player_pad(pads or [], new["Device"])
    if p2_dev:
        p2_new = {"Handler": "XInput" if p2_dev.startswith(XINPUT_PREFIX) else "SDL", "Device": p2_dev}
        p2 = cfg.get("Player 2 Input", {}) or {}
        if p2.get("Handler") != p2_new["Handler"] or p2.get("Device") != p2_new["Device"]:
            cfg["Player 2 Input"] = p2_new
            changed = True
            log(f"controller: player 2 -> {p2_new['Handler']} / {p2_new['Device']}")
    if changed:
        atomic_write(input_config_path(), dump_cfg(cfg))
    desc = f"Player 1: {new['Device']}" if new["Handler"] != "Keyboard" else "Player 1: keyboard (no gamepad found)"
    if p2_dev:
        desc = desc.replace(" (no gamepad found)", "") + f", Player 2: {p2_dev}"
    return desc


_XINPUT_SDL_HINTS = ("xbox", "xinput")


def second_player_pad(pads: list[str], p1_device: str) -> Optional[str]:
    """Pick Player 2's device: the first pad that is a different physical controller from Player 1.

    On Windows an Xbox-style pad shows up twice, as 'XInput Pad #N' and again through SDL
    ('Xbox 360 Controller 1', 'XInput Controller 1'...). For every XInput slot, one Xbox-looking
    SDL entry is treated as that same pad and skipped."""
    xi = [p for p in pads if p.startswith(XINPUT_PREFIX)]
    dupes_left = len(xi)
    unique = list(xi)
    for p in pads:
        if p.startswith(XINPUT_PREFIX):
            continue
        if dupes_left and any(h in p.lower() for h in _XINPUT_SDL_HINTS):
            dupes_left -= 1
            continue
        unique.append(p)
    # Player 1 on an SDL Xbox name (picked by hand) is also the first XInput slot's pad
    if p1_device and not p1_device.startswith(XINPUT_PREFIX) and any(h in p1_device.lower() for h in _XINPUT_SDL_HINTS) and xi:
        unique = [p for p in unique if p != xi[0]]
    for p in unique:
        if p != p1_device:
            return p
    return None


# =========================================================================== racing wheels
# RPCS3 emulates a Logitech G27 (natively supported by GT6) driven by any SDL joystick.
# Its mapping file is <config>/LogitechG27.yml (Emu/Io/LogitechG27Config.h). Each control
# names a device by "device_type_id" = num_buttons<<52 | num_hats<<42 | num_axes<<32 |
# vendor<<16 | product, plus a button/hat/axis index. Pedal axes: in RPCS3's Logitech G27
# emulation (LogitechG27.cpp), 0x00 is Pressed and 0xFF is Released. Released pedal must
# read as the axis maximum (+32767), and pressed pedal must read as the axis minimum (-32768).
# Hence, pedals resting at +32767 (e.g. Thrustmaster T150/T300) need reverse: false.

G27_KEYS = ["steering", "throttle", "brake", "clutch", "shift_up", "shift_down", "up", "down", "left", "right",
            "triangle", "cross", "square", "circle", "l2", "l3", "r2", "r3", "plus", "minus", "dial_clockwise",
            "dial_anticlockwise", "dial_center", "select", "pause", "ps", "shifter_1", "shifter_2", "shifter_3",
            "shifter_4", "shifter_5", "shifter_6", "shifter_r"]


def type_id(vendor: int, product: int, axes: int, hats: int, buttons: int) -> int:
    m = (1 << 10) - 1
    return product | (vendor << 16) | ((axes & m) << 32) | ((hats & m) << 42) | ((buttons & m) << 52)


class Joysticks:
    """Live access to all SDL joysticks (for detection and the wheel set-up wizard)."""

    def __init__(self):
        self.sdl = _load_sdl3()
        self.sdl_ver = 3
        if self.sdl is None:
            self.sdl = _load_sdl2()
            self.sdl_ver = 2
        if self.sdl is None:
            raise RuntimeError("SDL3/SDL2 library not found")
        s = self.sdl
        if self.sdl_ver == 3:
            for name, args, res in (
                    ("SDL_GetJoysticks", [ctypes.POINTER(ctypes.c_int)], ctypes.POINTER(ctypes.c_uint32)),
                    ("SDL_OpenJoystick", [ctypes.c_uint32], ctypes.c_void_p),
                    ("SDL_CloseJoystick", [ctypes.c_void_p], None),
                    ("SDL_GetJoystickName", [ctypes.c_void_p], ctypes.c_char_p),
                    ("SDL_GetJoystickVendor", [ctypes.c_void_p], ctypes.c_uint16),
                    ("SDL_GetJoystickProduct", [ctypes.c_void_p], ctypes.c_uint16),
                    ("SDL_GetJoystickType", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_GetNumJoystickAxes", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_GetNumJoystickHats", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_GetNumJoystickButtons", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_GetJoystickAxis", [ctypes.c_void_p, ctypes.c_int], ctypes.c_int16),
                    ("SDL_GetJoystickHat", [ctypes.c_void_p, ctypes.c_int], ctypes.c_uint8),
                    ("SDL_GetJoystickButton", [ctypes.c_void_p, ctypes.c_int], ctypes.c_bool),
                    ("SDL_UpdateJoysticks", [], None),
                    ("SDL_free", [ctypes.c_void_p], None),
                    ("SDL_QuitSubSystem", [ctypes.c_uint32], None)):
                fn = getattr(s, name)
                fn.argtypes, fn.restype = args, res
            self._init_state = _bind_optional(s, "SDL_GetJoystickAxisInitialState",
                                              [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int16)],
                                              ctypes.c_bool)
            if not _sdl_init(s, SDL_INIT_JOYSTICK):
                raise RuntimeError("SDL joystick init failed")
        else:
            for name, args, res in (
                    ("SDL_NumJoysticks", [], ctypes.c_int),
                    ("SDL_JoystickOpen", [ctypes.c_int], ctypes.c_void_p),
                    ("SDL_JoystickClose", [ctypes.c_void_p], None),
                    ("SDL_JoystickName", [ctypes.c_void_p], ctypes.c_char_p),
                    ("SDL_JoystickGetVendor", [ctypes.c_void_p], ctypes.c_uint16),
                    ("SDL_JoystickGetProduct", [ctypes.c_void_p], ctypes.c_uint16),
                    ("SDL_JoystickGetType", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_JoystickNumAxes", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_JoystickNumHats", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_JoystickNumButtons", [ctypes.c_void_p], ctypes.c_int),
                    ("SDL_JoystickGetAxis", [ctypes.c_void_p, ctypes.c_int], ctypes.c_int16),
                    ("SDL_JoystickGetHat", [ctypes.c_void_p, ctypes.c_int], ctypes.c_uint8),
                    ("SDL_JoystickGetButton", [ctypes.c_void_p, ctypes.c_int], ctypes.c_uint8),
                    ("SDL_JoystickUpdate", [], None),
                    ("SDL_QuitSubSystem", [ctypes.c_uint32], None)):
                fn = getattr(s, name)
                fn.argtypes, fn.restype = args, res
            self._init_state = _bind_optional(s, "SDL_JoystickGetAxisInitialState",
                                              [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int16)],
                                              ctypes.c_int)
            if not _sdl2_init(s, SDL_INIT_JOYSTICK):
                raise RuntimeError("SDL2 joystick init failed")
        self.devices: list[dict] = []
        self.refresh(rounds=8)

    def refresh(self, rounds: int = 3) -> list[dict]:
        self.close_all()
        s = self.sdl
        if self.sdl_ver == 3:
            _sdl_pump(s, rounds)  # without this Windows reports no devices (wheel wizard saw nothing)
            n = ctypes.c_int(0)
            ids = s.SDL_GetJoysticks(ctypes.byref(n))
            for i in range(n.value):
                h = s.SDL_OpenJoystick(ids[i])
                if not h:
                    continue
                raw = s.SDL_GetJoystickName(h)
                d = {"handle": h, "name": raw.decode("utf-8", "replace") if raw else "Joystick",
                     "vendor": s.SDL_GetJoystickVendor(h), "product": s.SDL_GetJoystickProduct(h),
                     "axes": s.SDL_GetNumJoystickAxes(h), "hats": s.SDL_GetNumJoystickHats(h),
                     "buttons": s.SDL_GetNumJoystickButtons(h)}
                d["is_wheel"] = s.SDL_GetJoystickType(h) == SDL_JOYSTICK_TYPE_WHEEL or is_wheel_name(d["name"])
                d["type_id"] = type_id(d["vendor"], d["product"], d["axes"], d["hats"], d["buttons"])
                self.devices.append(d)
            if ids:
                s.SDL_free(ids)
        else:
            _sdl2_pump(s, rounds)
            count = s.SDL_NumJoysticks()
            for i in range(count):
                h = s.SDL_JoystickOpen(i)
                if not h:
                    continue
                raw = s.SDL_JoystickName(h)
                d = {"handle": h, "name": raw.decode("utf-8", "replace") if raw else "Joystick",
                     "vendor": s.SDL_JoystickGetVendor(h), "product": s.SDL_JoystickGetProduct(h),
                     "axes": s.SDL_JoystickNumAxes(h), "hats": s.SDL_JoystickNumHats(h),
                     "buttons": s.SDL_JoystickNumButtons(h)}
                d["is_wheel"] = s.SDL_JoystickGetType(h) == SDL_JOYSTICK_TYPE_WHEEL or is_wheel_name(d["name"])
                d["type_id"] = type_id(d["vendor"], d["product"], d["axes"], d["hats"], d["buttons"])
                self.devices.append(d)
        return self.devices

    def state(self) -> list[dict]:
        """Snapshot of every axis/hat/button of every device."""
        s = self.sdl
        if self.sdl_ver == 3:
            s.SDL_UpdateJoysticks()
        else:
            s.SDL_JoystickUpdate()
        out = []
        for d in self.devices:
            h = d["handle"]
            out.append({"axes": [s.SDL_GetJoystickAxis(h, i) if self.sdl_ver == 3 else s.SDL_JoystickGetAxis(h, i) for i in range(d["axes"])],
                        "reported": [self._axis_reported(h, i) for i in range(d["axes"])],
                        "hats": [s.SDL_GetJoystickHat(h, i) if self.sdl_ver == 3 else s.SDL_JoystickGetHat(h, i) for i in range(d["hats"])],
                        "buttons": [bool(s.SDL_GetJoystickButton(h, i) if self.sdl_ver == 3 else s.SDL_JoystickGetButton(h, i)) for i in range(d["buttons"])]})
        return out

    def _axis_reported(self, h, axis: int) -> bool:
        """False while SDL has not received any value for this axis yet (it then reads 0).
        Some wheels on Windows (Logitech G923) only send their first report when something moves,
        so their pedals read 0 until then and jump to their real rest value (#41)."""
        fn = self._init_state
        if fn is None:
            return True
        return bool(fn(h, axis, ctypes.byref(ctypes.c_int16(0))))

    def close_all(self) -> None:
        for d in self.devices:
            if self.sdl_ver == 3:
                self.sdl.SDL_CloseJoystick(d["handle"])
            else:
                self.sdl.SDL_JoystickClose(d["handle"])
        self.devices = []

    def close(self) -> None:
        self.close_all()
        self.sdl.SDL_QuitSubSystem(SDL_INIT_JOYSTICK)


def _bind_optional(lib, name: str, args: list, res):
    """Bind an SDL function that older SDL builds may not export; None if missing."""
    fn = getattr(lib, name, None)
    if fn is not None:
        fn.argtypes, fn.restype = args, res
    return fn


HAT_BITS = {1: "up", 2: "right", 4: "down", 8: "left"}


def detect_change(base: list[dict], now: list[dict], devices: list[dict], want: str,
                  exclude: set = frozenset(),
                  allowed_device_type_ids: Optional[set[int]] = None) -> Optional[dict]:
    """Return the first clear input change between two snapshots.
    want: 'axis' (moved > 50 % of the range), 'button' (button/hat pressed), 'any'."""
    best = None
    for di, (b, n) in enumerate(zip(base, now)):
        tid = devices[di]["type_id"]
        if allowed_device_type_ids is not None and tid not in allowed_device_type_ids:
            continue
        if want in ("axis", "any"):
            for i, (bv, nv) in enumerate(zip(b["axes"], n["axes"])):
                if (tid, "axis", i) in exclude:
                    continue
                delta = nv - bv
                if abs(delta) > 0x7FFF * 0.35 and (best is None or abs(delta) > best["delta"]):
                    best = {"device_type_id": tid, "type": "axis", "id": i, "hat": "", "delta": abs(delta),
                            "rest": bv, "moved": nv}
        if want in ("button", "any") and best is None:
            for i, (bv, nv) in enumerate(zip(b["buttons"], n["buttons"])):
                if nv and not bv and (tid, "button", i) not in exclude:
                    return {"device_type_id": tid, "type": "button", "id": i, "hat": "", "delta": 1}
            for i, (bv, nv) in enumerate(zip(b["hats"], n["hats"])):
                new = nv & ~bv
                for bit, comp in HAT_BITS.items():
                    if new & bit and (tid, "hat", i, comp) not in exclude:
                        return {"device_type_id": tid, "type": "hat", "id": i, "hat": comp, "delta": 1}
    return best


def g27_config_path() -> str:
    return os.path.join(paths.rpcs3_settings_dir(), "LogitechG27.yml")


PEDAL_KEYS = ("throttle", "brake", "clutch")


def write_g27_config(mapping: dict[str, dict], enabled: bool, ffb_device: int = 0,
                     reverse_effects: bool = False) -> str:
    """mapping: G27 key -> {device_type_id, type, id, hat, reverse}. Unmapped keys point to
    device 0 (never present -> neutral / not pressed). Unmapped pedals use reverse=True so
    RPCS3 reports 0xFF (released) instead of 0x00 (100% pressed, which holds clutch down)."""
    cfg: dict = {}
    for k in G27_KEYS:
        m = mapping.get(k)
        if m:
            cfg[k] = {"device_type_id": int(m["device_type_id"]), "type": m["type"], "id": int(m["id"]),
                      "hat": m.get("hat", ""), "reverse": bool(m.get("reverse", False))}
        else:
            cfg[k] = {"device_type_id": 0, "type": "button", "id": 0, "hat": "", "reverse": k in PEDAL_KEYS}
    cfg.update({"reverse_effects": bool(reverse_effects), "ffb_direction_type": "steering_axis",
                "compatibility_limit": 4, "ffb_device_type_id": int(ffb_device),
                "led_device_type_id": 0, "enabled": bool(enabled)})
    p = g27_config_path()
    atomic_write(p, dump_cfg(cfg))
    return p
