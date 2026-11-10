"""GT6's own color correction, adjusted at the source (EMAIN 1.22, EU and US share the layout).

Reverse engineered from the decrypted EMAIN.SELF (notes: docs/re/gt6-color-pipeline.md):

* ``GTRender::ColorCorrectSetting`` (enable, gain[3], bias[3], gamma[3], chroma, ...) lives in
  ``EffectParameter.colorcorrect[3]``; the post-effect builder (0x56F210) creates a
  ``PDIScene::ColorCorrectRenderer`` for each enabled slot.
* The renderer constructor (0x8C2788) copies the setting to ``this+0x04`` gain, ``+0x10`` bias,
  ``+0x1C`` gamma, ``+0x28`` chroma; the render method (0x903410) sends them to the
  ``ColorCorrect`` RSX shader as ``gain``, ``bias`` and ``gamma_chroma``:

      c = pow(tex(colorMap), gamma);  c = c * gain + bias;  c = mix(luma(c), c, chroma)

This patch hooks the end of the constructor and applies user modifiers to whatever the game set,
so per-course and time-of-day looks are kept, only shifted. It has no effect where the game does
not enable color correction (whether it does in races still has to be checked in game).
"""
from __future__ import annotations

PATCH_NAME = "Engine Color Correct (experimental)"
# Hook and data addresses checked against the decrypted EMAIN.SELF of these titles only.
VERIFIED_TITLES = {"BCES01893"}

HOOK = 0x008C2834          # stfs f1, 0x28(r3) - last store of the constructor's copy
HOOK_ORIGINAL = 0xD0230028
DATA = 0x0155F800          # zero gap after the text segment (mapped 64 KiB page, unused by other patches)

# (config name, offset in the renderer, data slot, op, default, min, max)
VALUES = [
    ("Gain R", 0x04, 0, "mul", 1.0, 0.0, 2.0),
    ("Gain G", 0x08, 1, "mul", 1.0, 0.0, 2.0),
    ("Gain B", 0x0C, 2, "mul", 1.0, 0.0, 2.0),
    ("Bias R", 0x10, 3, "add", 0.0, -0.2, 0.2),
    ("Bias G", 0x14, 4, "add", 0.0, -0.2, 0.2),
    ("Bias B", 0x18, 5, "add", 0.0, -0.2, 0.2),
    ("Gamma R", 0x1C, 6, "mul", 1.0, 0.5, 2.0),
    ("Gamma G", 0x20, 7, "mul", 1.0, 0.5, 2.0),
    ("Gamma B", 0x24, 8, "mul", 1.0, 0.5, 2.0),
    ("Chroma", 0x28, 9, "mul", 1.0, 0.0, 2.0),
]


# Launcher setting (-100..100) -> patch value. Must match rpcs3 Emu/RSX/gt6_engine_color.h (emulator patch 10),
# which rewrites the same floats every frame from Video/Color Grading/Engine * while the patch is active.
SETTING_FOR = {"Gain R": "cge_gain_r", "Gain G": "cge_gain_g", "Gain B": "cge_gain_b",
               "Bias R": "cge_bias_r", "Bias G": "cge_bias_g", "Bias B": "cge_bias_b",
               "Gamma R": "cge_gamma_r", "Gamma G": "cge_gamma_g", "Gamma B": "cge_gamma_b",
               "Chroma": "cge_chroma"}


def to_patch_value(name: str, v: int) -> float:
    v = max(-100, min(100, int(v)))
    if name.startswith("Bias"):
        return round(v / 500.0, 6)                 # -0.2 .. 0.2, added
    if name.startswith("Gamma"):
        return round(2.0 ** (-v / 100.0), 6)       # 2 .. 0.5, multiplies the exponent (+ = brighter midtones)
    return round(1.0 + v / 100.0, 6)               # gain / chroma: 0 .. 2, multiplied


def patch_values(s) -> dict[str, float]:
    return {name: to_patch_value(name, getattr(s, key)) for name, key in SETTING_FOR.items()}


def _lfs(frt: int, d: int, ra: int) -> int: return (48 << 26) | (frt << 21) | (ra << 16) | (d & 0xFFFF)
def _stfs(frs: int, d: int, ra: int) -> int: return (52 << 26) | (frs << 21) | (ra << 16) | (d & 0xFFFF)
def _lis(rt: int, imm: int) -> int: return (15 << 26) | (rt << 21) | (imm & 0xFFFF)
def _fmuls(frt: int, fra: int, frc: int) -> int: return (59 << 26) | (frt << 21) | (fra << 16) | (frc << 6) | (25 << 1)
def _fadds(frt: int, fra: int, frb: int) -> int: return (59 << 26) | (frt << 21) | (fra << 16) | (frb << 11) | (21 << 1)


def cave() -> list[tuple[int, str]]:
    """Code cave body: (word, comment). Uses r11, f0, f13 only (free at the hook; cr7 untouched)."""
    hi = (DATA + 0x8000) >> 16
    base = DATA - (hi << 16)
    out = [(HOOK_ORIGINAL, "stfs f1, 0x28(r3)        original: chroma"),
           (_lis(11, hi), f"lis r11, {hi:#x}           user values at {DATA:#x}")]
    for name, off, slot, op, *_ in VALUES:
        d = base + 4 * slot
        out.append((_lfs(0, off, 3), f"lfs f0, {off:#x}(r3)"))
        out.append((_lfs(13, d, 11), f"lfs f13, {d:#x}(r11)    {name}"))
        out.append((_fmuls(0, 0, 13) if op == "mul" else _fadds(0, 0, 13), ("fmuls" if op == "mul" else "fadds") + " f0, f0, f13"))
        out.append((_stfs(0, off, 3), f"stfs f0, {off:#x}(r3)"))
    return out


def patch_yaml(title_id: str) -> str:
    """Patch entry for the launcher's <TITLE>_patch.yml (body under the PPU hash key); empty for
    titles whose executable has not been checked."""
    if title_id not in VERIFIED_TITLES:
        return ""
    body = cave()
    lines = [f'  "{PATCH_NAME}":',
             "    Games:",
             '      "Gran Turismo 6":',
             f"        {title_id}: [ 01.22 ]",
             '    Author: "GT6 Launcher"',
             '    Notes: "Adjusts GT6\'s own color correction (gain, bias, gamma, chroma) where the game uses it. '
             'Multiplies/offsets the per-course values. Experimental."',
             "    Patch Version: 1.0",
             "    Configurable Values:"]
    for name, _off, _slot, _op, default, lo, hi in VALUES:
        lines += [f'      "{name}":', "        Type: double_range", f"        Value: {default}",
                  f"        Min: {lo}", f"        Max: {hi}"]
    lines.append("    Patch:")
    for name, _off, slot, *_ in VALUES:
        lines.append(f'      - [ bef32, {DATA + 4 * slot:#010x}, "{name}" ]')
    lines.append(f"      - [ calloc, {HOOK:#010x}, {len(body)} ]  # replaces stfs f1, 0x28(r3) in ColorCorrectRenderer::ctor")
    for word, comment in body:
        lines.append(f"      - [ be32, 0x0, {word:#010x} ]  # {comment}")
    return "\n".join(lines) + "\n"
