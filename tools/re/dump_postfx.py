"""Index every SHDS shader package in a decrypted GT6 EMAIN.elf and disassemble chosen fragment programs.

    rpcs3 --decrypt EMAIN.SELF          (enter the KLIC RPCS3 logs as "KLIC=0x..." when the game runs)
    python -I tools/re/dump_postfx.py re-local/bin/EMAIN.elf [ShaderName ...]

Output stays local: never commit decrypted game code or full dumps.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elf import Elf
from shds import find_packages
from rsxfp import disasm

def main(path, names):
    e = Elf(path)
    for p in find_packages(e):
        print(f"## package {p.va:#x} size {p.size:#x}: {p.n_tech} techniques, {p.n_vp} VP, {p.n_fp} FP")
        for name, vp, fp in p.techniques():
            if fp is None:
                continue
            f = p.fp(fp)
            print(f"  {name:40s} vp={vp:3d} fp={fp:3d} ucode={f['ucode_va']:#x} size={f['size']:#x} entry={f['entry_va']:#x}")
            if name in names:
                for line in disasm(e.read(f['ucode_va'], f['size']), f['ucode_va']):
                    print("      " + line)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], set(sys.argv[2:]))
