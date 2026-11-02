#!/usr/bin/env python3
# =============================================================================
# gen_vectors.py - golden test vectors for the block-level unit testbenches
# -----------------------------------------------------------------------------
# Purpose : Expected values for the ALU, immediate generator, decoder,
#           load/store formatting and bus decoder, computed by the golden ISS
#           (or, for immediates and byte lanes, straight from the ISA text),
#           never by the RTL.
# Outputs : sim/build/unit/vectors/{alu,imm,dec,lsu_req,lsu_load,bus}.hex
#           One vector per line as fixed-width hex fields ($readmemh into a
#           wide register in each testbench).
# =============================================================================
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "model"))
import iss as iss_mod        # noqa: E402
import params as params_mod  # noqa: E402

OUT = os.path.join(ROOT, "sim", "build", "unit", "vectors")
R = random.Random(2026)
M = 0xFFFFFFFF
EDGES = [0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF, 0xFFFFFFFE, 31, 32, 0x55555555,
         0xAAAAAAAA, 0x0000FFFF, 0xFFFF0000]


def rnd32():
    return R.choice(EDGES) if R.random() < 0.3 else R.getrandbits(32)


def iss():
    P = params_mod.load()
    s = iss_mod.Iss(P)
    s.csr_check = False
    return s


# ALU op encoding {alt, funct3} -> R-type instruction with rd=x3, rs1=x1, rs2=x2
ALU_OPS = [(0x0, 0, 0), (0x8, 0, 0x20), (0x1, 1, 0), (0x2, 2, 0), (0x3, 3, 0), (0x4, 4, 0),
           (0x5, 5, 0), (0xD, 5, 0x20), (0x6, 6, 0), (0x7, 7, 0)]


def gen_alu(s):
    lines = []
    for op, f3, f7 in ALU_OPS:
        for i in range(400):
            a, b = rnd32(), rnd32()
            s.x[1], s.x[2] = a, b
            insn = (f7 << 25) | (2 << 20) | (1 << 15) | (f3 << 12) | (3 << 7) | 0x33
            s._execute(0x80000000, insn)
            y = s.x[3]
            bf3 = R.choice([0, 1, 4, 5, 6, 7])
            s.pc = 0x80000000
            br = (bf3 << 12) | (2 << 20) | (1 << 15) | (8 << 7) | 0x63      # offset 8
            rec = s._execute(0x80000000, br)
            taken = 1 if s.pc == 0x80000008 else 0
            lines.append("%01x%01x%01x%08x%08x%08x" % (op, bf3, taken, a, b, y))
    return lines


def imm_of(insn, kind):
    def sx(v, n):
        return (v - (1 << n)) & M if v >> (n - 1) else v
    if kind == 0:
        return sx(insn >> 20, 12)
    if kind == 1:
        return sx(((insn >> 25) << 5) | ((insn >> 7) & 31), 12)
    if kind == 2:
        return sx(((insn >> 31) << 12) | (((insn >> 7) & 1) << 11) | (((insn >> 25) & 63) << 5)
                  | (((insn >> 8) & 15) << 1), 13)
    if kind == 3:
        return insn & 0xFFFFF000
    if kind == 4:
        return sx(((insn >> 31) << 20) | (((insn >> 12) & 255) << 12) | (((insn >> 20) & 1) << 11)
                  | (((insn >> 21) & 1023) << 1), 21)
    return (insn >> 15) & 31


def gen_imm():
    lines = []
    for kind in range(6):
        for i in range(500):
            insn = rnd32()
            lines.append("%01x%08x%08x" % (kind, insn, imm_of(insn, kind)))
    return lines


