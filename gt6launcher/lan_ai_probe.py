"""Research probe: extra entries in a GT6 LAN race (EMAIN 1.22, EU). Notes: docs/re/gt6-lan-ai.md.

In a network race ``Race::entry`` (0x47EA4C) does not create a car slot itself: it asks the race network
layer (``requestEntry`` 0x491298, called at 0x47EB24) to publish the entry (STime objects
VehicleSettingObject / VehiclePacket / NetworkEntryInfo), and every machine then builds the slot.

This patch puts a code cave on that call. It always makes the original call, records what it saw in a
small block at ``BASE`` (unused tail of the RW data segment, past the end of .bss) and, if the u32
``BASE+0x00`` is N > 0 (set on the room host only, through the live bridge ``gt6_live.txt``), repeats
the request N more times (max 8): with the same car setup blob, or with a copy of it in which one word
is rewritten (``BASE+0x28`` byte offset != 0: word = (word & AND) | OR) - meant for switching the
DriverType of the copies to AI once the blob layout is known.

With N = 0 (the default) it only records, so the game behaves as stock.

Block layout (u32 unless noted):
  +0x00 N extra entries (bridge writes)      +0x04 Race*              +0x08 blob*      +0x0C blob size
  +0x10 net*                                 +0x14 first result       +0x18 hook calls +0x1C extra entries accepted
  +0x20 arg r6                               +0x24 arg r7
  +0x28 patch offset (bridge, 0 = off)       +0x2C AND mask (bridge)  +0x30 OR mask (bridge)
  +0x100..+0x7FF copy of the blob (up to 0x700 bytes)
"""
from __future__ import annotations

PATCH_NAME = "LAN AI Probe (research)"
VERIFIED_TITLES = {"BCES01893"}

HOOK = 0x0047EB24          # bl 0x491298 (requestEntry) inside Race::entry
HOOK_ORIG = 0x48012775
REQUEST_ENTRY = 0x00491298
# Guest code writes this block, so it must be in the RW data segment: the data segment's memsz ends at
# 0x17F9578 and RPCS3 maps it in 64K pages up to 0x1800000. (The text tail 0x1551000..0x155FFFF is
# read-only for guest code - 0x155E000 crashed with "Access violation writing ... (read-only memory)".)
# 0x17FB000..0x17FB7FF is clear of every lis/addi address in EMAIN that points past .bss.
BASE = 0x017FB000
COPY_OFF = 0x100
COPY_MAX = 0x700
MAX_EXTRA = 8


# --------------------------------------------------------------------------- tiny PPC encoder
def _d(op, rt, ra, imm):
    return (op << 26) | (rt << 21) | (ra << 16) | (imm & 0xFFFF)


def _x(rt, ra, rb, xo, rc=0):
    return (31 << 26) | (rt << 21) | (ra << 16) | (rb << 11) | (xo << 1) | rc


def stdu(rs, d, ra): return (62 << 26) | (rs << 21) | (ra << 16) | (d & 0xFFFC) | 1
def stw(rs, d, ra): return _d(36, rs, ra, d)
def lwz(rt, d, ra): return _d(32, rt, ra, d)
def stwu(rs, d, ra): return _d(37, rs, ra, d)
def lwzu(rt, d, ra): return _d(33, rt, ra, d)
def addi(rt, ra, imm): return _d(14, rt, ra, imm)  # ra = 0 means literal 0 (li)
def addic_(rt, ra, imm): return _d(13, rt, ra, imm)
def lis(rt, imm): return _d(15, rt, 0, imm)
def ori(ra, rs, imm): return _d(24, rs, ra, imm)
def li(rt, imm): return addi(rt, 0, imm)
def cmpwi(ra, imm): return _d(11, 0, ra, imm)
def cmplwi(ra, imm): return _d(10, 0, ra, imm)
def lwzx(rt, ra, rb): return _x(rt, ra, rb, 23)
def stwx(rs, ra, rb): return _x(rs, ra, rb, 151)
def and_(ra, rs, rb): return _x(rs, ra, rb, 28)
def or_(ra, rs, rb): return _x(rs, ra, rb, 444)
def srwi(ra, rs, n): return (21 << 26) | (rs << 21) | (ra << 16) | ((32 - n) << 11) | (n << 6) | (31 << 1)
def mtctr(rs): return 0x7C0903A6 | (rs << 21)


BCTRL = 0x4E800421

_BC = {"beq": (12, 2), "bne": (4, 2), "ble": (4, 1), "bgt": (12, 1), "blt": (12, 0), "bdnz": (16, 0)}


def _assemble(prog):
    """prog: list of words, ("label", name) or (branch_mnemonic, label)."""
    labels, pc = {}, 0
    for item in prog:
        if isinstance(item, tuple) and item[0] == "label":
            labels[item[1]] = pc
        else:
            pc += 4
    out, pc = [], 0
    for item in prog:
        if isinstance(item, tuple):
            if item[0] == "label":
                continue
            mn, target = item
            off = labels[target] - pc
            if mn == "b":
                out.append(0x48000000 | (off & 0x03FFFFFC))
            else:
                bo, bi = _BC[mn]
                out.append((16 << 26) | (bo << 21) | (bi << 16) | (off & 0xFFFC))
        else:
            out.append(item & 0xFFFFFFFF)
        pc += 4
    return out


