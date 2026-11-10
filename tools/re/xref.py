"""Resolve TOC-relative address construction in PS3 PPU code (lwz rX,d(r2) / addi rY,rX,k / addi rY,r2,k).

Heuristic linear sweep: tracks register values within a function, forgets them at calls/branches-to-LR.
xrefs(e, toc) -> dict[target_va] = [instruction_va, ...]
"""
import struct
from collections import defaultdict

def s16(v): return v - 0x10000 if v & 0x8000 else v

def build_xrefs(e, toc, text_va=None, text_size=None):
    va0, off, fsz, _, _ = e.segs[0]
    if text_va is None: text_va, text_size = va0, fsz
    code = e.b[off + (text_va - va0): off + (text_va - va0) + text_size]
    words = struct.unpack(f">{len(code)//4}I", code[:len(code)//4*4])
    data_lo, data_hi = e.segs[1][0], e.segs[1][0] + e.segs[1][3]
    def rd32(va):
        try: return e.u32(va)
        except KeyError: return None
    refs = defaultdict(list)
    regs = {}
    for i, w in enumerate(words):
        pc = text_va + 4 * i
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, s16(w & 0xFFFF)
        if op == 32 and ra == 2:                      # lwz rd, d(r2)
            v = rd32((toc + imm) & 0xFFFFFFFF)
            regs[rd] = v
            if v is not None: refs[v].append(pc)
            refs[(toc + imm) & 0xFFFFFFFF].append(pc)
        elif op == 14:                                # addi rd, ra, imm
            if ra == 2:
                v = (toc + imm) & 0xFFFFFFFF; regs[rd] = v; refs[v].append(pc)
            elif ra in regs and regs[ra] is not None:
                v = (regs[ra] + imm) & 0xFFFFFFFF; regs[rd] = v; refs[v].append(pc)
            else: regs.pop(rd, None)
        elif op == 15 and ra == 0:                    # lis rd, imm
            regs[rd] = (imm << 16) & 0xFFFFFFFF
        elif op == 24 and ra in regs and regs.get(ra) is not None and rd == ra:  # ori rd, rd, imm
            regs[ra] = regs[ra] | (w & 0xFFFF); refs[regs[ra]].append(pc)
        elif op == 18 and (w & 1):                    # bl: clobbers volatile regs
            for r in (0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12): regs.pop(r, None)
        elif w == 0x4E800020:                         # blr
            regs.clear()
        else:
            # any other instruction writing rd invalidates it (rough: most D/X-forms put rD in bits 21-25)
            if op not in (36, 37, 38, 39, 44, 45, 47, 52, 53, 54, 55, 62, 16, 17, 18, 19, 10, 11, 3, 2):
                regs.pop(rd, None)
    return refs

def find_calls(e, target):
    """All 'bl target' / 'b target' sites in the text segment."""
    va0, off, fsz, _, _ = e.segs[0]
    code = e.b[off:off + fsz]
    out = []
    for i in range(0, len(code) - 3, 4):
        w = int.from_bytes(code[i:i+4], "big")
        if w >> 26 == 18 and not (w & 2):
            li = w & 0x03FFFFFC
            if li & 0x02000000: li -= 0x04000000
            if va0 + i + li == target: out.append((va0 + i, "bl" if w & 1 else "b"))
    return out
