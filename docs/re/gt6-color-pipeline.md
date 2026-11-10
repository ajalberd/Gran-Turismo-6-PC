# GT6 color pipeline: recon notes

Status: static recon only (2026-11-09). Target: **EU BCES01893 1.22 `EMAIN.SELF`**, the build AlexHaust's
patches use (`PPU-638ef307e2b3…`). All addresses are PS3 virtual addresses in that build.

Goal: change how GT6 itself renders color (exposure, tone curve, color correction), as opposed to the
emulator-side grade in emulator patch 09.

## Getting the code

```sh
rpcs3 --decrypt EMAIN.SELF    # RPCS3 asks for the KLIC; it is in RPCS3.log as "KLIC=0x..." after any game start
python -I tools/re/dump_postfx.py EMAIN.elf ColorCorrect Composite_3_zw_rect_response
```

RPCS3 refuses to run with its config dir in a temp folder; use `RPCS3_CONFIG_DIR=<persistent dir>`.
Decrypted binaries and dumps live in `re-local/` (gitignored), never in the repo.

Sanity check: 6/6 "was" values from AlexHaust's 1.22 patches match the decrypted ELF.

## 1. The engine already has a data-driven color stage

GT6's C++ reflection (`PDISTD::PseudoReflection`) leaves type and member names in the binary:

| Type | Members |
|---|---|
| `GTRender::ColorCorrectSetting` | `enable`, `bias[]`, `gain[]`, `gamma[]` (per channel), `chroma`, `mask`, `env`, `postDynamicrangeCorrect`, `postFix` |
| `GTRender::AutoExposureSetting` | `enable`, `averageIntensity`, `minIntensity`, `maxIntensity`, `centerWeight`, `verticalWeightGrad`, `sensitivityDark`, `sensitivityLight`, `resetGain`, `resetGainBaseLuminance`, `colorBalanceDiffLimit` |
| `GTRender::EnvironmentSetting::Exposure` | `dynamicRangeCompress` (+ `…EnvMap`, `…ReflectMap`, `…SubReflectMap`), `maxIntensity` — the tone-compression curve |
| `GTRender::GlareSetting` | `enable`, `threshold`, `level`, `quarterLevel`, `sigma`, `sigmaStep`, `weight[]`, `weightMaster`, `feedback`, `linear`, `lensFlareIntensity`, `nLensFlare` |
| `GTRender::VignettingSetting` | `enable`, `fnumberFactor`, `lensRadius`, `lensToApertureOffset`, `minImageCircleRate`, `fourthRawFactor` |
| `effect.cxx` `EffectParameter` | `colorcorrect`, `autoexposure`, `glare`, `vignetting`, `defocus`, `motionblur`, `blurfilter`, `fisheye`, `heat_effect`, `disablePostAAIS`, `flags`, … |
| `GTCourse::EnvironmentParameter` | per course: `autoexposure`, `glare`, `vignetting`, `sky` (`exposure`, `nightExposure`, `glareColor`, …), `sceneMotionblur`, `courseEmissionScale`, `localLightScale`, … |
| `GTCourse::VariableEnvironmentParameterSet` | time-of-day keyed: `exposure`, `autoexposure`, `glare`, `luminance`, `fog`, `worldLight`, `time`, … |

So exposure, tone compression and a per-channel bias/gain/gamma grade are **parameters**, set per course
and per time of day, not hard-coded constants. Changing them (globally or per course) is the cleanest
"change the color rendering itself" route.

The Adhoc script layer has `MEffect` / `MEffectCamera` / `MEffectEdgeBlur` (`include/adhoc/menu/MEffect.h`),
so scripts can probably drive these effects (photo mode is a likely user). OpenAdhoc (Nenkai) can
recompile GT6 scripts.

## 2. Post-effect shaders: `SHDS` packages

Ten `SHDS` packages in the data segment. Layout (relative to package start, 32-bit wrap):

```
+0x04  u32 size            +0x14 u32 n_techniques       +0x18 u16 n_vp, u16 n_fp
+0x1c  u32 technique table +0x20 u32 vertex program table (40 bytes each)
+0x60  fragment table, 0x20 each: (0, param_off, ucode_off, ucode_size, ...)
tech   12 bytes each: (name_off, 0, u16 vp_index, u16 program_index)
```

`program_index` counts fragment programs **in parameter-block (`param_off`) order**, not table order.
Verified three ways: `ColorCorrect` → the only post shader with per-channel pow and 3 uniforms;
AlexHaust's glare-fix entry (table 26) → `Convolution_4` (his "4-tap blur"); his exposure-fix entry
(table 16) → `Average_8x1_x2` (his "horizontal sums"). Uniform names (`gain`, `bias`, `gamma_chroma`,
`colorMap`, …) are strings inside the package; the game binds them by name at runtime.

Post-effect package `0x16A4580` (55 techniques), color-relevant entries:

| Technique | table idx | ucode | What it does |
|---|---|---|---|
| `ColorCorrect` | 42 | `0x16ADC00` | `c=pow(tex,gamma); c=c*gain+bias; c=mix(luma(c),c,chroma)`, luma = (0.30, 0.59, 0.11) |
| `ColorCorrectBlend` | 52 | `0x16AEA00` | same with alpha / blend |
| `Average_8x1_x2` | 16 | `0x16AAE00` | auto-exposure measurement (AlexHaust expfix) |
| `Convolution_4` | 26 | `0x16ABD80` | glare blur (AlexHaust glarefix) |

Inline constants are 0 in the ELF; values are patched into the microcode at runtime.

## 3. PPU path: from setting to shader

```
GTCourse::EnvironmentParameter / effect.cxx EffectParameter.colorcorrect[3]   (ColorCorrectSetting x3, stride 0x64,
        |                                                                       at postfx_object + 0x150)
0x0056F210  post-effect chain builder (same function as AlexHaust's DOF flag at 0x56F714)
        |   for slot in 0..2: if enable(+0) -> stage chosen by postFix(+0x2E) / default / postDynamicrangeCorrect(+0x2D)
        |   calls at 0x56F578, 0x56FB00, 0x56FF18
0x00ECD730  factory: new ColorCorrectRenderer(&gain, &bias, &gamma, *chroma, *mask)  (0x60 bytes, frame allocator)
0x008C2788  PDIScene::ColorCorrectRenderer ctor: copies to this+0x04 gain, +0x10 bias, +0x1C gamma,
        |   +0x28 chroma, optional mask -> +0x2C..+0x58 (+0x5C = has mask). vtable 0x15CB1A8
0x008C2670  render (vtable slot 0) -> 0x903410 pass: technique "ColorCorrect"/"ColorCorrectBlend",
            setParameter("gain", this+4), ("bias", this+0x10), ("gamma_chroma", {gamma.rgb, chroma})
```

`GTRender::ColorCorrectSetting` (from its reflection registration at `0xECFE3C`…):
`+0x00 enable`, `+0x04 gain[3]`, `+0x10 bias[3]`, `+0x1C gamma[3]`, `+0x28 chroma`, `+0x2C env`,
`+0x2D postDynamicrangeCorrect`, `+0x2E postFix`, `+0x30 mask`.

### Patch: "Engine Color Correct (experimental)"

`gt6launcher/engine_color.py` generates it into the launcher's `BCES01893_patch.yml` (EU 1.22 only:
hook verified there). A 42-instruction `calloc` cave replaces the constructor's last copy
(`0x8C2834 stfs f1,0x28(r3)`) and applies user modifiers to the copied values:
gain ×, bias +, gamma ×, chroma × (10 configurable values, read from `0x155F800`, a zero gap after
the text segment that no other patch uses). Per-course looks are kept, only shifted. Uses r11/f0/f13
only (free at the hook; cr7 preserved for the following `beq`). **Untested in game.** It does nothing
where the game leaves color correction disabled.

Live control: emulator patch 10 (`Emu/RSX/gt6_engine_color.h`) checks for the hook (branch at
`0x8C2834`, `beq` at `0x8C2838`, title BCES01893) and rewrites the 10 floats at `0x155F800` every
presented frame from `Video/Color Grading/Engine *`. The launcher writes the same values (slider
-100..100) both there and, converted, as the patch's configurable values, so stock emulators get them
at boot. Conversions: gain/chroma `1 + v/100`, bias `v/500`, gamma `2^(-v/100)`.

## 4. Tools

`tools/re/`: `elf.py` (vaddr reader), `shds.py` (package parser), `rsxfp.py` (RSX fragment program
disassembler, bitfields from RPCS3 `RSXFragmentProgram.h`, validated against AlexHaust's annotations),
`dump_postfx.py` (index + disassemble), `xref.py` (TOC/lis address resolution, call finder),
`ppc.py` (capstone PPC wrapper). Disassembly needs `pip install capstone`.

## Next steps

1. **Test the patch in game.** Enable *Engine Color Correct (experimental)* in the launcher's Patches
   tab, set e.g. Chroma 0 (grayscale) and race. If nothing changes, the game has no ColorCorrect slot
   enabled in that scene: next step is a "force enable" variant (slot 0, stage default, neutral values).
2. **Exposure / tone curve.** Same method for `Exposure.dynamicRangeCompress` and
   `AutoExposureSetting` (reflection strings at `0x1173298` / `0x115BFC0`, registration code near
   `0xEE14F0` / `0xE6135C`), and the `Composite_*_response` shaders.
3. **Course data.** Where `EnvironmentParameter` is loaded from (course files in PDIPFS; Nenkai's
   GTToolsSharp unpacks them) for per-track grading without code patches.
4. **Dynamic capture** (RPCS3 `Log shader programs` / RenderDoc) to read live gain/bias/gamma values.
