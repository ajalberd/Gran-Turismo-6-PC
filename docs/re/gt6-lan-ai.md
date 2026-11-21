# GT6 LAN / online races with AI cars: research notes

EMAIN.SELF 1.22, EU BCES01893 (decrypted `re-local/bin/EMAIN.elf`), static analysis only, 2026-11-21.
Nothing built or tested in game yet. TOC = `0x1644F38`. All addresses are PPU virtual addresses.

## Verdict

**Feasible in principle, and the engine's own design points to one approach: the room host adds AI
entries through the normal network entry path, and the other machines see them as ordinary
remote cars.** The other two options (per-machine local AI, multi-monitor reuse) are worse.

| Option | Verdict | Why |
|---|---|---|
| A. Host-simulated AI, sent as extra network entries | **Most promising. Cheap probe possible.** | Every entry in a network race is created by its owner peer as replicated `STime` objects (car setup + car-state packet + entry info). Each slot has a ControlType (LOCAL / NETWORK) that is independent of its DriverType (PLAYER / AI). So "host runs an AI car, everyone else receives it" is a state the data model already supports. No limit of one entry per peer was found on the sending side. Only the host would need the mod. |
| B. Every machine spawns and simulates its own local AI | Not recommended | In a network race `Race::entry` always goes through the network (`0x47ea4c`, branch at `0x47eaf0`). The offline path assigns slots locally, which would collide with the slot numbers the network hands out. Even if it worked, each player would see different AI cars. |
| C. Reuse multi-monitor (`GTEngine::MultiMonitorServer/Client`) | Not suitable | Multi-monitor clients only render the server's race (`ORG.startMonitorClient`, `monitor_*` options). There is no input path from a client back to the simulating machine, so a second human can't drive. |

