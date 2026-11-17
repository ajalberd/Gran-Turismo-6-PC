"""Cockpit head motion from driving G-forces, using GT6's own neck rig (EMAIN 1.22, EU).

Reverse engineered from the decrypted EMAIN.SELF (notes: docs/re/gt6-head-motion.md):

* ``GTCamera::OnboardImplement`` owns two ``GTCamera::ImpactBlurCamera``. Their update (0x2F8F0C) measures
  the car's acceleration every frame, converts it to the car's frame and feeds a complete neck model:
  two ``DriverHeadDamper`` springs slide the head (fore/aft, sideways) and three springs pitch, yaw and
  roll it around a neck pivot 15 cm below / 6 cm behind the eyes (apply: 0x2F8A08).
* Stock GT6 only uses it for crashes: an axis must exceed 200 m/s^2 (0x1130078) and the car must report a
  collision this frame (virtual call at 0x2F94C4), so the cockpit looks static while driving.

It is also fed the change of acceleration between frames (jerk, 0x2F90B0), which only crashes make large.
This patch feeds it the acceleration itself, skips the collision check, lowers the threshold and scales the acceleration up (smaller
normaliser at 0x113007C / 0x1130080, stock 500), so normal braking and cornering move the head through
GT6's own springs and gains. Crash reactions keep working, capped at the same normalised limit.
"""
from __future__ import annotations

PATCH_NAME = "Cockpit Head Motion (experimental)"
VERIFIED_TITLES = {"BCES01893"}

JERK = 0x002F90B0            # vsubfp v1, v1, v0: accel - previous accel (GT6 feeds the rig jerk)
JERK_ORIGINAL = 0x1021004A
NOP = 0x60000000             # -> the rig gets the acceleration itself
GATE = 0x002F949C            # lbz r0, 0x1e4(r31): collision gate in ImpactBlurCamera::update
GATE_ORIGINAL = 0x881F01E4
GATE_SKIP = 0x48000070       # b 0x2F950C (straight to the channel update)
THRESHOLD = 0x01130078       # per-axis acceleration threshold, m/s^2 (stock 200)
CLAMP_MIN = 0x0113007C       # -normaliser (stock -500)
CLAMP_MAX = 0x01130080       # +normaliser (stock 500): input = clamp(accel) / normaliser

STOCK_NORMALISER = 500.0
STRENGTH_MIN, STRENGTH_MAX, STRENGTH_DEFAULT = 1, 20, 5


def normaliser(strength: int) -> float:
    s = max(STRENGTH_MIN, min(STRENGTH_MAX, int(strength)))
    return round(STOCK_NORMALISER / s, 4)


def patch_values(s) -> dict[str, float]:
    n = normaliser(getattr(s, "hm_strength", STRENGTH_DEFAULT))
    return {"Threshold": 0.0, "Clamp Min": -n, "Clamp Max": n}


def patch_yaml(title_id: str) -> str:
    """Patch entry for the launcher's <TITLE>_patch.yml; empty for titles not checked."""
    if title_id not in VERIFIED_TITLES:
        return ""
    n = normaliser(STRENGTH_DEFAULT)
    return "\n".join([
        f'  "{PATCH_NAME}":',
        "    Games:",
        '      "Gran Turismo 6":',
        f"        {title_id}: [ 01.22 ]",
        '    Author: "GT6 Launcher"',
        '    Notes: "Drives GT6\'s own cockpit neck rig (head slide, pitch, yaw, roll) from normal driving '
        'G-forces instead of only crashes. Experimental."',
        "    Patch Version: 1.1",
        "    Configurable Values:",
        '      "Threshold":',
        "        Type: double_range", "        Value: 0.0", "        Min: 0.0", "        Max: 200.0",
        '      "Clamp Min":',
        "        Type: double_range", f"        Value: {-n}", "        Min: -500.0", "        Max: -10.0",
        '      "Clamp Max":',
        "        Type: double_range", f"        Value: {n}", "        Min: 10.0", "        Max: 500.0",
        "    Patch:",
        f"      - [ be32, {JERK:#010x}, {NOP:#010x} ]  # was {JERK_ORIGINAL:#010x} vsubfp: feed acceleration, not jerk",
        f"      - [ be32, {GATE:#010x}, {GATE_SKIP:#010x} ]  # was {GATE_ORIGINAL:#010x} lbz r0,0x1e4(r31): skip collision gate",
        f'      - [ bef32, {THRESHOLD:#010x}, "Threshold" ]',
        f'      - [ bef32, {CLAMP_MIN:#010x}, "Clamp Min" ]',
        f'      - [ bef32, {CLAMP_MAX:#010x}, "Clamp Max" ]',
    ]) + "\n"
