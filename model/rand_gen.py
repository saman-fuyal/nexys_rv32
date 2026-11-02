#!/usr/bin/env python3
# =============================================================================
# rand_gen.py - random instruction-stream generator for lockstep testing
# -----------------------------------------------------------------------------
# Purpose : Produce long, varied, legal-to-run programs whose every retired
#           instruction is compared against the golden ISS (model/cosim.py).
#           The program has no self-check: the trace comparison is the check.
# Content : ALU register/immediate ops with edge-value immediates, LUI/AUIPC,
#           loads/stores of every width into a 2 KB data window (aligned and
#           deliberately misaligned), loads from random addresses (access
#           faults, IO registers), forward branches and jumps, bounded
#           backward loops, JALR through a register (aligned and misaligned
#           targets), CSR operations on safe and unimplemented CSRs, illegal
#           encodings filtered through the ISS decoder, ECALL, EBREAK, FENCE,
#           FENCE.I, WFI, and a periodic timer interrupt whose handler
#           re-arms mtimecmp with a random delay. Dense hazard patterns are
#           made more likely by drawing source registers from the last few
#           destinations.
# Rules   : x25 loop counter, x26 jump target, x27 data base, x30/x31 trap
#           handler: never written by random instructions. Stores only target
#           the data window, so the program never modifies its own code.
# Board   : --hil makes a program for the on-board self-test (host/board_hil.py):
#           nothing whose value depends on timing or on the board's previous
#           state (no interrupts, no cycle/instret counters, no IO or stray RAM
#           reads: random-address loads go to unmapped addresses and fault),
#           the CSRs it can read are cleared first, and at the end every
#           register and the whole data window are printed on the UART
#           ("HIL BEGIN" ... "HIL END"), TOHOST is written and the program
#           jumps to address 0, back into the bootloader. Its UART output is
#           therefore exactly what the golden ISS prints for the same ELF.
# Usage   : py model/rand_gen.py --seed N --count M [--hil] -o out.S
# =============================================================================
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iss as iss_mod        # noqa: E402
import params as params_mod  # noqa: E402

RESERVED = {25, 26, 27, 30, 31}
DESTS = [r for r in range(32) if r not in RESERVED]
SRCS = [r for r in range(32) if r not in (30, 31)]
EDGE_IMM = [0, 1, -1, 2047, -2048, 0x7FF, 0x400, -0x400, 31, 32, 15, 16]
SAFE_CSRS = ["mscratch", "mepc", "mcause", "mtval", "mcycle", "mcycleh", "minstret",
             "minstreth", "mip", "misa", "mstatush", "mvendorid", "marchid", "mimpid",
             "mhartid", "mconfigptr", "mie", "mstatus"]
RO_CSRS = {"mvendorid", "marchid", "mimpid", "mhartid", "mconfigptr"}
# values that differ between the board and a fresh ISS (timing, or counting the bootloader)
VOLATILE_CSRS = {"mcycle", "mcycleh", "minstret", "minstreth"}
IMPLEMENTED_CSRS = {c["addr"] for c in params_mod.load().csrs}   # bad_csr() must avoid these
UART, TOHOST = 0x40000000, 0x40000400


