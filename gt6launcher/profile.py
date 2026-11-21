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
import os
import sys
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
    "off": "No post AA - skips GT6's post pass (sharpest, sky/clouds may band; use 200%+)",
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
    "cpu_blit": "Force CPU Blit (<= 1.05, or 1.22 with Speedboost for PCIe 3.0 x8 / narrow bus GPUs)",
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
# Cockpit head motion (head_motion.py game patch + GT6-patched RPCS3 patch 16): setting key -> RPCS3
# "Video/Head Motion" key, with its range. Also editable live in the in-game home menu (Settings -> Head Motion).
HEAD_MOTION = {
    "hm_strength": ("Strength", 1, 20),
    "hm_braking": ("Braking Nod", 0, 300),
    "hm_lean": ("Cornering Lean", 0, 300),
    "hm_turn": ("Cornering Turn", 0, 300),
    "hm_slide": ("Head Slide", 0, 300),
}
SCHEDULERS = ["Operating System", "RPCS3 Scheduler", "RPCS3 Alternative Scheduler"]
ZCULL_ACCURACY = ["Approximate", "Relaxed", "Precise"]


def detect_system_ram_gb() -> float:
    """Detect total system physical RAM in GiB across Linux and Windows."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / (1024 ** 3)
        elif hasattr(os, "sysconf"):
            if "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
                return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3)
    except Exception:
        pass
    return 16.0


def default_spu_block_size() -> str:
    """Select best SPU Block Size based on total system RAM.

    - Under 8 GB RAM (e.g. 4-6 GB): 'Safe' to prevent compiler memory pressure / OOM-killer.
    - 8 GB RAM and above: 'Mega' for optimal performance and thread stability in GT6.
    (Note: 'Giga' is never auto-selected as it causes thread deadlocks and audio desyncs in GT6).
    """
    ram = detect_system_ram_gb()
    return "Safe" if ram < 7.0 else "Mega"


def detect_gpu_pcie_bottleneck() -> bool:
    """Return True if a discrete GPU is detected running on a narrow PCIe link (<= PCIe 3.0 x8, ~8GB/s)."""
    if sys.platform == "linux":
        try:
            import glob
            for dev in glob.glob("/sys/bus/pci/devices/*"):
                class_path = os.path.join(dev, "class")
                if os.path.isfile(class_path):
                    with open(class_path, "r") as f:
                        cls = f.read().strip()
                    if cls.startswith("0x03"):
                        speed_path = os.path.join(dev, "max_link_speed")
                        if not os.path.isfile(speed_path):
                            speed_path = os.path.join(dev, "current_link_speed")
                        width_path = os.path.join(dev, "max_link_width")
                        if not os.path.isfile(width_path):
                            width_path = os.path.join(dev, "current_link_width")

                        speed_val = 0.0
                        if os.path.isfile(speed_path):
                            with open(speed_path, "r") as f:
                                for part in f.read().split():
                                    try:
                                        speed_val = float(part)
                                        break
                                    except ValueError:
                                        pass
                        width_val = 16
                        if os.path.isfile(width_path):
                            with open(width_path, "r") as f:
                                try:
                                    width_val = int(f.read().strip())
                                except ValueError:
                                    pass
                        if 0 < speed_val <= 8.0 and width_val <= 8:
                            return True
        except Exception:
            pass
    return False


def _is_handheld_platform(cpu_name: str, dmi_info: str = "") -> bool:
    """Return True if the CPU or board/product DMI clearly identifies a handheld gaming PC."""
    combined_l = f"{cpu_name} {dmi_info}".lower()
    # Explicit substring matches (safe from chipset collisions like Z170/Z270)
    handheld_phrases = (
        "custom apu 0405", "custom apu 0932", "aerith", "sephiroth", "vangogh", "steam deck", "steamdeck",
        "ryzen z1", "z1 extreme", "ryzen z2", "z2 extreme", "z2 go",
        "rog ally", "ally x", "rc71l", "rc72l",
        "legion go", "83e1", "83l3",
        "msi claw", "claw a8", "claw 8", "claw 7", "claw a1m",
        "strix halo", "ai max+ 395", "ai max 395", "ai max 388", "ai max 385", "ryzen ai max",
        "gpd win", "ayaneo", "onexplayer", "aokzoe", "zotac zone",
    )
    if any(h in combined_l for h in handheld_phrases):
        return True
    # Steam Deck: DMI is read as "board product vendor ..." = "Jupiter Jupiter Valve Valve" (LCD) or
    # "Galileo Galileo Valve Valve" (OLED), so match the words independently of their order.
    words = set(combined_l.split())
    return "valve" in words and bool(words & {"jupiter", "galileo"})


def detect_gpu_name() -> str:
    """Fallback GPU name detection when rpcs3.log does not exist yet (Windows registry / Linux lspci)."""
    candidates: list[str] = []
    if sys.platform == "win32":
        try:
            import winreg
            base_key = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key) as cls_key:
                for i in range(16):
                    try:
                        sub = winreg.EnumKey(cls_key, i)
                        if not sub.isdigit():
                            continue
                        with winreg.OpenKey(cls_key, sub) as dev_key:
                            desc, _ = winreg.QueryValueEx(dev_key, "DriverDesc")
                            if desc:
                                candidates.append(str(desc).strip())
                    except OSError:
                        break
        except Exception:
            pass
    elif sys.platform == "linux":
        try:
            import shutil
            import subprocess
            if shutil.which("lspci"):
                out = subprocess.check_output(["lspci"], text=True, errors="replace", timeout=2)
                for line in out.splitlines():
                    low = line.lower()
                    if "vga compatible controller" in low or "3d controller" in low or "display controller" in low:
                        parts = line.split(":", 2)
                        if len(parts) == 3:
                            candidates.append(parts[2].strip())
        except Exception:
            pass
    if not candidates:
        return ""
    # Prefer discrete GPU over integrated graphics (matching Vulkan discrete-first ordering)
    discrete_markers = ("rtx", "gtx", "rx ", "radeon pro", "arc a", "arc b", "arc(tm) a", "arc(tm) b")
    for c in candidates:
        if any(m in c.lower() for m in discrete_markers):
            return c
    for c in candidates:
        if "microsoft basic" not in c.lower() and "llvmpipe" not in c.lower():
            return c
    return candidates[0]


def detect_cpu_info() -> dict[str, Any]:
    """Detect CPU model name, thread count, and architecture characteristics."""
    threads = os.cpu_count() or 4
    name = ""
    dmi_info = ""
    if sys.platform == "linux":
        try:
            with open("/proc/cpuinfo", "r", errors="replace") as f:
                for line in f:
                    if "model name" in line:
                        name = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
        try:
            for dmi_file in (
                "/sys/devices/virtual/dmi/id/board_name",
                "/sys/devices/virtual/dmi/id/product_name",
                "/sys/devices/virtual/dmi/id/sys_vendor",
                "/sys/devices/virtual/dmi/id/board_vendor",
            ):
                if os.path.isfile(dmi_file):
                    with open(dmi_file, "r", errors="replace") as f:
                        dmi_info += " " + f.read().strip()
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            name = name.strip()
        except Exception:
            pass
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
            for subk in ("BaseBoardProduct", "SystemProductName", "BaseBoardManufacturer", "BIOSVersion"):
                try:
                    dmi_val, _ = winreg.QueryValueEx(key, subk)
                    if dmi_val:
                        dmi_info += " " + str(dmi_val).strip()
                except Exception:
                    pass
        except Exception:
            pass
    if not name:
        import platform
        name = platform.processor() or "Generic Processor"
    combined_l = (name + " " + dmi_info).lower()
    is_intel_hybrid = "intel" in combined_l and any(
        g in combined_l for g in ("12th gen", "13th gen", "14th gen", "core ultra", "-12", "-13", "-14", "lunar lake", "arrow lake")
    )
    is_handheld_cpu = _is_handheld_platform(name, dmi_info)
    return {
        "name": name,
        "threads": threads,
        "is_intel_hybrid": is_intel_hybrid,
        "is_handheld": is_handheld_cpu,
        "board_name": dmi_info.strip(),
        "dmi_info": dmi_info.strip(),
        "is_pcie_bottleneck": detect_gpu_pcie_bottleneck(),
    }


def recommend_settings_for_hardware(cpu_info: dict[str, Any], gpu_name: str, ram_gb: float) -> tuple[dict[str, Any], list[str]]:
    """Determine the optimal GT6 settings based on detected CPU, GPU, and RAM."""
    cpu_name = cpu_info.get("name", "Generic CPU")
    threads = cpu_info.get("threads", 4)
    is_intel_hybrid = cpu_info.get("is_intel_hybrid", False)
    is_handheld_cpu = cpu_info.get("is_handheld", False)
    dmi_info = cpu_info.get("dmi_info", "") or cpu_info.get("board_name", "")
    dmi_l = dmi_info.lower()
    cpu_l = cpu_name.lower()
    gpu_l = (gpu_name or "").lower()
    is_pcie_bus_limited = cpu_info.get("is_pcie_bottleneck", False)

    # Detect GPUs with narrow PCIe bus (e.g. x8 or x4 lanes: RTX 5060, 4060, 3050, RX 7600, 6600, etc.)
    pcie_x8_gpus = ("5060", "4060", "3050", "7600", "6600", "6650", "6500", "6400", "5500", "a380", "a310")
    is_pcie_x8_gpu = any(g in gpu_l for g in pcie_x8_gpus)

    # Detect PCIe 3.0 vs PCIe 4.0+ motherboards/chipsets
    pcie3_chipsets = ("b450", "b350", "a320", "x370", "x470", "a520", "h310", "b360", "b365", "h370", "z370", "z390", "h410", "b460", "h470", "z490", "h510")
    pcie4_plus_chipsets = ("b550", "x570", "b650", "x670", "b850", "x870", "z590", "b560", "h570", "z690", "b660", "h670", "z790", "b760", "h770", "z890", "b860")
    is_pcie3_board = any(c in dmi_l for c in pcie3_chipsets)
    is_pcie4_plus_board = any(c in dmi_l for c in pcie4_plus_chipsets)

    # Issue #36: RTX 5060 on B450 / ASUS PRIME B450M-K with Ryzen 5 5600 (or unknown board with 5600+5060, unless known PCIe 4.0+)
    is_issue36_exact = "5060" in gpu_l and (
        "b450" in dmi_l or "prime b450m-k" in dmi_l or ("5600" in cpu_l and not is_pcie4_plus_board)
    )

    # Narrow PCIe bus bottleneck (Issue #36): RSX thread saturated by color buffer readback over PCIe 3.0 x8 (~8 GB/s)
    is_pcie_bandwidth_bottleneck = (
        is_issue36_exact
        or (is_pcie_x8_gpu and (is_pcie3_board or is_pcie_bus_limited))
    )

    is_amd = any(x in gpu_l for x in ("amd", "radeon"))
    is_discrete_gpu = any(x in gpu_l for x in ("rtx", "gtx", "rx ", "radeon pro", "arc a", "arc b", "arc(tm) a", "arc(tm) b", "quadro"))
    is_igpu = (not is_discrete_gpu) and (
        is_handheld_cpu
        or any(x in gpu_l for x in ("steam deck", "steamdeck", "vangogh", "custom gpu 0405", "custom gpu 0932", "vega", "660m", "680m", "740m", "760m", "780m", "uhd", "hd graphics", "iris", "130v", "140v"))
        or ("graphics" in gpu_l)
    )

    is_high_end = not is_igpu and not is_pcie_bandwidth_bottleneck and any(
        x in gpu_l for x in (
            "5090", "5080", "5070", "4090", "4080", "4070", "3090", "3080", "3070",
            "7900", "7800", "6950", "6900", "6800", "9060", "9070", "9080", "xtx"
        )
    )

    settings: dict[str, Any] = {
        "render_path": "auto",
        "lamp_glare": 1.0,
    }
    summary: list[str] = []

    # SPU Block Size
    if ram_gb < 7.0:
        settings["spu_block_size"] = "Safe"
        summary.append(f"RAM ({ram_gb:.0f} GB) -> SPU Block Size: Safe (low compiler memory)")
    else:
        settings["spu_block_size"] = "Mega"
        summary.append(f"RAM ({ram_gb:.0f} GB) -> SPU Block Size: Mega (optimal GT6 thread pacing)")

    # Thread Scheduler
    if is_intel_hybrid:
        settings["thread_scheduler"] = "RPCS3 Alternative Scheduler"
        summary.append(f"CPU ({cpu_name}) -> RPCS3 Alternative Scheduler (avoids E-core thread stalls)")
    else:
        settings["thread_scheduler"] = "Operating System"
        summary.append(f"CPU ({cpu_name}, {threads} threads) -> OS Thread Scheduler")

    # GPU & Visuals
    display_gpu = gpu_name or "Integrated Graphics"
    if is_pcie_bandwidth_bottleneck:
        settings["render_path"] = "cpu_blit"
        settings["output_resolution"] = "1920x1080"
        settings["resolution_scale"] = 100
        settings["upscaler"] = "fsr"
        settings["cas_sharpening"] = 60
        settings["shadows"] = "sharp"
        settings["aa"] = "off"
        settings["lamp_glare"] = 0.0
        settings["strict_rendering"] = False
        board_desc = "B450 / PCIe 3.0" if (is_pcie3_board or "b450" in dmi_l) else "PCIe 3.0 x8 bus"
        summary.append(
            f"GPU ({display_gpu}) on {board_desc} -> PCIe Bottleneck Fix (Issue #36): "
            f"Force CPU Blit + Speedboost, 1080p, 100% Scale + FSR, MLAA Off, Glare 0 (solid 60 FPS)"
        )
    elif is_igpu:
        settings["output_resolution"] = "1280x720"
        settings["resolution_scale"] = 100
        settings["upscaler"] = "fsr"
        settings["cas_sharpening"] = 60
        settings["shadows"] = "stock"
        settings["aa"] = "mlaa_sharp"
        settings["strict_rendering"] = False
        summary.append(f"GPU ({display_gpu}) -> Handheld/iGPU: 720p, 100% Scale + FSR 1, Stock Shadows")
    elif is_high_end:
        settings["output_resolution"] = "1920x1080"
        settings["resolution_scale"] = 200
        settings["upscaler"] = "bilinear"
        settings["shadows"] = "sharp"
        # Keep MLAA on: "Disable MLAA" combined with resolution scale > 100% shows a green band / green
        # image on 1.22 (Issues #36, #39).
        settings["aa"] = "mlaa_sharp"
        settings["strict_rendering"] = is_amd
        amd_fix = ", Strict Rendering: ON (fixes AMD hood reflection/strobe)" if is_amd else ""
        summary.append(f"GPU ({display_gpu}) -> High-End: 1080p output, 200% Scale + Sharper MLAA, "
                       f"Sharp Shadows{amd_fix}")
    else:
        settings["output_resolution"] = "1920x1080"
        settings["resolution_scale"] = 150
        settings["upscaler"] = "bilinear"
        settings["shadows"] = "sharp"
        settings["aa"] = "mlaa_sharp"
        settings["strict_rendering"] = is_amd
        amd_fix = ", Strict Rendering: ON (fixes AMD hood reflection/strobe)" if is_amd else ""
        summary.append(f"GPU ({display_gpu}) -> Mid-Range: 1080p output, 150% Scale, Sharp Shadows{amd_fix}")

    # Core stability settings
    # ZCull queries off: with them on, the car delivery / part install screens stall at 1-5 fps
    # (RSX semaphore_acquire timeouts, Issues #40, #42). RPCS3 wiki / AlexHaust recommendation.
    settings["zcull_queries_disabled"] = True
    settings["zcull_accuracy"] = "Approximate"
    settings["accurate_rsx_reservation"] = True
    settings["handle_tiled_memory"] = True
    settings["multithreaded_rsx"] = False
    settings["unlock_menu_fps"] = True

    return settings, summary


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
    # Cockpit head motion from G-forces (head_motion.py game patch)
    head_motion: bool = False
    hm_strength: int = 5
    hm_braking: int = 100
    hm_lean: int = 100
    hm_turn: int = 100
    hm_slide: int = 100
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
    spu_block_size: str = field(default_factory=default_spu_block_size)
    thread_scheduler: str = "Operating System"
    zcull_queries_disabled: bool = True   # see auto-config note (Issues #40, #42)
    strict_rendering: bool = False
    zcull_accuracy: str = "Approximate"
    render_path: str = "auto"       # never all three of WCB/RCB/CPU blit together (RPCS3 wiki)
    accurate_rsx_reservation: bool = True
    multithreaded_rsx: bool = False
    async_texture_streaming: bool = False
    # GT6 binds tiled RSX memory (cellGcmSetTile); without this the race standings/name
    # strip and other HUD text can show coloured noise blocks
    handle_tiled_memory: bool = True
    audio_format: str = "Stereo"
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
    wheel_reverse_ffb: bool = False
    # extras
    use_gamemode: bool = False
    use_mangohud: bool = False
    # UI language for launcher
    ui_language: str = "en"
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
        for k, (_rk, lo, hi) in HEAD_MOTION.items():
            try:
                setattr(s, k, max(lo, min(hi, int(getattr(s, k)))))
            except (TypeError, ValueError):
                setattr(s, k, getattr(default, k))
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


def head_motion_config(s: Settings) -> dict[str, Any]:
    """RPCS3 ``Video/Head Motion`` node (only read by the GT6-patched build, ignored by stock RPCS3)."""
    return {rk: int(getattr(s, k)) for k, (rk, _lo, _hi) in HEAD_MOTION.items()}


def head_motion_from_config(node: Any) -> dict[str, Any]:
    """Inverse of :func:`head_motion_config` (the in-game home menu saves into the per-game config)."""
    if not isinstance(node, dict):
        return {}
    out: dict[str, Any] = {}
    for k, (rk, lo, hi) in HEAD_MOTION.items():
        try:
            out[k] = max(lo, min(hi, int(str(node.get(rk)).strip())))
        except (TypeError, ValueError):
            pass
    return out


def ingame_settings_from_config(video: Any) -> dict[str, Any]:
    """Settings the in-game home menu can change, read back from a per-game config's Video node."""
    video = video if isinstance(video, dict) else {}
    return {**color_grading_from_config(video.get("Color Grading")), **head_motion_from_config(video.get("Head Motion"))}


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
        "Strict Rendering Mode": s.strict_rendering,
        "Relaxed ZCULL Sync": s.zcull_accuracy == "Relaxed",
        "Accurate ZCULL stats": s.zcull_accuracy == "Precise",
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
        "Head Motion": head_motion_config(s),
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
            "Audio Format": s.audio_format,
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
            # Otherwise the game keeps rendering under the home menu; GT6 lost the Vulkan device there
            "Pause Emulation During Home Menu": True,
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
    if s.render_path == "cpu_blit":
        # Force CPU Blit on GT6 1.22: bypasses PCIe Write Color Buffer readback bottleneck (Issue #36).
        # Requires Speedboost and Disable MLAA patches to avoid black 3D world and broken crowd sprites.
        want["Speedboost (disable Write Color Buffers)"] = {}
        want["Disable MLAA"] = {}
        want.pop("Use Sharper MLAA", None)
        want.pop("Use Sharper MLAA - Strong", None)
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
    if s.head_motion:
        from . import head_motion
        want[head_motion.PATCH_NAME] = head_motion.patch_values(s)
    if s.engine_color:
        from . import engine_color
        want[engine_color.PATCH_NAME] = engine_color.patch_values(s)
    if s.lan_enabled or s.dev_menu:
        want["Develop Settings"] = {}
    if s.lan_enabled:
        want["LAN Room Sync Without PSN"] = {}
        want["LAN Host Member Info"] = {}
        # research probe (docs/re/gt6-lan-ai.md): inert until N is written via gt6_live.txt
        from . import lan_ai_probe
        want[lan_ai_probe.PATCH_NAME] = {}
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
    "zcull_accuracy": ZCULL_ACCURACY,
})
