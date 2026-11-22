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

The probe below answers 1 and 2 with one small game patch, tested between two PCs. It needs no emulator
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
  * `+0x10` → race context. Its `+0xA10` holds a **pointer** to the **`GTRace::EntrySlotManager`** (vtable `0x1598288`;
    every caller of `slot()` does `lwz r3,0xA10(ctx)`) and
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
* **Slot allocation (found after probe run 6).** The owner never picks a slot. `0x4B0730` creates the
  NetworkEntryInfo with slot field −1 (bits 9..15 of the u64 at info+0x20 = 0x7F, which reads as `0xFE00`).
  Slots are then handed out per peer through a shared object, RM = `[impl+0x54]` (impl = `[net]`, where net
  is the `requestEntry` r3):
  * RM layout: `+0x00` u16 owner peer id of slots 0..31, `+0x80` byte flags[32], `+0xA0` u16 request
    queue[32], `+0xE0` / `+0xE1` queue read / write index, `+0xE2` queue closed.
  * NetworkEntryInfo create callback `0x4AFBA0` (OPD `0x1606FF8`, registered in `0x4B037C` for the 0x40-byte
    type `impl+0x1FCC`): if the object is mine and objmgr `+0xB0` is true (I am the host), `push(impl, owner)`
    runs (`0x4B4DF4`, skipped while `+0xE2` is set).
  * Per tick `0x4B4240`: if host (`impl+0x1F98` == `impl+0x1F9C`), pop one queued peer and get a free slot
    from `[impl+0x38]([impl+0x44])` = `0x478E98` → **`Race::allocSlot` `0x478D18`**. That function cycles over
    `[[Race+0x18]+0x18]` slots and takes one that is not in use (`slot+0x4D8 == 0`) and not net-taken
    (`0x48E92C` → `0x4B4C00`). Then `RM.owner[slot] = peer`.
  * The same function, for my oldest pending entry record (ring at `[impl+0x1C]`, read/write
    `impl+0x1B0C` / `+0x1B10`), waits until all three object ids are set (record obj `+0x1C/+0x1E/+0x20` != −1).
    It then takes the first i with `RM.owner[i] == impl+0x1F9C` (my peer id) and `impl+0x1648+i == 0`,
    writes i into the slot field and sets the taken byte. **With no such i the record is not given a
    slot** (`b 0x4B4728`).
  * So a peer gets one slot per NetworkEntryInfo it creates, as long as the host's queue push and `allocSlot`
    both succeed. Run 6 has to show which of these steps stopped the second entry.

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

## The probe (built: `gt6launcher/lan_ai_probe.py`)

**Goal:** answer open questions 1 and 2 without scripts, using one game patch ("LAN AI Probe (research)",
generated by the launcher like `head_motion.py` and enabled with LAN play). It is a launcher-only change,
so CI `windows.yml` only.

* Hook `0x47EB24` `bl 0x491298` (word `0x48012775`): an RPCS3 `calloc` code cave of 83 words, like the
  "LAN Host Member Info" patch. The cave:
  1. Records the Race pointer (r31 in the caller), net, blob ptr, size, args r6/r7 and a call counter, and
     copies up to 0x700 bytes of the blob.
  2. Optionally rewrites one word of that copy: `word = (word & AND) | OR` at a byte offset. This is meant
     for setting DriverType = AI once the blob layout is known.
  3. Makes the original call (`lis/ori/mtctr/bctrl`, since the cave address is not known) and keeps the result.
  4. If the call succeeded and N > 0, calls `0x491298` N more times (capped at 8) with the same blob, or
     with the rewritten copy when the offset is set. It counts the accepted calls.
