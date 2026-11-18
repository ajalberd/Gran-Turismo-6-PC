<p align="center">
  <img src="docs/img/cover.jpg" alt="Gran Turismo 6 PC" width="420">
</p>

<h1 align="center">Gran Turismo 6 PC</h1>

<p align="center">
  <b>Version 1.2 (Beta)</b> · Linux &amp; Windows<br>
  Gran Turismo 6, one of the hardest PlayStation 3 games to emulate, set up for PC in one download:
  a GT6-tuned emulator, the official updates, modern graphics options, gamepads and racing wheels,
  mods, LAN racing and more, behind a single <b>PLAY</b> button.
</p>

<p align="center">
  <img src="docs/img/ingame.jpg" alt="Gran Turismo 6 on PC" width="860">
</p>

> **You need your own copy of Gran Turismo 6.** No game files, firmware or keys are included or
> downloaded from unofficial sources. You add a disc image (`.iso`) you made from your own disc.
>
> ⚠️ **Beta notice:** v1.2 is a Beta release. **Not all hardware configurations, handhelds, and racing wheels have been tested and verified on physical hardware.** Feedback and bug reports are very welcome — use **Log → Save current logs** to export a `.zip` bundle with your system specs, logs, and crash reports.

---

## Why this exists: GT6 is a notoriously difficult PS3 game to run

Gran Turismo 6 (2013) came out at the end of the PS3 generation and pushes the console's Cell
processor harder than almost any other game. For years it was a showcase of what was *not* working
in PS3 emulation:

* **Rendering is split between the Cell's SPUs and the RSX GPU.** GT6 builds parts of each frame on
  the SPU co-processors (post-processing such as its MLAA anti-aliasing, lighting passes) while the GPU
  reads and writes the same memory. An emulator has to keep the GPU's copy and main memory in sync
  exactly, or the image breaks.
* **Updates after 1.05 changed the renderer.** From 1.06 on, the 3D world renders **completely black**
  unless the emulator writes and reads back GPU color buffers, which is expensive and breaks
  resolution scaling. Yet 1.22 is needed for mods, LAN and most fixes.
* **Race-time freezes.** Since RPCS3 v0.0.42-20037, an RSX command-queue change makes GT6 freeze
  for about a second at a time during races ("RSX queue appears to be stuck").
* **Fragile details.** Multithreaded RSX causes "vertex explosions" on cars. Occlusion queries slow car
  reward screens to near 0 FPS and soft-lock the garage. The bloom/glare buffers turn into green
  blotches at other resolutions. Horizontal bands of stale image show up while racing.
* **A heavy first start.** 1.22 runs a one-time ~20 minute data install inside the game, on top of
  compiling the game's code.

Gran Turismo 6 PC packages the community's fixes for all of this, adds its own, and hides the complexity.

## Emulation + recompilation: how it runs

GT6 PC is **not** a source port and **not** a hand-made decompilation. It combines three layers:

1. **Ahead-of-time recompilation.** RPCS3 translates the game's PowerPC (PPU) and SPU machine code into
   native x86-64 code with LLVM and caches it on disk. That is the ~8 minute compile on the first start.
   Afterwards the game's logic runs as native code on your CPU.
2. **Emulation** of the rest of the PS3: the RSX GPU (on Vulkan), memory, the operating system
   services (save data, audio, input, network), at the original 60 Hz timing.
3. **Game-specific binary patches** applied to the recompiled code at load time: graphics upgrades,
   bug fixes, the LAN mode fixes, the developer menu. They work at the instruction level, like a
   recompilation project's per-game fixes.

On top of that comes a **patched emulator build** (below) that changes RPCS3 itself where GT6 needs it.

## Unique PC features

