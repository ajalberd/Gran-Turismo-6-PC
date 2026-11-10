"""PPC disassembly helpers (capstone, big-endian PPC64) with TOC/string annotation."""
import struct, capstone
from elf import Elf
_md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_64 | capstone.CS_MODE_BIG_ENDIAN)

def func_start(e: Elf, va: int, limit=0x4000):
    """Walk back to the 'stdu r1,-N(r1)' / 'mflr r0' prologue."""
    for a in range(va, va - limit, -4):
        w = e.u32(a)
        if (w & 0xFFFF0003) == 0xF8210001:   # stdu r1, -N(r1)
            # mflr r0 is usually just before or after; include it
            return a - 4 if e.u32(a - 4) == 0x7C0802A6 else a
    return va

def cstr_at(e, va, maxlen=48):
    try:
        d = e.read(va, maxlen)
    except KeyError:
        return None
    if 0 in d:
        s = d[:d.index(0)]
        if len(s) >= 3 and all(32 <= c < 127 for c in s): return s.decode()
    return None

def disasm(e: Elf, va: int, n: int, notes=None):
    out = []
    for ins in _md.disasm(e.read(va, n), va):
        line = f"{ins.address:#010x}  {e.u32(ins.address):08x}  {ins.mnemonic:8s} {ins.op_str}"
        if notes and ins.address in notes: line += "    ; " + notes[ins.address]
        out.append(line)
    return out