* **Data block** at `0x17FB000` (u32 unless noted):

  | Offset | Field | Offset | Field |
  |---|---|---|---|
  | `+0x00` | N extra entries (bridge writes it) | `+0x18` | hook calls |
  | `+0x04` | Race* | `+0x1C` | extra entries accepted |
  | `+0x08` | blob* | `+0x20` / `+0x24` | args r6 / r7 |
  | `+0x0C` | blob size | `+0x28` | rewrite byte offset (0 = off, bridge) |
  | `+0x10` | net* | `+0x2C` / `+0x30` | AND / OR mask (bridge) |
  | `+0x14` | first result | `+0x100..+0x7FF` | blob copy |

  * The block lives in the unused tail of the **RW data segment**: memsz ends at `0x17F9578`, and RPCS3
    maps it in 64K pages up to `0x1800000`. `0x17FB000..0x17FB7FF` is clear of every `lis`/`addi` address
    in EMAIN that points past .bss.
  * The first build used `0x155E000`, the text segment's mapped tail. RPCS3 maps that tail, so patches and
    the bridge can write it, but **guest stores fault**. The host crashed on entering the online lobby with
    `VM: Access violation writing location 0x155e004 (read-only memory)`, because the cave records on
    every call even with N = 0. Guest-written patch data must go in the data segment.
* Only the **host** sets N, through its own `datapcs3\gt6_live.txt`: `w32 0x17FB000 1`. The other PC keeps
  N = 0, so the patch only records there.
* Read the block with `r32 0x17FB000 13` (results go to `gt6_live_out.txt`). The slot table is at
  `r32 [[[0x17FB004]+0x10]+0xA10]+4 …`: slots have a stride of 0x6D0, with ControlType at `+0x4C`.

Expected outcomes:

| Seen | Meaning | Next |
|---|---|---|
| Client grid shows a **second copy of the host's car** that moves with the host's | Q1 and Q2 yes: extra entries replicate and stream | Step 2: in a copy of the blob, set DriverType = AI (offset found from the blob dump), give the bots different cars/names |
| Copy on the client sits frozen on the grid | Q1 yes, Q2 no: only the primary car's packet is written | RE the VehiclePacket writer (find who fills `net+0x1FE8`-sized payloads for LOCAL slots) |
| No copy anywhere, race starts normally | The extra entry was dropped (host- or peer-side acceptance) | RE `checkAcceptRaceRequest` / `RaceManagement` object handling |
| Host hangs at loading | The second request never completed (dispatcher waits for ids) | Same as above. Quit RPCS3, nothing is saved mid-race |

Step 2 risk: AI may not drive in a network race if the course AI lines aren't loaded. If the car sits
still or drives badly, look at `reduceMemoryForRace` / enemy-line loading for online races.

## Test log

* **Run 1 (build with block at 0x155E000):** the host crashed on entering the online lobby, with a write fault
  in the cave. Fixed in `1360cd5` (block moved to `0x17FB000`). So `Race::entry` already runs on lobby
  entry.
* **Run 2 (1360cd5, host alone, N = 0):** the host reached the lobby. At 0:02:03 of emulation the game froze
  with `VM: Access violation writing location 0x42e71d00 (unmapped memory)` in memcpy `0xc5a510`,
  called from `0x4b5db8`, which copies 0x68 bytes into `*(obj)`. The call stack is `0x4b6168`
  (walks a 32-slot ring, stride 0xE8 at obj+0x18 and 0xB8 at obj+4) <- `0xa08748` <- `0xa0c100` <- `0xaf7f24`.
  That is the GTRace network-sync area. It looks like a stale pointer, not a probe effect:
  * `requestEntry` `0x491298` takes `r3` = net and `r4..r7`, and returns 0/1 (`extsw`). The cave doesn't
    touch `r3..r7` before the original call. It uses only volatile registers (`r0`, `r8..r12`, CTR, cr0)
    and keeps a 0x80-byte ABI frame (the callee saves LR at +0x10, locals at +0x70..+0x7B). It leaves
    `r2` alone, and the caller reloads everything it needs after the call (`mr r29,r3`).
  * No code or data in EMAIN refers to `0x17F9578..0x1800000`, counting each register's first use after
    `lis` and data words in the data segment. The TOC window ends at `0x164CF38`.
  * With N = 0 the cave adds only reads of the blob and writes to its own block.