Open questions that only a test can answer (static RE didn't get there):

1. Does the room accept **more than one entry from the same peer**? The sender side allows it (a
   16-deep command ring). Whether the host or other peers drop a second entry was not found.
2. Does the owner stream the **car-state packet for every LOCAL slot**, or only for its human car?
3. Does the **AI actually drive in a network race**? Course AI lines might not be loaded online. The
   network race may also force a DriverType.

The probe below answers 1 and 2 with one small game patch and two RPCS3 instances. It needs no emulator
rebuild.

## How a network race builds its entry list (what was found)

### Script layer → organizer

* The Adhoc VM exposes C++ natives. The registration call is `bl 0xCE3234` (method), `0xCE4C0C`
  (property) or `0xCEB11C` / `0xCE4C3C`, with r4 = name string and r5 = OPD. A full dump
  of about 4,900 natives is easy to regenerate (see "Tools" below).
* Race setup is script driven. The script fills a `GameParameter` (event → `RaceParameter`, `EntrySet`)
  and calls `ORG.*` natives (the race organizer, `GTFramework::mOrganizer`) to start the race and
  enter cars. Relevant `ORG` natives:

| Native | Impl | Notes |
|---|---|---|
| `entryRace` | `0xB5F94` | → `0x1E0FE4` → `0x1DE948` → … → `Race::entry` `0x47EA4C` |
| `entryRaceAsync` | `0xB5DD8` | |
| `entryRaceRequest` / `checkAcceptRaceRequest` | `0xBA470` / `0xC3080` | → race `0x46B058` / `0x46B01C` |
| `openEntryRacer` / `closeEntryRacer` / `canEntryRacer` | `0xA9EB0` / `0xAEDE0` / `0xB6F1C` | |
| `getEntryControlType(slot)` | `0xC4118` | reads `EntrySlot+0x4C` (layout below) |
| `getEntryDriverControlType(slot)` | `0xBB7F4` | |
| `getEntryMaxAtCurrentRace` | `0xB34D4` | |
| `rebuildNetworkRace` / `restartNetworkRace` | `0xA0474` / `0xB2D94` | |
| `is_host` / `getHostId` / `isOnline` | `0xB08E4` / `0xB9360` / `0xB080C` | `is_host` → race `0x4778D4` → net `0x48E168` |
| `startMonitorClient` / `setMonitorLayout` | `0xCB57C` / `0xCC6B0` | multi-monitor |

* Organizer object chain: Adhoc `mOrganizer` native object `+0x18` → organizer; organizer `+0` →
  impl; impl `+0xA74` → **Race** (GTRace).
  (`0x1DC2AC`: `lwz r9,0(r3); lwz r3,0xA74(r9)`.)
  No static global pointer to the organizer was found yet. The probe patch stores the Race pointer for
  the live bridge.

### Room config

* `GameParameter.packAsRoomConfig` (native `0x123B20`) copies the GameParameter (`0x3327CC` →
  `0xDE279C`) and serialises it with a room-specific bit packer `0x32ECD4`. Its size comes from
  `0x333950` → `0x32FD58`. `unpackAsRoomConfig` (`0x1238F0`) runs `0x330DE4` and then assigns the result
  (`0x34B5D0`). Lounge variants are `packAsLoungeConfig` / `unpackAsLoungeConfig`.
* The session object (`GTFramework::mOnlineSession`) exposes `updateRoomConfig` `0x171CBC`,
  `getRoomConfig` `0x1720B0`, `getRaceParameter` `0x1723BC`, `getGameParameter` `0x1764AC`,
  `prepareNetworkRace` `0x16FDE0`, `issueForceEntryOrder` `0x16FF5C`, `isRoomOwner` `0x16EFD0`, plus
  `setSelectedCar` and the member-state natives. Registrations are at `0x16C010..0x16C940`.
* `setIsLanMode` / `isLanMode` (`0x17B3E4` / `0x17B75C`) are on the lobby/session class registered at
  `0x17AA14..0x17ACFC`. `RaceParameter.is_lan` and `online_on` are race-parameter properties.
* For option A the room config does **not** need to carry AI entries. The host only has to enter the
  extra cars when the race is built.

### `RaceParameter` / `EntrySet` / `EntryBase` (script-visible properties)

* `RaceParameter` (registrations `0x151C44..0x1527F0`) has `entry_max`, `over_entry_max`, `large_entry_max`,
  `racers_max`, `online_on`, `is_lan`, `grid_sort_type`, `packet_timeout_interval/latency/lag`, `disable_collision`,
  `enable_damage` and more.
* `EntrySet` (`0x11F718..`) has `entry_num`, `player_pos`, `generate_type`, `enemy_list_type`, `ai_skill*`,
  `ai_roughness`, `enemy_lv`, `enemy_bspec_lv`, `cars`, `entry_base_array`, `delays` and `enemy_sort_type`.
  `GameParameter.removeEntriesByEntryGenerate` is `0x118B64`.
* `EntryBase` (`0x11FBD0..`) has `car`, `driver_name`, `driver_region`, `race_class_id`, `ai_skill_*`,
  `ai_roughness`, `ai_reaction`, tuning fields and `paint_id`.
* `DriverParameter` (`0x1939A0..`) has `isHuman`, `isGhost`, `setAILevel`, `setAISkill`, `special_ai_type`,
  `ai_*`. **DriverType is the top nibble of the word at impl `+0x08`** (`isHuman` → `0x38F430`:
  `(w & 0xF0000000) == 0`).

### Enums (decoded from the registration tables)

| Enum | Table | Values |
|---|---|---|
| `ControlType` | `0x15630B4` | LOCAL 0, NETWORK 1, GPSREPLAY 2 |
| `DriverType` | `0x1562AC4` | NONE -1, PLAYER 0, **AI 1**, GPS 3 |
| `EntryLevel` | `0x1563124` | SPECTATOR 0, RACER 1, ORGANIZER 2, NONE 3 |
| `RunningState` | `0x15630CC` | IS_RUNNING 0, ON_GRID 1, IN_FORMATION_LAP 2, IN_PITAREA 3, IS_PITSTOP 4, NOW_PITWORK 5, DO_NOT_FINISH 6, OUT_LAP 7, WINNING_RUN 8, IN_GARAGE 9 |
| `EnemyListType` | `0x1562504` | SAME 0, MIX 1, ONLY_PREMIUM 2, ONLY_STANDARD 3 |
| `GhostType` | `0x156315C` | NONE, FULL, ONELAP, RECORD, SECTOR_ATTACK |
| `RaceType` | `0x15634C4` | COMPETITION 0, TIMEATTACK 1, DRIFTATTACK 2, DEMO 3, OVERTAKE 4, SPEEDTEST 5, DARALOGGER 6, NONE 7 |

### Race and entry slots (`GTRace`)

* `Race` (the object at organizer impl `+0xA74`):
  * `+0x10` → race context. Its `+0xA10` is the **`GTRace::EntrySlotManager`** (vtable `0x1598288`) and
    its `+0xA24` is a per-slot network-entry array with a 0x38 stride.
  * `+0x6D4` network started (u32), `+0x744` network object (before start), `+0x748` network object
    (running). `0x469264` takes a reference to `+0x748`.
  * `+0x1F8`, `+0x204`: entry-related state used by `Race::entry`.
* `EntrySlotManager::slot(i)` `0x49F85C`: `mgr+0x04` array of `EntrySlot`, **stride `0x6D0`**. The count
  is at `[mgr+0x34]+0x18`.
* `GTRace::EntrySlot` (vtable `0x15982A0`, ctor `0x4A48B0`, reset `0x4A3DE8`):
  * `+0x4C` **ControlType**, `+0x5C` and `+0x654` set together with it by `EntrySlot::setControl`
    `0x4A1454` (`stw r6,0x5C; stw r4,0x4C; stw r5,0x654`).
  * `+0x330` linked slot (−1 none, −2 / −3 special), `+0x34` flag, `+0x50C` / `+0x20` state words.
  * `0x4A12F8(slot, blob, size)` loads the vehicle setting (car + driver) from a serialized blob.

### `Race::entry` `0x47EA4C` (the key function)

Args: r3 race, r4/r5 = **serialized vehicle-setting blob (ptr, size)**, r6 kind, r7, r8.

```
if race.isNetworkRace()           // 0x475C6C: net started (+0x6D4) and +0x748 != 0
    net = race.netRef()           // 0x469264
    ok  = net.requestEntry(blob, size, r7, r8)   // 0x491298, call site 0x47EB24
    race.netRelease()             // 0x468BEC
    return ok                     // slot is created later by the network callback
else                              // offline
    s = race.allocSlot()          // 0x478D18
    slot(s).setVehicleSetting(blob, size)        // 0x4A12F8
    slot(s).setControl(LOCAL, 0, 0)              // 0x4A1454
    ...queue the vehicle build...
```

So in an online/LAN race **the script's `ORG.entryRace` never creates a slot directly**. It asks the
network layer, and every machine creates the slot when the entry shows up.

### Network entry path (`GTRace::RaceNetworkCom`, vtable `0x1598588`)

1. `0x491298 requestEntry`: pushes a command into a 32-entry ring in the net impl
   (`+0x1F7C` read, `+0x1F80` write, `+0x1F88` record pointers; `0x4B2D50` allocs, refusing beyond 16
   pending). The record holds `+0x00` blob ptr, `+0x04` size, `+0x08/+0x0C` r7/r8, `+0x10` type (1 = entry),
   `+0x14/+0x18/+0x1C` result object ids (−1 = pending) and `+0x40` pending flag.
2. Dispatcher `0x48E600` (per tick): type 1 → `RaceNetworkCom` vtable `+0x64` = **`0x4B0730`**. That function
   creates three **STime replicated objects**, owned by this peer, through the object manager at
   `net+0x1F78` (vtable `+0x70` create, `+0x100/+0x104` lock/unlock, `+0xA0` my peer id, `+0x8C` destroy):
   * `VehicleSettingObject` (type id global `0x16409B4`): the blob copied in, plus a trailer word
   * `VehiclePacket` (type id `net+0x1FE4`, payload size `net+0x1FE8`): the car's live state stream
   * `NetworkEntryInfo` (type id `net+0x1FCC`): 64-bit handle, slot fields
   Object types are registered in `0x4B037C`. Other race-wide objects are `RaceManagement`, `TeamInfo` and
   `NetworkClientManagement` (strings at `0x1144288..`).
3. Creation callbacks (`0x4AEAB4`, `0x4AEB28`, OPDs `0x1606F48` / `0x1606F50`) fill the record's ids when
   the object was created by this peer. Type 2 then copies them into the entry's network record (`+0x1C`,
   `+0x1E`, `+0x20` u16; destroyed again by vtable `+0x50` `0x4AE7A4`).
