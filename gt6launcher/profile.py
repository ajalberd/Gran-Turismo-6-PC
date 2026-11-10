"""GT6-specific RPCS3 configuration.

The launcher owns ``custom_configs/config_<TITLE>.yml`` and regenerates it from
:class:`Settings` before every boot. Values are the exact strings RPCS3 uses
(checked against rpcs3/Emu/system_config*.{h,cpp}).

Sources for the defaults:
  * RPCS3 wiki GT6 page / abowen's GT6 1.22 LAN gist: Write+Read Color Buffers on
    for game versions > 1.05 (black world otherwise), Accurate RSX reservation
    access, Disable ZCull Occlusion Queries (reward screen slowdowns, Garage
    car-image softlock).
  * AlexHaust KNOWN_ISSUES: keep Multithreaded RSX off (vertex explosions).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Any

# --------------------------------------------------------------------------- choices

RESOLUTION_SCALES = [100, 150, 200, 250, 300]
OUTPUT_RESOLUTIONS = {
    "1920x1080": "1080p (desktop, GT6 renders ~1440x1080)",
    "1280x720": "720p (handhelds / Steam Deck - much lighter on the GPU)",
}
HANDHELD_PRESET = {"output_resolution": "1280x720", "resolution_scale": 100, "aspect": "16:10",
                   "upscaler": "fsr", "cas_sharpening": 60, "shadows": "stock", "anisotropic": 8,
                   "motion_blur": "stock"}
ASPECTS = {
    "16:9": None,                       # stock, no patch
    "21:9 (2560x1080)": 2.37037037037037,
    "21:9 (3440x1440)": 2.388888888888889,
    "21:9 (3840x1600)": 2.4,
    "32:9": 3.555555555555556,
    "16:10": 1.6,
}
AA_MODES = {
    "mlaa": "Stock MLAA",
    "mlaa_sharp": "Sharper MLAA (recommended)",
    "mlaa_strong": "Sharper MLAA - Strong",
    "off": "No post AA (use with 200%+ resolution = SSAA)",
}
UPSCALERS = {
    "bilinear": "Bilinear",
    "fsr": "AMD FSR 1 + CAS sharpening",
    "nearest": "Nearest",
}
FRAME_MODES = {
    "60": "60 FPS (native, correct game speed)",
    "60_vsync": "60 FPS + VSync",
    "display": "Match display refresh (frame limiter = Display)",
    "uncapped": "Uncapped limiter (benchmark only)",
}
MOTION_BLUR = {
    "stock": "Stock (replays only)",
    "off": "Off (also fixes black replay screen)",
    "gameplay": "In gameplay - 8 samples",
    "gameplay16": "In gameplay - 16 samples",
    "gameplay24": "In gameplay - 24 samples",
}
SHADOWS = {
    "stock": "Stock",
    "sharp": "Sharper",
    "sharp4": "Sharper - 4x filter samples",
    "sharp8": "Sharper - 8x filter samples",
}
RENDER_PATHS = {
    "auto": "Automatic by game version (wiki: CPU blit up to 1.05, color buffers after)",
    "color_buffers": "Write + Read Color Buffers",
    "cpu_blit": "Force CPU Blit (only correct up to 1.05)",
}
LICENSE_AREA = {"BCES": "SCEE", "NPEA": "SCEE", "BCUS": "SCEA", "NPUA": "SCEA", "BCJS": "SCEJ", "NPJA": "SCEJ",
                "BCAS": "SCEH", "NPHA": "SCEH", "BCKS": "SCEK"}
DEFAULT_LANGUAGE = {"SCEE": "English (UK)", "SCEA": "English (US)", "SCEJ": "Japanese", "SCEH": "English (US)",
                    "SCEK": "Korean"}
LANGUAGES = ["auto", "English (UK)", "English (US)", "German", "French", "Spanish", "Italian", "Dutch",
             "Portuguese (Portugal)", "Portuguese (Brazil)", "Polish", "Russian", "Turkish", "Finnish", "Swedish",
             "Danish", "Norwegian", "Japanese", "Korean", "Chinese (Traditional)", "Chinese (Simplified)"]
SPU_BLOCK = ["Safe", "Mega", "Giga"]
# Color grading in the GT6-patched RPCS3 (emulator patch 09): setting key -> RPCS3 "Video/Color Grading" key.
# All sliders are -100..100, 0 = neutral. Also editable live in the in-game home menu (Settings -> Color).
COLOR_GRADING = {
    "cg_brightness": "Brightness",
    "cg_contrast": "Contrast",
    "cg_gamma": "Gamma",
    "cg_shadows": "Shadows",
    "cg_highlights": "Highlights",
    "cg_saturation": "Saturation",
    "cg_vibrance": "Vibrance",
    "cg_temperature": "Temperature",
    "cg_tint": "Tint",
}
# GT6's own color correction (engine_color.py game patch, EU 1.22): setting key -> RPCS3 key in the same node.
# -100..100, 0 = neutral; the GT6-patched emulator also exposes them live in the home menu while the patch is on.
ENGINE_COLOR = {
    "cge_gain_r": "Engine Gain R", "cge_gain_g": "Engine Gain G", "cge_gain_b": "Engine Gain B",
    "cge_bias_r": "Engine Bias R", "cge_bias_g": "Engine Bias G", "cge_bias_b": "Engine Bias B",
    "cge_gamma_r": "Engine Gamma R", "cge_gamma_g": "Engine Gamma G", "cge_gamma_b": "Engine Gamma B",
    "cge_chroma": "Engine Chroma",
}
GRADING_SLIDERS = {**COLOR_GRADING, **ENGINE_COLOR}
SCHEDULERS = ["Operating System", "RPCS3 Scheduler", "RPCS3 Alternative Scheduler"]


@dataclass
class Settings:
    # display
    fullscreen: bool = True
    output_resolution: str = "1920x1080"   # PS3 video output mode
    resolution_scale: int = 150
    aspect: str = "16:9"
    aa: str = "mlaa_sharp"
    upscaler: str = "bilinear"
    cas_sharpening: int = 50
    anisotropic: int = 16
    frame_mode: str = "60"
    unlock_menu_fps: bool = True
    motion_blur: str = "stock"
    depth_of_field: bool = True
    shadows: str = "sharp"
    lamp_glare: float = 1.0
    fov_bumper: int = 0
    fov_cockpit: int = 0
    fov_roof: int = 0
    fov_chase: int = 0
    performance_overlay: bool = False
    # color grading (GT6-patched RPCS3 video-out pass), see COLOR_GRADING
    color_grading: bool = False
    cg_brightness: int = 0
    cg_contrast: int = 0
    cg_gamma: int = 0
    cg_shadows: int = 0
    cg_highlights: int = 0
    cg_saturation: int = 0
    cg_vibrance: int = 0
    cg_temperature: int = 0
    cg_tint: int = 0
    cg_dither: bool = True
    # GT6's own color correction (game patch), see ENGINE_COLOR
    engine_color: bool = False
    cge_gain_r: int = 0
    cge_gain_g: int = 0
    cge_gain_b: int = 0
    cge_bias_r: int = 0
    cge_bias_g: int = 0
    cge_bias_b: int = 0
    cge_gamma_r: int = 0
    cge_gamma_g: int = 0
    cge_gamma_b: int = 0
    cge_chroma: int = 0
    # emulation
    renderer: str = "Vulkan"
    gpu_adapter: str = ""            # empty = RPCS3 default
    spu_block_size: str = "Safe"
    thread_scheduler: str = "Operating System"
    zcull_queries_disabled: bool = True
    render_path: str = "auto"       # never all three of WCB/RCB/CPU blit together (RPCS3 wiki)
    accurate_rsx_reservation: bool = True
    multithreaded_rsx: bool = False
    async_texture_streaming: bool = False
    # GT6 binds tiled RSX memory (cellGcmSetTile); without this the race standings/name
    # strip and other HUD text can show coloured noise blocks
    handle_tiled_memory: bool = True
    audio_time_stretch: bool = True   # smooth audio through short FPS dips (intro/name screen)
    audio_buffer_ms: int = 50
    # controller: auto = first connected gamepad (else keyboard), pad = controller_device,
    # keyboard, manual = leave RPCS3's own input settings alone
    controller_mode: str = "auto"
    controller_device: str = ""
    # racing wheel -> RPCS3's emulated Logitech G27 (mapping recorded by the set-up wizard)
    wheel_enabled: bool = False
    wheel_name: str = ""
    wheel_mapping: dict[str, Any] = field(default_factory=dict)
    # extras
    use_gamemode: bool = False
    use_mangohud: bool = False
    # console region/language: region follows the disc; GT6 picks default units (km/h vs mph)
    # and the EU disc its text language from these
    console_language: str = "auto"
    # GT6's built-in developer menu (credits "Cashier", garage tools) via the Develop Settings patch
    dev_menu: bool = False
    # LAN
    lan_enabled: bool = False
    lan_bind_address: str = "0.0.0.0"
    # Online via community server (EU 1.22 "irekej Custom Server" patch + RPCN account)
    online_enabled: bool = False
    # user patches beyond the ones driven above: {name: {"enabled": bool, "values": {...}}}
    extra_patches: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Settings":
        """Unknown keys are dropped; values that are not valid choices (old/new launcher version,
        hand edits) fall back to the default instead of breaking every launch."""
        names = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in (d or {}).items() if k in names})
        default = cls()
        for k, choices in _CHOICES.items():
            if getattr(s, k) not in choices:
                setattr(s, k, getattr(default, k))
        for k in GRADING_SLIDERS:
            try:
                setattr(s, k, max(-100, min(100, int(getattr(s, k)))))
            except (TypeError, ValueError):
                setattr(s, k, 0)
        for f in fields(cls):
            dv = getattr(default, f.name)
            v = getattr(s, f.name)
            if isinstance(dv, bool) and not isinstance(v, bool):
                setattr(s, f.name, dv)
            elif isinstance(dv, (int, float)) and not isinstance(dv, bool):
                try:
                    setattr(s, f.name, type(dv)(v))
                except (TypeError, ValueError):
                    setattr(s, f.name, dv)
            elif isinstance(dv, dict) and not isinstance(v, dict):
                setattr(s, f.name, dict(dv))
        return s

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CHOICES: dict[str, Any] = {}  # filled below, after all choice tables exist


def needs_color_buffers(version: str | None) -> bool:
    return bool(version) and version > "01.05"


def render_flags(s: "Settings", version: str | None) -> tuple[bool, bool]:
    """(color_buffers, cpu_blit). RPCS3 wiki: <=1.05 -> CPU blit on, buffers off (higher FPS,
    no flicker, weaker lighting); >1.05 -> buffers on, CPU blit off (black world otherwise)."""
    mode = s.render_path
    if mode == "auto":
        mode = "color_buffers" if needs_color_buffers(version) else "cpu_blit"
    return (mode == "color_buffers", mode == "cpu_blit")


ONLINE_PATCH = "irekej Custom Server"
ONLINE_TITLES = {"BCES01893"}


def console_region(title_id: str) -> tuple[str, str]:
    area = LICENSE_AREA.get(title_id[:4], "SCEA")
    return area, DEFAULT_LANGUAGE.get(area, "English (US)")


def color_grading_config(s: Settings) -> dict[str, Any]:
    """RPCS3 ``Video/Color Grading`` node (only read by the GT6-patched build, ignored by stock RPCS3)."""
    node: dict[str, Any] = {"Enabled": s.color_grading, "Dither": s.cg_dither}
    node.update({rk: int(getattr(s, k)) for k, rk in GRADING_SLIDERS.items()})
    return node


def color_grading_from_config(node: Any) -> dict[str, Any]:
    """Inverse of :func:`color_grading_config` for a node read back with the string loader
    (the in-game home menu saves its sliders into the per-game config)."""
    if not isinstance(node, dict):
        return {}
    out: dict[str, Any] = {}
    for key, rk in (("color_grading", "Enabled"), ("cg_dither", "Dither")):
        v = str(node.get(rk, "")).strip().lower()
        if v in ("true", "false"):
            out[key] = v == "true"
    for k, rk in GRADING_SLIDERS.items():
        try:
            out[k] = max(-100, min(100, int(str(node.get(rk)).strip())))
        except (TypeError, ValueError):
            pass
    return out


def build_custom_config(s: Settings, version: str | None, title_id: str = "") -> dict[str, Any]:
    """RPCS3 per-game config (only the keys we care about; RPCS3 fills the rest)."""
    cb, cpu_blit = render_flags(s, version)
    limit = {"60": "Auto", "60_vsync": "Auto", "display": "Display", "uncapped": "Off"}[s.frame_mode]
    vsync = "Full" if s.frame_mode == "60_vsync" else "Disabled"
    scale = s.resolution_scale
    out_mode = {"bilinear": "Bilinear", "fsr": "FidelityFX Super Resolution", "nearest": "Nearest"}[s.upscaler]
    video: dict[str, Any] = {
        "Renderer": s.renderer,
        "Resolution": s.output_resolution if s.output_resolution in OUTPUT_RESOLUTIONS else "1920x1080",
        "Aspect ratio": "16:9",
        "Frame limit": limit,
        "MSAA": "Auto",
        "Shader Mode": "Async Recompiler with Shader Interpreter",
        "VSync Mode": vsync,
        "Write Color Buffers": cb,
        "Read Color Buffers": cb,
        "Stretch To Display Area": ASPECTS.get(s.aspect) is not None,
        "Disable ZCull Occlusion Queries": s.zcull_queries_disabled,
        "Force CPU Blit": cpu_blit,
        "Handle RSX Memory Tiling": s.handle_tiled_memory,
        "Multithreaded RSX": s.multithreaded_rsx,
        "Resolution Scale": scale,
        "Anisotropic Filter Override": s.anisotropic,
        "Output Scaling Mode": out_mode,
        "FidelityFX CAS Sharpening Intensity": s.cas_sharpening,
        "Vulkan": {"Asynchronous Texture Streaming": s.async_texture_streaming},
        "Performance Overlay": {"Enabled": s.performance_overlay, "Enable Framerate Graph": s.performance_overlay,
                                "Enable Frametime Graph": s.performance_overlay, "Detail level": "Medium"},
        "Color Grading": color_grading_config(s),
    }
    if s.gpu_adapter:
        video["Vulkan"]["Adapter"] = s.gpu_adapter
    cfg: dict[str, Any] = {
        "Core": {
            "PPU Decoder": "Recompiler (LLVM)",
            "SPU Decoder": "Recompiler (LLVM)",
            "LLVM Precompilation": True,
            "SPU Block Size": s.spu_block_size,
            "Thread Scheduler Mode": s.thread_scheduler,
            "Accurate RSX reservation access": s.accurate_rsx_reservation,
            "RSX FIFO Fetch Accuracy": "Atomic",
        },
        "Video": video,
        "Audio": {
            "Enable Buffering": True,
            "Desired Audio Buffer Duration": s.audio_buffer_ms,
            "Enable Time Stretching": s.audio_time_stretch,
        },
        "Miscellaneous": {
            "Start games in fullscreen mode": s.fullscreen,
            "Exit RPCS3 when process finishes": True,
            "Show shader compilation hint": False,
            "Prevent display sleep while running games": True,
            "Enable GameMode": s.use_gamemode,
        },
    }
    if s.lan_enabled:
        cfg["Net"] = {"Internet enabled": "Connected", "PSN status": "Disconnected",
                      "IP address": "0.0.0.0", "Bind address": s.lan_bind_address}
        cfg["System"] = {"Process ARGV": {"lan": "lanmode"}}
    elif s.online_enabled:
        # RPCN account is configured once in RPCS3 (Advanced -> Open RPCS3 -> Configuration -> RPCN)
        cfg["Net"] = {"Internet enabled": "Connected", "PSN status": "RPCN"}
        cfg["System"] = {"Process ARGV": {}}
    else:
        cfg["Net"] = {"Internet enabled": "Disconnected", "PSN status": "Disconnected"}
        cfg["System"] = {"Process ARGV": {}}
    area, lang = console_region(title_id)
    cfg["System"]["License Area"] = area
    cfg["System"]["Language"] = lang if s.console_language == "auto" else s.console_language
    return cfg


# --------------------------------------------------------------------------- patches

def desired_patches(s: Settings, version: str | None) -> dict[str, dict[str, float]]:
    """Patch name -> configurable values, derived from the high level settings.

    Names match AlexHaust's imported_patch.yml / RPCS3 patch.yml; any that do not
    exist for the current serial+version are silently skipped by the caller."""
    want: dict[str, dict[str, float]] = {}
    if s.aa == "mlaa_sharp":
        want["Use Sharper MLAA"] = {}
    elif s.aa == "mlaa_strong":
        want["Use Sharper MLAA - Strong"] = {}
    elif s.aa == "off":
        want["Disable MLAA"] = {}
    ratio = ASPECTS.get(s.aspect)
    if ratio:
        want["Aspect Ratio"] = {"Aspect Ratio": ratio}
    if s.unlock_menu_fps:
        want["Unlock FPS"] = {}
    if s.motion_blur == "off":
        want["Disable Motion Blur"] = {}
    elif s.motion_blur == "gameplay":
        want["Enable Motion Blur in Gameplay"] = {}
    elif s.motion_blur == "gameplay16":
        want["Enable Motion Blur in Gameplay - 16 Samples"] = {}
    elif s.motion_blur == "gameplay24":
        want["Enable Motion Blur in Gameplay - 24 Samples"] = {}
    if not s.depth_of_field:
        want["Disable Depth of Field"] = {}
    if s.shadows == "sharp":
        want["Sharper Shadows"] = {}
    elif s.shadows == "sharp4":
        want["Sharper Shadows - 4x Filter Samples"] = {}
    elif s.shadows == "sharp8":
        want["Sharper Shadows - 8x Filter Samples"] = {}
    if abs(s.lamp_glare - 1.0) > 1e-6:
        want["Lamp Glare Intensity"] = {"Glare Intensity": s.lamp_glare}
    if any((s.fov_bumper, s.fov_cockpit, s.fov_roof, s.fov_chase)):
        want["Extended FOV"] = {"Bumper Vertical FOV": s.fov_bumper, "Cockpit Vertical FOV": s.fov_cockpit,
                                "Roof/Hood Vertical FOV": s.fov_roof, "Chase Vertical FOV": s.fov_chase}
    # Resolution-scale companion fixes: always on. They adapt to the current scale, and the scale can
    # change while the game runs (RPCS3 home menu slider, buffer rebuild after alt-tab) - without
    # them GT6's bloom/glare turns into green blotches.
    want["Bloom/Glare Resolution Scale Fix"] = {}
    want["Auto Exposure Resolution Scale Fix"] = {}
    want["Smoke and Dust Resolution Scale Fix"] = {}
    want["Movie Playback Fix"] = {}
    if s.engine_color:
        from . import engine_color
        want[engine_color.PATCH_NAME] = engine_color.patch_values(s)
    if s.lan_enabled or s.dev_menu:
        want["Develop Settings"] = {}
    if s.lan_enabled:
        want["LAN Room Sync Without PSN"] = {}
        want["LAN Host Member Info"] = {}
    if s.online_enabled and not s.lan_enabled:
        want[ONLINE_PATCH] = {}
    # user extras override
    for name, e in (s.extra_patches or {}).items():
        if e.get("enabled"):
            vals = {}
            for k, v in (e.get("values") or {}).items():
                try:
                    vals[k] = float(v)
                except (TypeError, ValueError):
                    pass  # broken value -> patch default
            want[name] = vals
        else:
            want.pop(name, None)
    return want


_CHOICES.update({
    "resolution_scale": RESOLUTION_SCALES, "aspect": ASPECTS, "aa": AA_MODES, "upscaler": UPSCALERS,
    "frame_mode": FRAME_MODES, "motion_blur": MOTION_BLUR, "shadows": SHADOWS, "spu_block_size": SPU_BLOCK,
    "thread_scheduler": SCHEDULERS, "render_path": RENDER_PATHS, "output_resolution": OUTPUT_RESOLUTIONS,
    "console_language": LANGUAGES, "controller_mode": ["auto", "pad", "keyboard", "manual"],
})