* **Run 3 (1360cd5, solo LAN room, then the track, N = 0):** the `sgx-audio-thr` thread read a
  garbage pointer, `0x10730121`, at `0xcb54dc` (LR `0xcaa8b8`). The probe block afterwards read
  `00000000 4fe00ab0 42550000 0000045f 4fff40a0 00000001 00000001 00000000 4fd4e000 000000c0`. So there was
  one hook call with a 0x45F-byte blob (copied to `0x17FB100..0x17FB55F`), `requestEntry` returned 1, and
  there were no extras.
  * RPCS3 maps the data segment with one `falloc` in 64K pages (`vm.cpp` `block_t::falloc`):
    `0x1560000..0x17FFFFF` belongs to the segment. No PRX, HLE stub or patch cave can be placed there
    (the probe's cave is at `0x18E0000`), and the loader only zero-fills filesz..memsz.
* **Crashes depend on the track:** Trial Mountain always works, while Autumn Ring and Nürburgring GP crash.
  This matches upstream issue Mabec-games/Gran-Turismo-6-PC#43 ("LAN mode crashes on certain tracks").
  Treat runs 2 and 3 as a GT6/RPCS3 LAN bug, not a probe effect. Probe tests use **Trial Mountain**.
* **Run 4 (19:21:33, all patches, N = 0):** the log ends abruptly at 1:43 with no fatal error and no Windows
  crash record. The block showed 1 hook call, result 1.
* **Run 5 (20:43, solo Trial Mountain):** this tested nothing, because N was still 0. GT6 boots `EBOOT.BIN`,
  which exit-spawns `EMAIN.SELF` (the log shows two loader passes, at 0:00:04 and 0:00:29). The bridge's
  one-shot `w32` fired during the EBOOT stage, and that memory was replaced when EMAIN loaded. Use `w32!` (every
  poll) for N. The block again showed one hook call for the whole run (lobby/room entry plus the race), so N
  must already be set when entering the lobby.
* **Run 6 (09:01, solo Trial Mountain, N = 1 via `w32!`):** no second car. Block: N=1, 1 hook call, first
  result 1, **1 extra entry accepted** (the second `requestEntry` returned 1). The slot reads were not
  conclusive: ControlType 0 is also the value of an unused slot. Next run reads the slot-allocation
  chain (see "Slot allocation") with in-use flags `slot+0x4D8`, RM, the taken bytes and the ring indices.
* **Run 7 (09:12, solo Trial Mountain, N = 1):** still no second car, but **the second entry got a slot**:
  * host and my peer id both 0; `RM.owner[0] = RM.owner[1] = 0`, the rest `0xFFFF`; RM flags `01 01`;
    queue rd = wr = 2, not closed
  * taken bytes `impl+0x1648` = `01 01`, entry and command rings 2/2 (both done)
  * slots 0 and 1 in use (`+0x4D8` = 1), both ControlType LOCAL, capacity 16
  So `0x47EED0` ran for both. It loads the blob (`0x4A12F8`), calls `setControl`, fills the build record
  `ctx+0xA24 + slot*0x38` (`+0x24` slot*, `+0x28` slot#, `+0x30` = 1 pending, `+0x34` Race), bumps
  `Race+0x210` and queues the build task `0x47E52C` (OPD `0x16067F8`) on `ctx+0xA18`. The drop is
  after that: the vehicle build, the grid / racer list, or the car is built but not placed. Next run
  dumps both slots in full (436 words each) and both build records, to diff them.
* **Bridge reads for the slots:** mgr = `[[[0x17FB004]+0x10]+0xA10]`. The count is at `[mgr+0x34]+0x18`, and
  slot i's ControlType at `[mgr+4] + i*0x6D0 + 0x4C`.

## Test setup: two PCs on the same LAN

The two-RPCS3-instances-on-one-PC plan was dropped because a second PC is available.

* Both PCs run the same launcher build (the patch must load on both, but N stays 0 on the client), the
  EU game at 1.22, LAN play enabled, a unique player name and Console PSID, and Bind address set to the PC's
  own LAN IPv4 address. Set the bind address explicitly on a PC that also has a VPN adapter (for example
  Radmin VPN).
* Windows firewall: the network profile is Private and RPCS3 is allowed on Private networks.
* This PC (host) is the only one that writes N.

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