def gen_dec(s):
    """Legality of an encoding as the ISS sees it (CSR address checks off)."""
    lines = []
    words = []
    opcodes = [0x03, 0x0F, 0x13, 0x17, 0x23, 0x33, 0x37, 0x63, 0x67, 0x6F, 0x73]
    for opc in opcodes:
        for f3 in range(8):
            for f7 in (0x00, 0x20, 0x01, 0x40, 0x7F, 0x02):
                words.append((f7 << 25) | (R.getrandbits(13) << 12 & 0x01FF8000) | (f3 << 12)
                             | (R.getrandbits(5) << 7) | opc)
    words += [0x00000073, 0x00100073, 0x30200073, 0x10500073, 0x00000000, 0xFFFFFFFF, 0x000000F3,
              0x00200073, 0x10200073, 0x7FF00073, 0x0000100F, 0x0FF0000F, 0x8330000F]
    for i in range(6000):
        w = R.getrandbits(32)
        if R.random() < 0.7:
            w = (w & ~0x7F) | R.choice(opcodes + [0x0B, 0x2B, 0x5B, 0x7B, 0x07, 0x27, 0x53])
        words.append(w)
    for w in words:
        s.x = [0] * 32
        s.x[0] = 0
        ill = 0
        try:
            s._execute(0x80000000, w)
        except iss_mod.Trap as t:
            ill = 1 if t.cause == iss_mod.EXC_ILLEGAL else 0
        lines.append("%01x%08x" % (ill, w))
    return lines


def gen_lsu():
    req, load = [], []
    for size in range(3):
        for lo in range(4):
            for i in range(40):
                d = rnd32()
                nb = 1 << size
                mis = 1 if lo % nb else 0
                strb = 0 if mis and size != 0 else (((1 << nb) - 1) << lo) & 0xF
                if size == 2:
                    strb = 0xF
                    mis = 1 if lo else 0
                if size == 1:
                    strb = 0xC if lo & 2 else 0x3
                if size == 0:
                    wd = (d & 0xFF) * 0x01010101
                elif size == 1:
                    wd = (d & 0xFFFF) * 0x00010001
                else:
                    wd = d
                req.append("%01x%01x%08x%01x%01x%08x" % (size, lo, d, mis, strb, wd & M))
                for uns in (0, 1):
                    raw = rnd32()
                    if size == 0:
                        v = (raw >> (8 * lo)) & 0xFF
                        if not uns and v & 0x80:
                            v |= 0xFFFFFF00
                    elif size == 1:
                        v = (raw >> (16 * (lo >> 1))) & 0xFFFF
                        if not uns and v & 0x8000:
                            v |= 0xFFFF0000
                    else:
                        v = raw
                    load.append("%01x%01x%01x%08x%08x" % (size, lo, uns, raw, v))
    return req, load


def gen_bus():
    """Address decode: expected fault for (addr, size, we) per the ISS SoC."""
    P = params_mod.load()
    soc = iss_mod.Soc(P)
    lines = []
    bases = [P.rom["base"], P.ram["base"], P.io["base"], 0x10000000, 0x20000000, 0xC0000000]
    addrs = []
    for b in bases:
        for off in [0, 4, 0x7FC, 0x800, 0xFFC, 0x1000, 0xFFFC, 0x10000, 0x100, 0x108, 0x10C, 0x110,
                    0x200, 0x20C, 0x300, 0x30C, 0x310, 0x400, 0x410, 0x414, 0x500, 0xF00]:
            addrs.append((b + off) & M)
    for i in range(3000):
        addrs.append(R.choice(bases) + R.randrange(0, 0x20000, 4))
    for a in addrs:
        for size in (0, 1, 2):
            for we in (0, 1):
                aa = a & ~((1 << size) - 1)
                reg = soc.region(aa)
                ok = (reg == "ram") or (reg == "rom" and not we) or \
                     (reg == "io" and size == 2 and soc.io_reg(aa) is not None)
                ifault = 0 if soc.region(aa) in ("ram", "rom") else 1
                lines.append("%01x%01x%01x%01x%08x" % (size, we, 0 if ok else 1, ifault, aa & M))
    return lines


def write(name, lines):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".hex"), "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(lines)


def main():
    s = iss()
    n = {}
    n["alu"] = write("alu", gen_alu(s))
    n["imm"] = write("imm", gen_imm())
    n["dec"] = write("dec", gen_dec(iss()))
    req, load = gen_lsu()
    n["lsu_req"] = write("lsu_req", req)
    n["lsu_load"] = write("lsu_load", load)
    n["bus"] = write("bus", gen_bus())
    print("vectors: " + ", ".join("%s=%d" % kv for kv in n.items()))


if __name__ == "__main__":
    main()