| | |
|---|---|
| **One download, nothing to configure** | The GT6-patched emulator is built in. The launcher installs the PS3 firmware, finds your disc image and installs the official update chain (1.02 → 1.22, ~10.5 GB) in the right order, with resumable, checksum-verified downloads. |
| **GT6-patched emulator** | Fixes the ~1 s race freezes, stale-band rendering, the intro-skip crash and save-state issues, and stops memory-lock retry spam (see [emulator/](emulator/)). Built for **Linux and Windows** from the same upstream commit + patches. |
| **Auto-configure for my PC** | One-click hardware detection (CPU, GPU, motherboard/PCIe bus, RAM) picks optimal GT6 settings, with a **Restore previous settings** button to revert anytime. |
| **Version-aware tuning** | 1.06+ gets color buffers; 1.05 (or narrow PCIe 3.0 x8 GPUs via Speedboost) gets the faster CPU-blit path, never both. Strict Rendering Mode and ZCULL accuracy options are exposed cleanly. |
| **Modern graphics** | 100–300 % internal resolution (sharp at 1440p/4K), ultrawide **21:9 / 32:9** and **16:10**, *Sharper MLAA* or no post-AA, **AMD FSR 1 + CAS**, 16× anisotropic filtering, sharper shadows, extended FOV, optional in-game motion blur, depth of field toggle, lamp-glare control, **color grading** (brightness, contrast, gamma, shadows/highlights, saturation, vibrance, white balance) with live sliders in the in-game home menu (Xbox/PS button or F10, mouse supported), plus experimental control of GT6's own per-track color correction and **cockpit head motion from G-forces** (GT6's own neck rig). |
| **Resolution-scale fixes always on** | Bloom, auto exposure and smoke render correctly at every resolution, including when it changes while you play. |
| **60 FPS everywhere** | Menus and screens that ran at 30 FPS on PS3 (gallery, new-car screen) run at 60. |
| **Handheld & gamepad support** | Built-in `gamecontrollerdb.txt` synced to RPCS3 + handheld prioritization (`Steam Deck`, `ROG Ally / Ally X`, `Legion Go / Go S`, `MSI Claw`, `Strix Halo`) alongside Xbox, PlayStation, 8BitDo, and Switch Pro controllers. |
| **Racing wheels** | Any wheel (Logitech RS50/G PRO/G923/G29/G920/G27, Thrustmaster T150/T300, Fanatec, Moza, multi-USB pedals/shifters) via an interactive wizard with live **Input level** meter, **Controls Review & Test**, **Invert pedals**, and **Reverse FFB**. The game sees a **Logitech G27** natively **with force feedback**. |
| **Mods** | One-click **GT6 Career Mod + Spec II**, with a full backup: uninstalling restores the game byte for byte (guarded until GT6 finishes unpacking first-boot data). |
| **LAN racing** | GT6's hidden `lanmode`, with the fixes needed to race over LAN without PSN, for the **EU and US** discs. The EU port was verified by comparing the decrypted game code. |
| **Online** | The community GT6 server (EU disc) through RPCN, with login handled in the launcher. |
| **Cheats** | GT6's own developer menu: set your credits with the *Cashier*, add cars. Single player only. |
| **Right defaults per region** | The emulated console's region and language follow your disc. |
| **New-version notice** | On start the launcher checks GitHub and shows a banner with a **Download** link whenever a newer release is out, beta or stable (from v1.2-beta3 on). Silent when offline. |
| **Languages & diagnostics** | Dynamic language switcher: <img src="docs/img/flags/gb.png" width="20" height="15" alt="GB"> English / <img src="docs/img/flags/cn.png" width="20" height="15" alt="CN"> 简体中文 (Simplified Chinese) / <img src="docs/img/flags/fr.png" width="20" height="15" alt="FR"> Français (French) / <img src="docs/img/flags/jp.png" width="20" height="15" alt="JP"> 日本語 (Japanese), low-VRAM GPU warnings, automatic crash-report capture, and one-click `.zip` log export (**Log → Save current logs**). |

<p align="center">
  <img src="docs/img/launcher.jpg" alt="Launcher" width="860">
</p>

## What's new in v1.2 (Beta)

