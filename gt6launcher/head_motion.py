"""Cockpit head motion from driving G-forces, using GT6's own neck rig (EMAIN 1.22, EU).

Reverse engineered from the decrypted EMAIN.SELF (notes: docs/re/gt6-head-motion.md):

* ``GTCamera::OnboardImplement`` owns two ``GTCamera::ImpactBlurCamera``. Their update (0x2F8F0C) measures
  the car's acceleration every frame, converts it to the car's frame and feeds a complete neck model:
  two ``DriverHeadDamper`` springs slide the head (fore/aft, sideways) and three springs pitch, yaw and
  roll it around a neck pivot 15 cm below / 6 cm behind the eyes (apply: 0x2F8A08).
* Stock GT6 only uses it for crashes: it is fed the change of acceleration between frames (jerk,
  0x2F90B0), an axis must exceed 200 m/s^2 (0x1130078) and the car must report a collision this frame
  (virtual call at 0x2F94C4), so the cockpit looks static while driving.

This patch feeds the rig the acceleration itself, skips the collision check, drops the threshold and scales
the input (normaliser at 0x113007C / 0x1130080, stock 500), so braking and cornering move the head through
GT6's own springs. Per-movement gains: pitch (0x11300A8) and roll (0x11300B0) are only used by this rig and
are written in place; yaw and head slide share their constants with other cameras, so their loads are
redirected to two floats of the patch's own (0x155F840 / 0x155F844, zero tail of the mapped text page).

The GT6-patched emulator (patch 16, Emu/RSX/gt6_head_motion.h) rewrites the same values every frame from
Video/Head Motion while this patch is active, so the home menu sliders work live.
"""
from __future__ import annotations

PATCH_NAME = "Cockpit Head Motion (experimental)"
VERIFIED_TITLES = {"BCES01893"}

LIS_R9_156 = 0x3D200156      # lis r9, 0x156  (r9 = 0x1560000)
# (address, new word, original word, comment)
CODE = [
    (0x002F90B0, 0x60000000, 0x1021004A, "nop (was vsubfp v1,v1,v0): feed acceleration, not jerk"),
    (0x002F949C, 0x48000070, 0x881F01E4, "b 0x2F950C (was lbz r0,0x1e4(r31)): skip collision gate"),
    (0x002F9528, LIS_R9_156, 0x3D200113, "lis r9, 0x156 (was 0x113)"),
    (0x002F952C, 0xC389F844, 0xC3890098, "lfs f28, -0x7bc(r9): head slide gain from 0x155F844"),
    (0x002F9624, LIS_R9_156, 0x3D200113, "lis r9, 0x156 (was 0x113)"),
    (0x002F9634, 0xC029F840, 0xC02900AC, "lfs f1, -0x7c0(r9): yaw gain from 0x155F840"),
]
THRESHOLD = 0x01130078       # per-axis acceleration threshold, m/s^2 (stock 200)
CLAMP_MIN = 0x0113007C       # -normaliser (stock -500)
CLAMP_MAX = 0x01130080       # +normaliser (stock 500): input = clamp(accel) / normaliser
PITCH = 0x011300A8
ROLL = 0x011300B0
YAW = 0x0155F840
SLIDE = 0x0155F844

# GT6's stock values. Must match rpcs3 Emu/RSX/gt6_head_motion.h.
STOCK_NORMALISER = 500.0
STOCK = {"Pitch Gain": -1.0471976, "Roll Gain": 0.87266463, "Yaw Gain": 1.3962634, "Slide Gain": -10.0}
# launcher setting -> patch value it scales
GAIN_SETTING = {"Pitch Gain": "hm_braking", "Roll Gain": "hm_lean", "Yaw Gain": "hm_turn", "Slide Gain": "hm_slide"}
GAIN_ADDR = {"Pitch Gain": PITCH, "Roll Gain": ROLL, "Yaw Gain": YAW, "Slide Gain": SLIDE}

STRENGTH_MIN, STRENGTH_MAX, STRENGTH_DEFAULT = 1, 20, 5
PERCENT_MIN, PERCENT_MAX, PERCENT_DEFAULT = 0, 300, 100


def normaliser(strength: int) -> float:
    s = max(STRENGTH_MIN, min(STRENGTH_MAX, int(strength)))
    return round(STOCK_NORMALISER / s, 4)


def gain(name: str, percent: int) -> float:
    p = max(PERCENT_MIN, min(PERCENT_MAX, int(percent)))
    return round(STOCK[name] * p / 100.0, 6)


def patch_values(s) -> dict[str, float]:
    n = normaliser(getattr(s, "hm_strength", STRENGTH_DEFAULT))
    out = {"Threshold": 0.0, "Clamp Min": -n, "Clamp Max": n}
    for name, key in GAIN_SETTING.items():
        out[name] = gain(name, getattr(s, key, PERCENT_DEFAULT))
    return out


def _range(name: str, value: float, lo: float, hi: float) -> list[str]:
    return [f'      "{name}":', "        Type: double_range", f"        Value: {value}",
            f"        Min: {lo}", f"        Max: {hi}"]


def patch_yaml(title_id: str) -> str:
    """Patch entry for the launcher's <TITLE>_patch.yml; empty for titles not checked."""
    if title_id not in VERIFIED_TITLES:
        return ""
    n = normaliser(STRENGTH_DEFAULT)
    lines = [
        f'  "{PATCH_NAME}":',
        "    Games:",
        '      "Gran Turismo 6":',
        f"        {title_id}: [ 01.22 ]",
        '    Author: "GT6 Launcher"',
        '    Notes: "Drives GT6\'s own cockpit neck rig (head slide, pitch, yaw, roll) from normal driving '
        'G-forces instead of only crashes, with a gain per movement. Experimental."',
        "    Patch Version: 1.2",
        "    Configurable Values:",
    ]
    lines += _range("Threshold", 0.0, 0.0, 200.0)
    lines += _range("Clamp Min", -n, -500.0, -10.0)
    lines += _range("Clamp Max", n, 10.0, 500.0)
    for name, stock in STOCK.items():
        lo, hi = sorted((0.0, round(stock * PERCENT_MAX / 100.0, 6)))
        lines += _range(name, stock, lo, hi)
    lines.append("    Patch:")
    for addr, word, orig, comment in CODE:
        lines.append(f"      - [ be32, {addr:#010x}, {word:#010x} ]  # {comment} [{orig:#010x}]")
    lines.append(f'      - [ bef32, {THRESHOLD:#010x}, "Threshold" ]')
    lines.append(f'      - [ bef32, {CLAMP_MIN:#010x}, "Clamp Min" ]')
    lines.append(f'      - [ bef32, {CLAMP_MAX:#010x}, "Clamp Max" ]')
    for name, addr in GAIN_ADDR.items():
        lines.append(f'      - [ bef32, {addr:#010x}, "{name}" ]')
    return "\n".join(lines) + "\n"
