"""Minimal RSX (NV47) fragment program disassembler, bitfields from RPCS3 RSXFragmentProgram.h."""
import struct
OPS = ["NOP","MOV","MUL","ADD","MAD","DP3","DP4","DST","MIN","MAX","SLT","SGE","SLE","SGT","SNE","SEQ","FRC","FLR",
       "KIL","PK4","UP4","DDX","DDY","TEX","TXP","TXD","RCP","RSQ","EX2","LG2","LIT","LRP","STR","SFL","COS","SIN",
       "PK2","UP2","POW","PKB","UPB","PK16","UP16","BEM","PKG","UPG","DP2A","TXL","NULL","TXB","NULL","TEXBEM",
       "TXPBEM","BEMLUM","REFL","TIMESWTEX","DP2","NRM","DIV","DIVSQ","LIF","FENCT","FENCB","NULL","BRK","CAL","IFE",
       "LOOP","REP","RET"]
NSRC = {"NOP":0,"MOV":1,"MUL":2,"ADD":2,"MAD":3,"DP3":2,"DP4":2,"DST":2,"MIN":2,"MAX":2,"SLT":2,"SGE":2,"SLE":2,
        "SGT":2,"SNE":2,"SEQ":2,"FRC":1,"FLR":1,"KIL":0,"PK4":1,"UP4":1,"DDX":1,"DDY":1,"TEX":1,"TXP":1,"TXD":3,
        "RCP":1,"RSQ":1,"EX2":1,"LG2":1,"LIT":1,"LRP":3,"STR":0,"SFL":0,"COS":1,"SIN":1,"PK2":1,"UP2":1,"POW":2,
        "PKB":1,"UPB":1,"PK16":1,"UP16":1,"BEM":3,"PKG":1,"UPG":1,"DP2A":3,"TXL":2,"TXB":2,"REFL":2,"DP2":2,"NRM":1,
        "DIV":2,"DIVSQ":2,"LIF":1}
ATTR = ["WPOS","COL0","COL1","FOGC","TEX0","TEX1","TEX2","TEX3","TEX4","TEX5","TEX6","TEX7","TEX8","TEX9","SSA"]
SW = "xyzw"
PREC = {0: "", 1: "_H", 2: "_X12", 3: "_X9"}
SCALE = {0: "", 1: "_x2", 2: "_x4", 3: "_x8", 5: "_d2", 6: "_d4", 7: "_d8"}

def bf(v, lo, n): return (v >> lo) & ((1 << n) - 1)
def ins_word(be): return ((be & 0xFFFF) << 16) | (be >> 16)  # RSX ucode words: 16-bit halves swapped
def const_word(be): return ((be & 0xFFFF) << 16) | (be >> 16)
def f32(u): return struct.unpack(">f", struct.pack(">I", u))[0]

def src(s, d, consts, is_src0):
    t = bf(s, 0, 2)
    swz = "".join(SW[bf(s, 9 + 2 * i, 2)] for i in range(4))
    swz = "" if swz == "xyzw" else "." + swz
    if t == 0: r = ("H" if bf(s, 8, 1) else "R") + str(bf(s, 2, 6))
    elif t == 1: r = ATTR[bf(d, 13, 4)] if bf(d, 13, 4) < len(ATTR) else f"IN{bf(d,13,4)}"
    elif t == 2: r = "C(" + ", ".join(f"{c:g}" for c in consts) + ")" if consts else "C"
    else: r = "?"
    r += swz
    ab = bf(s, 29, 1) if is_src0 else bf(s, 18, 1)
    if ab: r = f"|{r}|"
    if bf(s, 17, 1): r = "-" + r
    return r

def disasm(data: bytes, base_va: int = 0):
    out, i = [], 0
    while i + 16 <= len(data):
        w = [ins_word(x) for x in struct.unpack_from(">IIII", data, i)]
        d, s0, s1, s2 = w
        op = bf(d, 24, 6) | (bf(s1, 31, 1) << 6)
        name = OPS[op] if op < len(OPS) else f"OP{op:#x}"
        uses_c = any(bf(x, 0, 2) == 2 for x in (s0, s1, s2)[:max(1, NSRC.get(name, 3))])
        consts = None
        if uses_c and i + 32 <= len(data):
            consts = [f32(const_word(x)) for x in struct.unpack_from(">IIII", data, i + 16)]
        mask = "".join(c for j, c in enumerate(SW) if bf(d, 9 + j, 1))
        dst = ("H" if bf(d, 7, 1) else "R") + str(bf(d, 1, 6)) + ("" if mask == "xyzw" else "." + mask)
        if bf(d, 30, 1): dst = "RC" + ("" if mask == "xyzw" else "." + mask)
        mods = PREC.get(bf(d, 22, 2), "") + SCALE.get(bf(s1, 28, 3), "") + ("_sat" if bf(d, 31, 1) else "") + ("C" if bf(d, 8, 1) else "")
        n = NSRC.get(name, 3)
        srcs = [src(s, d, consts, k == 0) for k, s in enumerate((s0, s1, s2)[:n])]
        if name in ("TEX", "TXP", "TXL", "TXB", "TXD"): srcs.append(f"TEX{bf(d, 17, 4)}")
        out.append(f"{base_va + i:#010x}  {name}{mods} {dst}, " + ", ".join(srcs) + ("   ; END" if bf(d, 0, 1) else ""))
        i += 32 if consts is not None else 16
        if bf(d, 0, 1): break
    return out