* **⚡ Auto-configure for my PC & Restore:** Detects your CPU (selecting `RPCS3 Alternative Scheduler` on Intel hybrid CPUs), GPU tier, motherboard/PCIe link, and system RAM (`Mega` SPU block size when 7+ GiB RAM is detected, `Safe` otherwise) to configure optimal settings in one click, with a **Restore previous settings** button next to it.
* **PCIe 3.0 x8 GPU Bottleneck Fix (Issue #36):** Automatically detects narrow-link PCIe x8/x4 GPUs (such as RTX 5060 / 4060 / 3050 / RX 7600 / 6600) on PCIe 3.0 motherboards (B450, B350, A320, etc.) and applies `Force CPU Blit` + `Speedboost (disable Write Color Buffers)` + `Disable MLAA` + `100% scale + FSR` + `Lamp glare 0` so races can run at a full 60 FPS without green edge artifacts.
* **Expanded Handheld Controller Support:** Bundles community SDL `gamecontrollerdb.txt` mappings into RPCS3's `input_configs/` folder, adds runtime mapping synthesis as a fallback, prioritizes integrated handheld controls in Automatic mode, and labels handheld controllers (`Valve Steam Deck`, `ASUS ROG Ally / Ally X`, `Lenovo Legion Go / Go S / Z1E`, `MSI Claw / Claw A8`, `AMD Strix Halo`, `GPD`, `AYANEO`, `OneXPlayer`).
* **Green Glare / Light Flare Fix with No post AA (Issues #39, #35):** Ensures RPCS3's synced `imported_patch.yml` (AlexHaust) takes precedence over colliding `patch.yml` entries so `Disable MLAA` (*No post AA*) + `>100%` resolution scale works cleanly with `Bloom/Glare Resolution Scale Fix` without green/colored glare artifacts. High-end Auto-configure also uses `Sharper MLAA` at `200%` scale (preserving `Strict Rendering Mode` on AMD). Note: *No post AA* skips GT6's whole SPU post-process pass, not just MLAA, so clouds and sky gradients can show colour banding; use `Sharper MLAA` for the original look.
* **Racing Wheel Setup Overhaul:**
  * Supports **Logitech RS50 / G PRO / G923** and multi-device USB setups (separate pedals/shifters) with device selection and auto-switching inside the wizard, and prevents wheels from being auto-bound as DualShock 3 `Player 1 Input`.
  * Fixes step advancement by waiting for the calibrated axis or button to return to rest before moving to the next step.
  * Adds a live **Input level** bar and percentage readout (`0%–100%`) on axis steps so you can see wheel rotation and pedal travel as you calibrate.
  * Fixes pedal axis polarity for **Thrustmaster** wheels (such as T150/T300 where released pedals rest at `+32767`), and fixes unmapped pedals (e.g. skipping **Clutch** on 2-pedal sets) so RPCS3 reports them as released instead of permanently pressed (Issue #38).
  * Adds a **Controls Review & Test** screen at the end of the wizard with live steering/pedal bars, button test, per-axis **Invert** checkboxes, plus one-click **Invert pedals** and **Reverse FFB** (`reverse_effects`) controls in the main Controls section (Issue #38).
* **Graphics & Emulation Improvements:** Adds **Strict Rendering Mode** (fixes AMD hood reflection/strobe), **ZCULL Accuracy** selector (`Approximate`, `Relaxed`, `Precise`), disables ZCull occlusion queries by default (see below), warns when selecting an integrated or low-VRAM GPU, and prevents mod installation until GT6 finishes unpacking first-boot `PDIPFS` data.
* **5.1 Surround Audio:** Advanced → **Audio output** offers **Stereo (2.0)** or **Surround 5.1** (RPCS3 `Audio Format`). Added in v1.2 Beta but missing from earlier notes.
* **Language Switcher & Better Diagnostics:** Adds dynamic language switching (<img src="docs/img/flags/gb.png" width="20" height="15" alt="GB"> English / <img src="docs/img/flags/cn.png" width="20" height="15" alt="CN"> 简体中文 (Simplified Chinese) / <img src="docs/img/flags/fr.png" width="20" height="15" alt="FR"> Français (French) / <img src="docs/img/flags/jp.png" width="20" height="15" alt="JP"> 日本語 (Japanese)), automatic abnormal-exit crash reports, direct-RPCS3-launch detection, and an updated **Log → Save current logs** exporter that saves a `.zip` archive (`system-info.txt`, `launcher.log`, `RPCS3.log` preserving both header and tail, and recent crash reports) with an **Open folder** button.

### Changes since v1.2-beta2

* **New-version notice:** the launcher checks GitHub when it starts and shows a banner under the version number when any newer release is published (beta or stable, e.g. v1.2-beta4, v1.2, v1.4), with a **Download** link. It stays silent when offline. Works from this version on; older builds don't have it.
* **Fixed 1–5 FPS on the car delivery and part install screens (Issues #40, #42):** *Disable ZCull occlusion queries* is on again by default and in **Auto-configure**. v1.2 Beta had turned the queries on, which made the emulator stall about once a second on these screens on both AMD and NVIDIA. Existing settings are switched over once on the first start; untick it under Advanced only if cars flicker on London / Madrid / the kart tracks.
* **Steam Deck OLED:** now detected as a handheld, so **Auto-configure** picks the 720p handheld profile instead of 1080p / 150%.
* **<img src="docs/img/flags/fr.png" width="20" height="15" alt="FR"> French and <img src="docs/img/flags/jp.png" width="20" height="15" alt="JP"> Japanese:** the language button now cycles <img src="docs/img/flags/gb.png" width="20" height="15" alt="GB"> English → <img src="docs/img/flags/cn.png" width="20" height="15" alt="CN"> 简体中文 → <img src="docs/img/flags/fr.png" width="20" height="15" alt="FR"> Français → <img src="docs/img/flags/jp.png" width="20" height="15" alt="JP"> 日本語.
* **Racing wheel wizard:** no longer captures pedals as steering on wheels that report their axes late (Issue #41).
* **Clearer graphics notes:** *Force CPU Blit* now warns that garage car pictures and Paint / Pit Service previews turn black (Issue #44), and *No post AA* explains that it skips GT6's whole post-process pass (Issue #39).

## Download

Get **v1.2 (Beta)** from [Releases](../../releases):

* **Linux (Ubuntu, Debian, Linux Mint, Pop!_OS, SteamOS & SDL2 distros):** `GT6-Launcher-Ubuntu-SDL2-x86_64.AppImage`. Built on Ubuntu 22.04 LTS (`GLIBC 2.35+`) with both SDL3 and SDL2 (`libSDL2-2.0.so.0`) gamepad/wheel support.
* **Linux (Arch, CachyOS & rolling-release distros):** `GT6-Launcher-x86_64.AppImage`. Make it executable and start it.
* **Windows 10/11:** `GT6-Launcher-win64.zip`. Unzip anywhere and start `GT6-Launcher.exe`. The portable
  build stores launcher and RPCS3 data, including settings, updates, saves, and logs, in the adjacent `data\` folder;
  it does not use `%APPDATA%` or `%LOCALAPPDATA%` for application data. If you select an RPCS3 install with its own
  `portable\` folder beside `rpcs3.exe`, the launcher uses that folder for RPCS3 data, matching RPCS3's own path choice.

**PC requirements:** 8+ CPU threads (GT6 is very CPU-heavy), 16 GB RAM, a Vulkan GPU, ~35 GB of disk space.

## Getting started

1. **Setup** tab: *Install firmware* → *Add ISO* (or let it find your image) → controllers → *Download & install updates* (1.22).
2. Press **PLAY**.

> ⏱️ **The very first start of 1.22 takes about 30 minutes, once**: ~8 min compiling, then the game's
> own *"Installing... approx. 20 mins left"* screen (steady 60 FPS, it's working). Later starts take
> seconds. A brief stutter the first time a new car, track or camera view appears is shaders being
> built, and it goes away.

**Worth setting once in the game** (stored in your save):

| | |
|---|---|
| Options → Display → **Display Size (HD) = 100** | removes the 90 % black border |
| Options → Global → **Units** | km/h or mph |
| Options → Wireless Controller: **R2 Accelerate, L2 Brake** | trigger driving (RT/LT) |
| Options → Steering Controller / Sound | wheel options, music vs. engine balance |

## Supported versions

| Disc | Serial | Updates | Graphics patches | LAN | Online |
|---|---|---|---|---|---|
| Europe | BCES01893 | ✔ | 1.22, 1.05 | ✔ | ✔ |
| North America | BCUS98296 | ✔ | 1.22, 1.05 | ✔ | – |
| UK | BCES01977 | ✔ | 1.22, 1.05 | – | – |
| Japan / Asia / Latin America / PSN | | ✔ | partly | – | – |

## Status of v1.2 (Beta)

> **Important:** Because v1.2 adds hardware auto-configuration, expanded handheld controller mappings, PCIe bottleneck workarounds, and updated racing wheel calibration, **not all PC hardware combinations, handhelds, and racing wheels have been tested and verified on physical hardware yet**.

Tested: EU 1.22 on Linux (Ryzen 9 6900HS, RTX 3080 Laptop) and Windows 10/11: full update install,
first boot, races with 6 cars at 60 FPS, mod install/uninstall, gamepad, LAN code verification.
The Windows package is portable (`data\` beside `GT6-Launcher.exe`) and bundles the GT6-patched RPCS3
compiled with RPCS3's own Windows (MSVC) build steps.
Partially tested / community-verified or awaiting broader hardware verification: racing wheels
(Logitech G923, Thrustmaster T150/T300, multi-USB pedals/shifters), PCIe 3.0 x8 desktop setups,
handheld PCs (Steam Deck, ROG Ally, Legion Go, MSI Claw, Strix Halo), two-PC LAN, and online play.
Reports are welcome — export your logs with **Log → Save current logs** and attach the `.zip` archive
to a GitHub issue.

## Building

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m gt6launcher                  # run from source
packaging/build_appimage.sh path/to/rpcs3-gt6-x86_64.AppImage   # Linux AppImage (needs linuxdeploy)
```

Windows: `packaging\build_windows.ps1`, or the workflows: [GT6 RPCS3 for Windows](.github/workflows/rpcs3-gt6-windows.yml)
(patched emulator, RPCS3's MSVC CI) → [Windows build + smoke test](.github/workflows/windows.yml) (launcher package).
The GT6-patched emulator is built with `emulator/scripts/build_rpcs3.sh` (see [emulator/README.md](emulator/README.md)).

## Credits

* **[RPCS3](https://github.com/RPCS3/rpcs3)**: the emulator this is built on (GPL-2.0)
* **[AlexHaust](https://github.com/AlexHaust/granturismo-RPCS3-patches)**: GT6 graphics, camera and HUD patches (downloaded at first start)
* **[Nenkai](https://github.com/Nenkai)**: [OpenAdhoc](https://github.com/Nenkai/OpenAdhoc), the [GT Modding Hub](https://nenkai.github.io/gt-modding-hub/), Develop Settings (with **illusion**), Spec II (with **TheAdmiester**)
* **abowen**: [GT6 LAN without PSN](https://gist.github.com/abowen/85d145055fff07e787a52f0928f84ece), plus the RPCS3 fixes that patches 01–05 are based on
* **Lunard**: [GT6 Career Mod](https://www.gtplanet.net/forum/downloads/gran-turismo-6-career-mod.7049/), with **Emivebe** and **Plunke**
* **FlexBy** (irekej server patch), **Edo** (Looser Chase Camera), the [RPCS3 wiki](https://wiki.rpcs3.net/index.php?title=Gran_Turismo_6) and GTPlanet
* **Polyphony Digital**: for Gran Turismo 6

## License

The launcher is licensed under **GPL-3.0** ([LICENSE](LICENSE)). The bundled emulator is RPCS3
(GPL-2.0), built from upstream commit `eee3f0f7c` plus the patches in [emulator/gt6-patches](emulator/gt6-patches).
Third-party patches and mods belong to their authors and are downloaded from their official sources.

*Gran Turismo* is a trademark of Sony Interactive Entertainment. This is an unofficial fan project, not
affiliated with or endorsed by Sony Interactive Entertainment or Polyphony Digital.