class Gen(object):
    def __init__(self, seed, count, irq, hil=False):
        self.r = random.Random(seed)
        self.count = count
        self.irq = irq and not hil
        self.hil = hil
        self.out = []
        self.recent = [0] * 4
        self.label = 0
        P = params_mod.load()
        self.illegal_checker = iss_mod.Iss(P)

    # ---- helpers -----------------------------------------------------------
    def L(self):
        self.label += 1
        return "L%d" % self.label

    def rd(self):
        d = self.r.choice(DESTS)
        self.recent = self.recent[1:] + [d]
        return d

    def rs(self):
        if self.r.random() < 0.5:
            return self.r.choice(self.recent)
        return self.r.choice(SRCS)

    def imm12(self):
        return self.r.choice(EDGE_IMM) if self.r.random() < 0.3 else self.r.randint(-2048, 2047)

    def emit(self, s):
        self.out.append("    " + s)

    def is_illegal(self, w):
        s = self.illegal_checker
        s.zicsr = 1
        try:
            s._execute(0x80000000, w)
        except iss_mod.Trap as t:
            return t.cause == iss_mod.EXC_ILLEGAL
        except Exception:
            return False
        return False

    # ---- instruction kinds -------------------------------------------------
    def alu_rr(self):
        op = self.r.choice(["add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and"])
        self.emit("%s x%d, x%d, x%d" % (op, self.rd(), self.rs(), self.rs()))

    def alu_ri(self):
        op = self.r.choice(["addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai"])
        if op in ("slli", "srli", "srai"):
            imm = self.r.randint(0, 31)
        else:
            imm = self.imm12()
        self.emit("%s x%d, x%d, %d" % (op, self.rd(), self.rs(), imm))

    def upper(self):
        op = self.r.choice(["lui", "auipc"])
        self.emit("%s x%d, 0x%x" % (op, self.rd(), self.r.randint(0, 0xFFFFF)))

    def load(self):
        op, sz = self.r.choice([("lb", 1), ("lbu", 1), ("lh", 2), ("lhu", 2), ("lw", 4)])
        x = self.r.random()
        if x < 0.85:
            off = self.r.randrange(0, 2040, sz) + (self.r.randint(1, sz - 1) if sz > 1 and self.r.random() < 0.1 else 0)
            self.emit("%s x%d, %d(x27)" % (op, self.rd(), off))
        elif self.hil:
            # board mode: an unmapped address, so the load always faults the same way
            base = self.r.choice([0x10000000, 0x20000000, 0x30000000, 0xC0000000, 0xF0000000])
            self.emit("li x26, 0x%08x" % (base + self.r.randrange(0, 0x100000, 4)))
            self.emit("%s x%d, %d(x26)" % (op, self.rd(), self.imm12()))
        else:
            self.emit("%s x%d, %d(x%d)" % (op, self.rd(), self.imm12(), self.rs()))

    def store(self):
        op, sz = self.r.choice([("sb", 1), ("sh", 2), ("sw", 4)])
        off = self.r.randrange(0, 2040, sz) + (self.r.randint(1, sz - 1) if sz > 1 and self.r.random() < 0.1 else 0)
        self.emit("%s x%d, %d(x27)" % (op, self.rs(), off))

    def branch(self):
        op = self.r.choice(["beq", "bne", "blt", "bge", "bltu", "bgeu"])
        l = self.L()
        self.emit("%s x%d, x%d, %s" % (op, self.rs(), self.rs(), l))
        for _ in range(self.r.randint(0, 3)):
            self.simple()
        self.out.append("%s:" % l)

    def jal(self):
        l = self.L()
        self.emit("jal x%d, %s" % (self.rd(), l))
        for _ in range(self.r.randint(0, 2)):
            self.simple()
        self.out.append("%s:" % l)

    def jalr(self):
        l = self.L()
        self.emit("la x26, %s" % l)
        off = 2 if self.r.random() < 0.15 else (1 if self.r.random() < 0.1 else 0)
        self.emit("jalr x%d, %d(x26)" % (self.rd(), off))
        if off & 2:
            # misaligned: traps, handler resumes at the next instruction
            self.emit("nop")
        self.out.append("%s:" % l)

    def loop(self):
        l = self.L()
        self.emit("li x25, %d" % self.r.randint(1, 4))
        self.out.append("%s:" % l)
        for _ in range(self.r.randint(1, 5)):
            self.simple()
        self.emit("addi x25, x25, -1")
        self.emit("bnez x25, %s" % l)

    def csr(self):
        pool = [c for c in SAFE_CSRS if not (self.hil and (c in VOLATILE_CSRS or c in ("mie", "mstatus")))]
        c = self.r.choice(pool)
        k = self.r.random()
        if c in ("mie", "mstatus"):
            # keep these meaningful: toggle MTIE / MIE only
            bit = 0x80 if c == "mie" else 0x8
            self.emit("li x%d, 0x%x" % (self.recent[-1] if self.recent[-1] not in (0,) else 5, bit))
            self.emit("%s x%d, %s, x%d" % (self.r.choice(["csrrs", "csrrc"]), self.rd(), c,
                                           self.recent[-2] if self.recent[-2] != 0 else 5))
            return
        if c in RO_CSRS and k < 0.7:
            self.emit("csrrs x%d, %s, x0" % (self.rd(), c))
        elif k < 0.4:
            self.emit("%s x%d, %s, x%d" % (self.r.choice(["csrrw", "csrrs", "csrrc"]), self.rd(), c, self.rs()))
        else:
            self.emit("%s x%d, %s, %d" % (self.r.choice(["csrrwi", "csrrsi", "csrrci"]), self.rd(), c,
                                          self.r.randint(0, 31)))

    def bad_csr(self):
        addr = self.r.choice([0x7C0, 0xC00, 0xC01, 0x180, 0x302, 0x303, 0x320, 0x3A0, 0x7B0, None])
        while addr is None or addr in IMPLEMENTED_CSRS:   # a random address must not hit a real CSR
            addr = self.r.randint(0, 0xFFF)
        self.emit("csrrs x%d, 0x%x, x%d" % (self.rd(), addr, self.rs()))

    def illegal(self):
        for _ in range(100):
            w = self.r.getrandbits(32)
            if self.r.random() < 0.5:
                w = (w & ~0x7F) | self.r.choice([0x33, 0x13, 0x03, 0x23, 0x63, 0x67, 0x73, 0x0F])
            if self.is_illegal(w):
                self.emit(".word 0x%08x" % w)
                return
        self.emit(".word 0x00000000")

    def system(self):
        self.emit(self.r.choice(["ecall", "ebreak", "fence", "fence.i", "wfi", "fence rw, rw", "fence.tso"]))

    def simple(self):
        k = self.r.random()
        if k < 0.35:
            self.alu_rr()
        elif k < 0.65:
            self.alu_ri()
        elif k < 0.72:
            self.upper()
        elif k < 0.88:
            self.load()
        else:
            self.store()

    def any(self):
        k = self.r.random()
        if k < 0.60:
            self.simple()
        elif k < 0.70:
            self.branch()
        elif k < 0.74:
            self.jal()
        elif k < 0.78:
            self.jalr()
        elif k < 0.81:
            self.loop()
        elif k < 0.88:
            self.csr()
        elif k < 0.90:
            self.bad_csr()
        elif k < 0.94:
            self.illegal()
        else:
            self.system()

    # ---- whole program ------------------------------------------------------
    def program(self):
        r = self.r
        o = self.out
        o.append("/* generated by model/rand_gen.py - DO NOT EDIT */")
        o.append("    .option arch, +zicsr")
        o.append("    .option norvc")
        o.append("    .section .text.init, \"ax\"")
        o.append("    .globl _start")
        o.append("_start:")
        self.emit("la x31, trap")
        self.emit("csrw mtvec, x31")
        self.emit("la x27, rdata")
        for i in range(1, 32):
            if i not in RESERVED:
                self.emit("li x%d, 0x%08x" % (i, r.choice([0, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF,
                                                          r.getrandbits(32), r.getrandbits(32)])))
        if self.hil:
            # known register and CSR state whatever ran before; timer compare at its maximum (no interrupt)
            self.emit("li x25, 0")          # reserved registers can be read before their first write
            self.emit("li x26, 0")
            for c in ("mscratch", "mepc", "mcause", "mtval", "mie", "mstatus"):
                self.emit("csrw %s, x0" % c)
            self.emit("li x30, 0x40000300")
            self.emit("li x31, -1")
            self.emit("sw x31, 12(x30)")
            self.emit("sw x31, 8(x30)")
        if self.irq:
            self.emit("li x30, 0x40000300")
            self.emit("lw x31, 0(x30)")
            self.emit("addi x31, x31, %d" % r.randint(1, 10))
            self.emit("li x26, -1")
            self.emit("sw x26, 12(x30)")
            self.emit("sw x31, 8(x30)")
            self.emit("sw x0, 12(x30)")
            self.emit("li x26, 0x80")
            self.emit("csrs mie, x26")
            self.emit("csrsi mstatus, 8")
        n0 = len(o)
        while len(o) - n0 < self.count:
            self.any()
        self.emit("csrci mstatus, 8")
        if self.hil:
            self.hil_epilogue()
        else:
            self.emit("li x30, 0x40000400")
            self.emit("li x31, 1")
            self.emit("sw x31, 0(x30)")
            o.append("1:  j 1b")
        o.append("    .balign 4")
        o.append("trap:")
        self.emit("csrr x31, mcause")
        self.emit("bltz x31, irq")
        self.emit("csrr x31, mepc")
        self.emit("addi x31, x31, 4")
        self.emit("csrw mepc, x31")
        self.emit("mret")
        o.append("irq:")
        self.emit("li x30, 0x40000300")
        self.emit("li x31, -1")
        self.emit("sw x31, 12(x30)")
        self.emit("lw x31, 0(x30)")
        self.emit("addi x31, x31, %d" % r.randint(1, 6))
        self.emit("sw x31, 8(x30)")
        self.emit("sw x0, 12(x30)")
        self.emit("mret")
        o.append("    .data")
        o.append("    .balign 16")
        o.append("rdata:")
        for _ in range(512):
            o.append("    .word 0x%08x" % r.getrandbits(32))
        if self.hil:
            o.append("    .balign 4")
            o.append("hilsave:")
            o.append("    .space 128")
        o.append("    .section .tohost, \"aw\", @nobits")
        o.append("tohost: .dword 0")
        return "\n".join(o) + "\n"


    # ---- board-mode end: dump registers and data on the UART, back to the bootloader
    def hil_epilogue(self):
        e, o = self.emit, self.out
        e("la x30, hilsave")
        for i in range(1, 30):
            e("sw x%d, %d(x30)" % (i, 4 * i))
        e("li x1, 0x%08x" % UART)

        def puts(text):
            for ch in text:
                e("li x5, %d" % ord(ch))
                self.putc()

        def dump(label_base, count):
            l, d = self.L(), self.L()
            e("la x2, %s" % label_base)
            e("li x3, %d" % count)
            o.append("%s:" % l)
            e("lw x4, 0(x2)")
            e("li x7, 8")
            o.append("%s:" % d)
            e("srli x5, x4, 28")
            e("addi x5, x5, 48")
            e("li x6, 58")
            skip = self.L()
            e("blt x5, x6, %s" % skip)
            e("addi x5, x5, 39")
            o.append("%s:" % skip)
            self.putc()
            e("slli x4, x4, 4")
            e("addi x7, x7, -1")
            e("bnez x7, %s" % d)
            e("li x5, 10")
            self.putc()
            e("addi x2, x2, 4")
            e("addi x3, x3, -1")
            e("bnez x3, %s" % l)
        puts("HIL BEGIN\n")
        dump("hilsave+4", 29)
        dump("rdata", 512)
        puts("HIL END\n")
        w = self.L()
        o.append("%s:" % w)
        e("lw x6, 8(x1)")
        e("andi x6, x6, 1")
        e("bnez x6, %s" % w)
        e("li x30, 0x%08x" % TOHOST)
        e("li x31, 1")
        e("sw x31, 0(x30)")
        e("jalr x0, 0(x0)")

    def putc(self):
        """x5 -> UART (x1 = UART base), waiting while TX_BUSY."""
        w = self.L()
        self.out.append("%s:" % w)
        self.emit("lw x6, 8(x1)")
        self.emit("andi x6, x6, 1")
        self.emit("bnez x6, %s" % w)
        self.emit("sw x5, 0(x1)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=2000, help="approximate instruction lines")
    ap.add_argument("--no-irq", action="store_true")
    ap.add_argument("--hil", action="store_true", help="on-board self-test program (see header)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    g = Gen(a.seed, a.count, not a.no_irq, a.hil)
    with open(a.out, "w", newline="\n") as fh:
        fh.write(g.program())


if __name__ == "__main__":
    main()