def _base(r):
    hi = (BASE + 0x8000) >> 16
    return [lis(r, hi), addi(r, r, BASE - (hi << 16))]


def _call_request():
    return [lis(12, REQUEST_ENTRY >> 16), ori(12, 12, REQUEST_ENTRY & 0xFFFF), mtctr(12), BCTRL]


def cave_words() -> list[int]:
    """Entered by a branch from HOOK with r3 net, r4 blob, r5 size, r6, r7 as for the original call and r31 =
    Race; leaves with r3 = result of the original call (RPCS3 appends the branch back to HOOK+4)."""
    p = [
        stdu(1, -0x80, 1),
        stw(3, 0x70, 1),                       # net
        *_base(11),
        stw(31, 0x04, 11), stw(4, 0x08, 11), stw(5, 0x0C, 11), stw(3, 0x10, 11),
        stw(6, 0x20, 11), stw(7, 0x24, 11),
        lwz(9, 0x18, 11), addi(9, 9, 1), stw(9, 0x18, 11),
        # copy min((size+3)/4, COPY_MAX/4) words of the blob to BASE+COPY_OFF
        addi(10, 5, 3), srwi(10, 10, 2),
        cmplwi(10, COPY_MAX // 4), ("ble", "cnt_ok"), li(10, COPY_MAX // 4),
        ("label", "cnt_ok"),
        cmpwi(10, 0), ("beq", "copied"),
        mtctr(10), addi(9, 11, COPY_OFF - 4), addi(8, 4, -4),
        ("label", "copy"),
        lwzu(0, 4, 8), stwu(0, 4, 9), ("bdnz", "copy"),
        ("label", "copied"),
        # optional word rewrite in the copy
        lwz(8, 0x28, 11), cmpwi(8, 0), ("beq", "no_rewrite"),
        addi(9, 11, COPY_OFF), lwzx(0, 9, 8),
        lwz(10, 0x2C, 11), and_(0, 0, 10), lwz(10, 0x30, 11), or_(0, 0, 10),
        stwx(0, 9, 8),
        ("label", "no_rewrite"),
        # the original call (r3..r7 untouched so far)
        *_call_request(),
        stw(3, 0x74, 1),
        *_base(11), stw(3, 0x14, 11),
        cmpwi(3, 0), ("beq", "done"),
        lwz(0, 0x00, 11), cmpwi(0, 0), ("ble", "done"),
        cmplwi(0, MAX_EXTRA), ("ble", "n_ok"), li(0, MAX_EXTRA),
        ("label", "n_ok"),
        stw(0, 0x78, 1),
        ("label", "again"),
        *_base(11),
        lwz(3, 0x70, 1), lwz(4, 0x08, 11), lwz(5, 0x0C, 11),
        lwz(0, 0x28, 11), cmpwi(0, 0), ("beq", "use_blob"),
        cmplwi(5, COPY_MAX), ("bgt", "done"),       # copy would be truncated: stop
        addi(4, 11, COPY_OFF),
        ("label", "use_blob"),
        lwz(6, 0x20, 11), lwz(7, 0x24, 11),
        *_call_request(),
        *_base(11),
        cmpwi(3, 0), ("beq", "next"),
        lwz(9, 0x1C, 11), addi(9, 9, 1), stw(9, 0x1C, 11),
        ("label", "next"),
        lwz(0, 0x78, 1), addic_(0, 0, -1), stw(0, 0x78, 1), ("bgt", "again"),
        ("label", "done"),
        lwz(3, 0x74, 1),
        addi(1, 1, 0x80),
    ]
    return _assemble(p)


def patch_yaml(title_id: str) -> str:
    """Patch entry for the launcher's <TITLE>_patch.yml; empty for titles not checked."""
    if title_id not in VERIFIED_TITLES:
        return ""
    words = cave_words()
    lines = [
        f'  "{PATCH_NAME}":',
        "    Games:",
        '      "Gran Turismo 6":',
        f"        {title_id}: [ 01.22 ]",
        '    Author: "GT6 Launcher"',
        '    Notes: "Research: on the LAN room host, repeats the race entry request N times (N written to '
        f'{BASE:#x} via gt6_live.txt) to test extra (AI) cars. Inert while N = 0."',
        "    Patch Version: 1.0",
        "    Patch:",
        f"      - [ calloc, {HOOK:#010x}, {len(words)} ]  # was bl {REQUEST_ENTRY:#x} [{HOOK_ORIG:#010x}]",
    ]
    lines += [f"      - [ be32, 0x0, {w:#010x} ]" for w in words]
    return "\n".join(lines) + "\n"