4. On **every** machine the race's network-entry callback **`0x47EED0`** (OPD `0x1606810`, registered by
   `Race::startNetwork` `0x47A698` together with handlers `0x478E98`, `0x47B988`, `0x47D520`,
   `0x47E1B4` and `0x47EDC4`) receives `(handle, info, race)`:
   * slot index = `(s16)handle >> 9` (7 bits); `0xFE00` means invalid
   * `slot.setVehicleSetting(info+0x08, info+0x0C)`
   * `slot.setControl(info+0x00 /*ControlType*/, race, info+0x1C)`: **LOCAL on the owner, NETWORK
     elsewhere**
   * then it queues the vehicle build (record at `ctx+0xA24 + slot*0x38`, task OPD `0x16067F8`).
* Remote car state: the vehicle manager (`0x3CE280`, one per race, n vehicles) creates one
  **`GTVehicle::OnlinePacketCommunicator`** (vtable `0x15938C8`, ctor `0x3CB474`) sized for **all**
  vehicles. Layout: `+0x04` u32 *packet[n], `+0x08` s8 remap[n] (init −1) and `+0x0C` enabled.
  `getPacket(i, dst)` (vtable +0xC, `0x3CB51C`) copies **0x48 bytes** from `packet[remap[i] != -1 ?
  remap[i] : i]`.
