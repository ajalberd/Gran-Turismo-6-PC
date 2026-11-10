"""Tiny big-endian ELF64 loader: map PS3 virtual addresses to bytes."""
import struct
class Elf:
    def __init__(self, path):
        self.b = open(path, "rb").read()
        b = self.b
        phoff, = struct.unpack_from(">Q", b, 0x20); phentsize, phnum = struct.unpack_from(">HH", b, 0x36)
        self.segs = []
        for i in range(phnum):
            t, fl, off, va, pa, fsz, msz, al = struct.unpack_from(">IIQQQQQQ", b, phoff + i * phentsize)
            if t == 1: self.segs.append((va, off, fsz, msz, fl))
    def read(self, va, n):
        for sva, off, fsz, msz, fl in self.segs:
            if sva <= va < sva + msz:
                rel = va - sva
                data = self.b[off + rel: off + min(fsz, rel + n)]
                return data + bytes(n - len(data))
        raise KeyError(hex(va))
    def u32(self, va): return struct.unpack(">I", self.read(va, 4))[0]
