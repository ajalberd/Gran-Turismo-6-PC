"""GT6 'SHDS' shader package parser (layout reverse-engineered from EMAIN 1.22).

header  +0x04 size, +0x14 n_tech, +0x18 (u16 n_vp, u16 n_fp), +0x1c tech table, +0x20 vp table
fp table at +0x60, 0x20 bytes each: (0, param_off, ucode_off, ucode_size, ...)
tech table, 12 bytes each: (name_off, 0, u16 vp_index, u16 program_index)
  program_index counts fragment programs in *parameter-block address order* (fp entry field 1), not
  table order: verified with ColorCorrect (pow shader, 3 uniforms) and AlexHaust's blur/exposure entries.
vp table, 0x20 bytes each: (ucode_off, size, ...)
All offsets are relative to the package start (32-bit wrap).
"""
import re, struct
from elf import Elf

class Package:
    def __init__(self, e: Elf, va: int):
        self.e, self.va = e, va
        h = e.read(va, 0x40)
        self.size, = struct.unpack_from(">I", h, 4)
        self.n_tech, = struct.unpack_from(">I", h, 0x14)
        self.n_vp, self.n_fp = struct.unpack_from(">HH", h, 0x18)
        self.tech_off, self.vp_off = struct.unpack_from(">II", h, 0x1c)
    def addr(self, off): return (self.va + off) & 0xFFFFFFFF
    def cstr(self, off):
        d = self.e.read(self.addr(off), 128); return d[:d.index(0)].decode("ascii", "replace")
    def fp(self, i):
        ent = self.addr(0x60 + 0x20 * i)
        _, param, uoff, usz = struct.unpack(">IIII", self.e.read(ent, 16))
        return {"index": i, "entry_va": ent, "param_va": self.addr(param), "ucode_va": self.addr(uoff), "size": usz}
    def fp_by_program_index(self, idx):
        if not hasattr(self, "_order"):
            params = [struct.unpack(">I", self.e.read(self.addr(0x60 + 0x20 * k + 4), 4))[0] for k in range(self.n_fp)]
            self._order = sorted(range(self.n_fp), key=lambda k: params[k])
        return self._order[idx] if idx < self.n_fp else None

    def techniques(self):
        """[(name, vp_index, fp_table_index)]"""
        out = []
        for i in range(self.n_tech):
            no, _, vp, fp = struct.unpack(">IIHH", self.e.read(self.addr(self.tech_off + 12 * i), 12))
            out.append((self.cstr(no), vp, self.fp_by_program_index(fp)))
        return out

def find_packages(e: Elf):
    res = []
    for m in re.finditer(b"SHDS", e.b):
        for va, o, fsz, msz, fl in e.segs:
            if o <= m.start() < o + fsz: res.append(Package(e, va + m.start() - o))
    return res