* Sync helpers: `GTRace::NetworkEntryUpdateSync::Internal` (ctor `0x4B6AFC`) has two 32-entry tables
  (0xB8 and 0xE8 bytes per entry), so there is room for 32 entries per race. `GTRace::RaceNetworkUpdateSync`
  (`0x4B6CAC`) is a double-buffered 0x250-byte race-state block.
* STime classes (`N5STime…`): `SharedMemoryEngine`, `ObjectManager{Server,Client}`, `PeerManager`,
  `HostManager`, `MessengerP2P`, `ConnectionManager`, `PacketAggregator`, `LanGame`, `Timekeeper` and others.
  This is a replicated-object engine. Peers own objects and the engine syncs them. Wire formats weren't
  needed for option A and were not decoded.

## The probe (proposed, not built)

**Goal:** answer open questions 1 and 2 without scripts, using one game patch (`lan_ai_probe`, generated by the
launcher like `head_motion.py`; launcher-only change, so CI `windows.yml` only, ~3 min).

* Hook `0x47EB24` `bl 0x491298` (word `0x48012775`) → `bl <cave>` (RPCS3 `calloc` code cave, as the
  existing "LAN Host Member Info" patch does). The cave:
  1. Calls `0x491298(net, blob, size, r6, r7)` as the original did and keeps the result.
  2. Saves the Race pointer (r31 in the caller), blob ptr and size to `0x155F860..0x155F86C`, and
     copies up to 0x400 bytes of the blob to `0x155F900`. Both are in the free text-page tail. This lets
     the live bridge find the slot table and the blob's DriverType field.
  3. If the u32 at `0x155F870` (default 0) is N > 0 and the call succeeded, it calls `0x491298` N more
     times with **the same blob**. N stays ≤ 4 because the ring holds 16 pending commands.
* Only the **host** sets N, through its own `gt6_live.txt`: `w32 0x155F870 1`. The client instance keeps
  N = 0, so the patch does nothing there.
* Watch the state with the bridge: `r32 [0x155F860]+… ` (Race → `+0x10` → `+0xA10` slot manager →
  `+0x04` slots, stride 0x6D0, ControlType at `+0x4C`).

Expected outcomes:

| Seen | Meaning | Next |
|---|---|---|
| Client grid shows a **second copy of the host's car** that moves with the host's | Q1 and Q2 yes: extra entries replicate and stream | Step 2: in a copy of the blob, set DriverType = AI (offset found from the blob dump), give the bots different cars/names |
| Copy on the client sits frozen on the grid | Q1 yes, Q2 no: only the primary car's packet is written | RE the VehiclePacket writer (find who fills `net+0x1FE8`-sized payloads for LOCAL slots) |
| No copy anywhere, race starts normally | The extra entry was dropped (host- or peer-side acceptance) | RE `checkAcceptRaceRequest` / `RaceManagement` object handling |
| Host hangs at loading | The second request never completed (dispatcher waits for ids) | Same as above. Quit RPCS3, nothing is saved mid-race |

Step 2 risk: AI may not drive in a network race if the course AI lines aren't loaded. If the car sits
still or drives badly, look at `reduceMemoryForRace` / enemy-line loading for online races.

## Testing on one PC: two RPCS3 instances in LAN mode (plan)

Needed because both machines must run the probe build. This is untested and is a plan only.

* **Separate config dir for instance 2** (RPCS3 honours `RPCS3_CONFIG_DIR` because the bundled RPCS3
  has no `portable\` folder). For example `J:\Games\GT6\lan2\rpcs3cfg\`:
  * Copy `config\` (then edit it, see below), `patches\`, `dev_flash*`, and `dev_hdd0\home\00000001`
    (2.8 MB, GT6 save with tutorials done).
  * In `dev_hdd0\game\BCES01893\USRDIR\`, use a **directory junction** for `PDIPFS` (14 GB, read only) and
    copy the small rest (`EBOOT.BIN`, `EMAIN.SELF`, `GT6_1.x`, `car`, `db`, `grim2`, `replay`).
  * Copy the PPU/SPU caches, or let instance 2 build its own on first boot (slow).
* Instance 2 needs a **unique user name and Console PSID** (`localusername`, `config.yml` System) and the
  same game patches. The launcher writes these only into its own dir, so copy them after one launcher start.
* **Network:** GT6 LAN binds fixed ports (TCP 20000, UDP 20123-20125), so the two instances need
  different local IPs. Add a second static IPv4 address to the network adapter (or use the Microsoft
  KM-TEST Loopback Adapter with two addresses) and set `Net: Bind address` / `IP address` per instance. Whether
  Windows delivers one instance's subnet broadcast (room discovery) to the other on the same host is
  the first thing to check. A second PC avoids all of this.
* Load: two GT6 instances at once is heavy. Run instance 2 at low resolution with the frame limit on.
* Start instance 2 with `RPCS3_CONFIG_DIR` set and the same boot path the launcher uses (see the `Path:`
  line in `RPCS3.log`).

## Online (RPCN) later

With option A only the host runs the mod, and other players receive ordinary network entries. Even so,
keep it to private rooms with people who know. Other players' games are involved and the community
server's rules apply. Don't try it until LAN works.

## Script route and tooling note

The cleanest long-term implementation would be a script change in the online-room race setup: on the host,
call `ORG.entryRace` with AI driver parameters for the bots. That requires extracting the compiled
scripts from the game's `PDIPFS` and editing Adhoc bytecode. Nenkai's community tooling covers this, but
the **OpenAdhoc repository forbids AI/LLM use** (its `AGENTS.md`). These notes don't use it, and an
AI agent shouldn't read it. If the user wants the script route, they should check the licence/AI
policy of each tool and do that part themselves. The game-patch probe above needs none of it.

## Tools used (repro)

* `tools/re/elf.py`, `ppc.py`, `xref.py`, plus the cached TOC xref table `re-local/xrefs.pkl`.
* Native table: sweep the text segment for `lis/addi r4` (name) + `lis/addi r5` (OPD) followed by `bl` to a
  registration function. The most common targets are `0xCE3234` (2713 sites, methods), `0xCE4C0C` (1327,
  properties) and `0xCE4C3C` (436, static).
* Enum tables: the enum registrars load `lis r9 / addi r9` = table of `{char* name, s32 value}` and
  `addi r23, r9, size`.
* vtables: RTTI name string → typeinfo (`{vptr, name}`) → data word pointing at typeinfo + 4 = vtable of
  OPDs.
