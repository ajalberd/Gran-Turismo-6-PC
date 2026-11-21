# Agent handoff: GT6 PC mod work (color grading, home menu, head motion, RE)

Read this first. It gets a new agent (human or AI) productive in this repo in ~15 minutes.
Last updated 2026-11-21.

## 1. What this is

A fork of [Mabec-games/Gran-Turismo-6-PC](https://github.com/Mabec-games/Gran-Turismo-6-PC): a PySide6
launcher (`gt6launcher/`) that wraps a **GT6-patched RPCS3** (upstream commit `eee3f0f7c` + our diffs in
`emulator/gt6-patches/`) and generates RPCS3 game patches for Gran Turismo 6 **EU BCES01893, update 1.22**.

On top of upstream we added (all working in game unless noted):

| Feature | Where |
|---|---|
| Color grading in the video-out pass (brightness/contrast/gamma/…/dither), live sliders | emulator patch 09, `Emu/RSX/color_grading.h`, launcher `profile.COLOR_GRADING` |
| Home menu: mouse, F10 / Shift+F10, compact TV-style slider view | patches 10, 13 |
| GT6's own per-track color correction (game patch + live sliders) **untested in game** | `gt6launcher/engine_color.py`, patch 10, `docs/re/gt6-color-pipeline.md` |
| Cockpit head motion from G-forces, per movement (nod / lean / turn / slide), live | `gt6launcher/head_motion.py`, patch 16, `docs/re/gt6-head-motion.md` |
| Live memory bridge for RE (`data/rpcs3/gt6_live.txt`) | patch 15, `Emu/RSX/gt6_live_bridge.h` |
| Fixes: grading flicker (11), post-menu crash (12), invisible menu / "freeze" (14) | see `emulator/README.md` |

Upstream's `beta` branch (v1.2-beta5: auto-config, wheels, handhelds, translations) is merged in.

## 2. Where things are (this machine)

| Path | What |
|---|---|
| `F:\Games\PS3\GT6\GT6-Launcher\git_repo` | **The dev repo.** Work here. |
| `F:\...\git_repo\emulator\rpcs3-src` | RPCS3 source checkout (gitignored), branch `gt6-color`, one commit per patch 01..16 |
| `F:\...\git_repo\re-local\` | Gitignored RE files: `bin/EMAIN.elf` (decrypted 1.22), dumps |
| `J:\Games\GT6\GT6-Launcher` | **The install the user plays.** `GT6-Launcher.exe`, `_internal\`, `rpcs3\`, `data\` |
| `J:\Games\GT6\GT6-Launcher\data` | User data: saves, game updates, shader/PPU cache, `launcher.json`. **Never delete or overwrite.** |
| `J:\...\backup-original`, `backup-pre-beta` | Previous builds (rollback = move the three items back) |
| `J:\Games\GT6\GT6-Launcher\git_repo` | **Stale copy** (stops at patch 14). Don't develop there. |
| `F:\Games\PS3\GT6` | Old install, kept until the user deletes it. Not in use. |

Git remotes in the dev repo: `fork` = `ajalberd/Gran-Turismo-6-PC` (push here, branch
`color-grading-home-menu`), `origin` = Mabec-games upstream (read only; pushes get 403). `gh` is logged in.

## 3. Build: CI only

There is no local MSVC toolchain. Everything builds on GitHub Actions in the fork:

1. **Emulator** `rpcs3-gt6-windows.yml` (~40-60 min): applies `emulator/gt6-patches/*.diff` in order to upstream RPCS3.
2. **Package** `windows.yml` (~3 min): PyInstaller launcher + the **latest successful emulator run in the repo
   (any branch!)** + SDL3. Artifact `GT6-Launcher-win64`. The zip's `rpcs3\GT6-PATCHED.txt` names the emulator run.

```bash
gh workflow run rpcs3-gt6-windows.yml --ref color-grading-home-menu -R ajalberd/Gran-Turismo-6-PC
gh run list -R ajalberd/Gran-Turismo-6-PC -w rpcs3-gt6-windows.yml -L 1
gh workflow run windows.yml --ref color-grading-home-menu -R ajalberd/Gran-Turismo-6-PC
gh run download <run> -R ajalberd/Gran-Turismo-6-PC -n GT6-Launcher-win64 -D dist/pkgN
```

`gh run watch` sometimes exits early with code 1 while the run is still going; re-check with `gh run view`.
Only launcher changes? Skip step 1. Emulator changes need both, in order.

**Install** (user must close the launcher and GT6 first; check `tasklist`): replace `GT6-Launcher.exe`,
`_internal\`, `rpcs3\` in `J:\Games\GT6\GT6-Launcher` from `dist/pkgN/x/GT6-Launcher`, verify hashes, leave `data\`.
For risky changes, move the current three into a new `backup-*` folder first.

## 4. Changing the emulator

```bash
cd emulator/rpcs3-src            # local autocrlf=false, LF files
# edit, then one commit per patch:
git add -A rpcs3 && git commit -m "17 short description"
git format-patch -1 HEAD --stdout --no-signature | sed -n '/^diff --git/,$p' > ../gt6-patches/17-name.diff
```

* Patches must be **LF** (check: `tr -cd '\r' < file | wc -c` = 0). Global git has `autocrlf=true`; upstream's
  `overlay_tabs.h` is CRLF, so avoid touching it.
* Add a row to `emulator/README.md`, commit in the main repo, push to `fork`.
* `<windows.h>` defines `mouse_event()`: don't name types that (we use `overlay_mouse_event`).
* Data the game reads every frame can be written live from the presenter (see `gt6_engine_color.h`,
  `gt6_head_motion.h`); **code** changes must be game patches (applied at boot, then recompiled by PPU LLVM).

## 5. Changing the launcher

* The launcher **owns** the per-game config `data/rpcs3/config/custom_configs/config_BCES01893.yml`,
  `patch_config.yml` GT6 entries and `patches/BCES01893_patch.yml`: all rewritten on every start.
  Hand edits there are lost.
* Our game patches are generated Python (`engine_color.py`, `head_motion.py`, `lan.py`), appended in
  `lan.patch_file_text`. Enable via `profile.desired_patches`. Sanity check without the game:
  `patches.extract_from_text(lan.patch_file_text('BCES01893'), 'x')`.
* In-game home menu saves are synced back: `core.sync_ingame_color_grading` +
  `profile.ingame_settings_from_config` (Color Grading + Head Motion nodes).
* Line endings in the work tree vary (git `autocrlf=true`): most files are CRLF, some (e.g. `lan.py`) LF.
  Check before scripted edits and don't mix within a file; the Edit tool keeps a file's style.
* Upstream beta's `selfupdate.py` only shows a notice about newer Mabec releases. Installing those would
  replace our build: tell the user.

## 6. Testing with the user

The user drives; you watch logs and memory.

* Log: `J:\Games\GT6\GT6-Launcher\data\rpcs3\log\RPCS3.log` is open while the game runs. Copy it with a
  shared-read `FileStream` (PowerShell), then `tr -d '\0'`. Grep `home menu|·F |·E |device lost|frozen`.
* Live memory: write commands to `data\rpcs3\gt6_live.txt` (format in `Emu/RSX/gt6_live_bridge.h`),
  read `gt6_live_out.txt` ~0.2 s later. Use it to verify patches are applied (`r32 <addr>`) and to tune
  data live. It cannot change code.
* Give the user one change at a time and a concrete thing to try ("brake hard on a straight").

## 7. Reverse engineering

* Decrypt: `rpcs3 --decrypt EMAIN.SELF`, KLIC from `RPCS3.log` ("KLIC=0x…"), with
  `RPCS3_CONFIG_DIR=re-local/rpcs3cfg` (RPCS3 refuses temp dirs). Result goes in `re-local/bin/`.
* Tools: `tools/re/` (`elf.py` vaddr reader, `ppc.py` capstone disasm (**3rd arg is a byte count**),
  `xref.py` TOC/call finder, `shds.py`/`rsxfp.py` shader packages). `pip install capstone`. Run with `python -I`.
* Class names survive as RTTI strings (`N8GTCamera16ImpactBlurCameraE`); vtable = typeinfo ref + 4;
  vtable entries are OPD descriptors (code, toc). TOC = `0x1644F38`.
* Free memory for patch data: zero tail of the text segment page `0x1550868..0x1560000`.
  Used: `0x155F800..0x155F827` (engine color), `0x155F840..0x155F847` (head motion).
* Notes: `docs/re/gt6-color-pipeline.md`, `docs/re/gt6-head-motion.md`.

## 8. Open items

1. Engine color patch: test in game (GT6 Chroma -100 should turn a race grey).
2. Head motion: user is tuning per-axis gains; consider presets and separate fore/aft vs side slide
   (both use one load at `0x2F952C`, needs a small code cave).
3. Exposure / tone curve (`AutoExposureSetting`, `Exposure.dynamicRangeCompress`): next "rendering itself" target.
4. Presets / `.cube` LUT import, CAS sharpening slider in the grading pass.
5. Upstreamable fixes (patches 11, 12, 14) could go to RPCS3 as PRs, but only if the user asks.

## 9. Research question: AI cars in LAN / online races

**Status (2026-11-21): static RE done, see `docs/re/gt6-lan-ai.md` (verdict: host-simulated AI entries
through GT6's own network entry path is the way; a small game-patch probe is designed but not built).
The notes below are the earlier string-level recon.**

What the binary shows (EMAIN 1.22):

* Races are described by one generic `RaceParameter` (`entry_max`, `racers_max`, `enemy_list_type`,
  `entry_set`, `ai_skill*`, `ai_reaction`, `special_ai_type`, `damage.ai_cars_get_damaged`) and a list of
  `GTGame::EntryBase` (each entry: player, AI, ghost …). Offline races, online rooms and LAN all use these.
* Online/LAN rooms: `GTGame::mRoomConfig` (`MRoomConfig.cpp`, `packAsRoomConfig` / `unpackAsRoomConfig`,
  `updateRoomConfig`), exposed to the Adhoc scripts. Car sync is **peer-to-peer** (`STime::PeerManager`,
  `STime::MessengerP2P`): each machine simulates its own car and receives the others'.
* `isLanMode` / `setIsLanMode` (the hidden lanmode the launcher already enables), `ONLINE_SINGLE_RACE`.
* `GTEngine::MultiMonitorServer` / `MultiMonitorClient` (game mode `MULTIMONITOR_CLIENT`): GT6's 3-screen
  setup over LAN, where one PS3 runs the **whole** race and the others only render it. So code that
  streams every car's state, including AI cars, from one authoritative machine **does exist**.
* The stock online lobby UI offers no AI option (as far as is known for GT5/GT6).

**My assessment (author of this doc):** possible in principle, but this is a research project, not a
tweak. The hard part is not spawning AI (the race code is generic); it's **who simulates them and how the
other machines see them**. Options, cheapest first:

1. **Room config hack**: add AI entries to the room's `RaceParameter` / entry list (via Adhoc script edits,
   or memory pokes with the live bridge before the race starts). Most likely outcome: every machine spawns
   and simulates its *own* AI locally. They aren't synced, so each player sees different AI cars, and
   collisions with them only happen locally. It's cheap to try in LAN with two RPCS3 instances and tells
   us how the P2P layer copes with extra entries (it may desync or refuse). Worth doing first as a probe.
2. **Host-simulated AI, sent as peers**: the room host runs the AI and broadcasts their states in the
   same packets a remote player's car uses, so clients see them as extra (bot) players. Needs RE of the
   `MessengerP2P` car-state messages and of how entries map to peers. Hard, but it would give real
   shared AI races.
3. **Reuse multi-monitor**: it already sends all cars from one simulator, but clients only render, they
   don't drive. Adding a second human driver to it is probably harder than option 2.

Suggested first steps for whoever picks this up:

* Extract the Adhoc scripts from the game's `PDIPFS` (Nenkai's **GTToolsSharp**) and decompile the online
  room / lounge / race-setup projects with **OpenAdhoc**. Room creation and the `RaceParameter` fill-in are
  in script, which is the easiest place to add AI entries (recompile with OpenAdhoc, ship as a mod file).
* Set up a 2-instance LAN test on one PC (two RPCS3 config dirs, the launcher's LAN settings) so changes
  can be tested without a second machine.
* Use the live bridge to read the active `RaceParameter` in a LAN room (find it via `getRoomConfig` /
  `MRoomConfig` xrefs) before and after the race starts.
* Keep online (RPCN community server) out of it until LAN works: other people's games are involved there.

## 10. Working with this user

* They test in game and report back. Keep messages short and concrete, one change per test.
* Ask before deleting anything, pushing anywhere other than `fork`, or posting publicly.
* Commits end with the `Co-Authored-By` line given by the harness; never push to `origin`.
