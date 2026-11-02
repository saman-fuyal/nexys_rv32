#!/usr/bin/env python3
# =============================================================================
# iss.py - golden instruction-set simulator for the nexys_rv32 SoC
# -----------------------------------------------------------------------------
# Purpose : Reference model written from the RISC-V specifications, not from
#           the RTL. Any difference between its retired-instruction trace and
#           the RTL trace is treated as a bug in one of the two.
# Scope   : RV32I base, Zicsr, machine-mode trap/interrupt handling (as listed
#           in params.json), optional Zifencei, and the SoC memory map with
#           functional models of UART, GPIO, 7-segment, timer and sysctrl.
# Trace   : one line per event
#             R <pc> <insn> <rd> <rdval> <mem>
#               mem = '-' | L:<addr> | S:<addr>:<strb>:<data>
#             T <mcause> <mepc> <mtval>        (trap or interrupt taken)
#           All numbers hex, 8 digits except rd (2 decimal) and strb (1 hex).
# Modes   : standalone  - runs on its own; peripherals advance with a
#                         nominal cycle count (cycles_per_insn)
#           follow      - steps in sync with an RTL trace; timing-dependent
#                         read values and interrupt points come from the RTL
#                         record, everything else must match exactly.
# =============================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as params_mod  # noqa: E402

MASK = 0xFFFFFFFF

# mcause codes (Privileged spec, table "Machine cause register values")
EXC_INSN_MISALIGNED = 0
EXC_INSN_FAULT = 1
EXC_ILLEGAL = 2
EXC_BREAKPOINT = 3
EXC_LOAD_MISALIGNED = 4
EXC_LOAD_FAULT = 5
EXC_STORE_MISALIGNED = 6
EXC_STORE_FAULT = 7
EXC_ECALL_M = 11
IRQ_MTIMER = (1 << 31) | 7

MSTATUS_MIE = 1 << 3
MSTATUS_MPIE = 1 << 7
MSTATUS_MPP = 3 << 11
MIP_MTIP = 1 << 7


def sext(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


class Trap(Exception):
    def __init__(self, cause, tval):
        Exception.__init__(self)
        self.cause = cause
        self.tval = tval & MASK


class Uart(object):
    def __init__(self):
        self.tx = bytearray()
        self.rx = []
        self.on_tx = None

    def read(self, idx):
        if idx == 1:                       # RXDATA
            return self.rx.pop(0) if self.rx else 0
        if idx == 2:                       # STATUS
            return (2 if self.rx else 0)
        return 0

    def write(self, idx, v):
        if idx == 0:
            b = v & 0xFF
            self.tx.append(b)
            if self.on_tx:
                self.on_tx(b)


class Soc(object):
    """Memory map and peripheral models."""

    def __init__(self, P, pipelined=True):
        self.P = P
        self.rom = bytearray(P.rom["size"])
        self.ram = bytearray(P.ram["size"])
        self.rom_base, self.rom_size = P.rom["base"], P.rom["size"]
        self.ram_base, self.ram_size = P.ram["base"], P.ram["size"]
        self.io_base, self.io_size = P.io["base"], P.io["size"]
        self.pidx = {pd["index"]: (n, pd["nregs"]) for n, pd in P.periph.items()}
        self.uart = Uart()
        self.leds = 0
        self.switches = 0
        self.buttons = 0
        self.btn_edge = 0
        self.seg_value = 0
        self.seg_en = 0xFF
        self.seg_dp = 0
        self.mtime = 0
        self.mtimecmp = (1 << 64) - 1
        self.tohost = 0
        self.tohost_hi = 0
        self.features = P.features_word(pipelined)

    # ---- address classification -------------------------------------------
    def region(self, addr):
        if self.ram_base <= addr < self.ram_base + self.ram_size:
            return "ram"
        if self.rom_base <= addr < self.rom_base + self.rom_size:
            return "rom"
        if self.io_base <= addr < self.io_base + self.io_size:
            return "io"
        return None

    def io_reg(self, addr):
        off = addr - self.io_base
        p = self.pidx.get(off >> 8)
        if p is None:
            return None
        ridx = (off & 0xFF) >> 2
        if ridx >= p[1]:
            return None
        return p[0], ridx

    def volatile(self, addr):
        """Reads whose value depends on timing or external inputs."""
        r = self.io_reg(addr) if self.region(addr) == "io" else None
        if r is None:
            return False
        name, idx = r
        return (name == "uart" and idx in (1, 2)) or \
               (name == "gpio" and idx in (1, 2, 3)) or \
               (name == "timer" and idx in (0, 1))

    # ---- program loading ---------------------------------------------------
    def load_bytes(self, addr, data):
        for i, b in enumerate(data):
            a = addr + i
            reg = self.region(a)
            if reg == "ram":
                self.ram[a - self.ram_base] = b
            elif reg == "rom":
                self.rom[a - self.rom_base] = b
            else:
                raise ValueError("load address 0x%08x outside ROM/RAM" % a)

    # ---- instruction fetch -------------------------------------------------
    def fetch(self, pc):
        reg = self.region(pc)
        if reg == "ram":
            o = pc - self.ram_base
            m = self.ram
        elif reg == "rom":
            o = pc - self.rom_base
            m = self.rom
        else:
            raise Trap(EXC_INSN_FAULT, pc)
        return m[o] | (m[o + 1] << 8) | (m[o + 2] << 16) | (m[o + 3] << 24)

    # ---- data access ------------------------------------------------------
    def load(self, addr, size):
        reg = self.region(addr)
        if reg == "ram":
            o, m = addr - self.ram_base, self.ram
        elif reg == "rom":
            o, m = addr - self.rom_base, self.rom
        elif reg == "io":
            r = self.io_reg(addr)
            if r is None or size != 4:
                raise Trap(EXC_LOAD_FAULT, addr)
            return self.io_read(*r)
        else:
            raise Trap(EXC_LOAD_FAULT, addr)
        v = 0
        for i in range(size):
            v |= m[o + i] << (8 * i)
        return v

    def store_check(self, addr, size):
        reg = self.region(addr)
        if reg == "ram":
            return
        if reg == "io" and size == 4 and self.io_reg(addr) is not None:
            return
        raise Trap(EXC_STORE_FAULT, addr)

    def store(self, addr, size, v):
        reg = self.region(addr)
        if reg == "ram":
            o = addr - self.ram_base
            for i in range(size):
                self.ram[o + i] = (v >> (8 * i)) & 0xFF
        else:
            self.io_write(self.io_reg(addr), v & MASK)

    def io_read(self, name, idx):
        if name == "uart":
            return self.uart.read(idx)
        if name == "gpio":
            return (self.leds, self.switches, self.buttons, self.btn_edge)[idx]
        if name == "seg7":
            return (self.seg_value, self.seg_en, self.seg_dp)[idx]
        if name == "timer":
            return ((self.mtime & MASK), self.mtime >> 32,
                    self.mtimecmp & MASK, self.mtimecmp >> 32)[idx]
        if name == "sysctrl":
            return (self.tohost, self.tohost_hi, self.P.cpu_hz, self.features,
                    self.P.build_id)[idx]
        return 0

    def io_write(self, r, v):
        name, idx = r
        if name == "uart":
            self.uart.write(idx, v)
        elif name == "gpio":
            if idx == 0:
                self.leds = v & 0xFFFF
            elif idx == 3:
                self.btn_edge &= ~v & 0x1F
        elif name == "seg7":
            if idx == 0:
                self.seg_value = v
            elif idx == 1:
                self.seg_en = v & 0xFF
            elif idx == 2:
                self.seg_dp = v & 0xFF
        elif name == "timer":
            if idx == 0:
                self.mtime = (self.mtime & ~MASK) | v
            elif idx == 1:
                self.mtime = (self.mtime & MASK) | (v << 32)
            elif idx == 2:
                self.mtimecmp = (self.mtimecmp & ~MASK) | v
            elif idx == 3:
                self.mtimecmp = (self.mtimecmp & MASK) | (v << 32)
        elif name == "sysctrl":
            if idx == 0:
                self.tohost = v
            elif idx == 1:
                self.tohost_hi = v

    def mtip(self):
        return self.mtime >= self.mtimecmp


class Iss(object):
    """RV32I + Zicsr + M-mode traps."""

    def __init__(self, P, soc=None, pipelined=True):
        self.P = P
        self.soc = soc or Soc(P, pipelined)
        self.x = [0] * 32
        self.pc = P.reset_vector
        self.mstatus = MSTATUS_MPP          # MPP hardwired to M
        self.mie = 0
        self.mtvec = 0
        self.mscratch = 0
        self.mepc = 0
        self.mcause = 0
        self.mtval = 0
        self.mcycle = 0
        self.minstret = 0
        self.cycles = 0                     # standalone time base
        self.cycles_per_insn = 1
        self.timer_phase = 0
        self.follow = None                  # RTL record during follow mode
        self.zicsr = P.zicsr
        self.zifencei = P.zifencei
        self.irq_enabled_model = True       # standalone interrupts
        self.halted = False
        self.csr_check = True               # False: decoder-only view (unit vectors)

    # ---- CSRs --------------------------------------------------------------
    def csr_exists(self, a):
        return self.zicsr and a in (0x300, 0x301, 0x304, 0x305, 0x310, 0x340, 0x341, 0x342,
                                    0x343, 0x344, 0xB00, 0xB02, 0xB80, 0xB82, 0xF11, 0xF12,
                                    0xF13, 0xF14, 0xF15)

    def csr_volatile(self, a):
        return a in (0x344, 0xB00, 0xB80)

    def csr_read(self, a):
        if a == 0x300:
            return self.mstatus
        if a == 0x301:
            return self.P.misa
        if a == 0x304:
            return self.mie
        if a == 0x305:
            return self.mtvec
        if a == 0x310:
            return 0
        if a == 0x340:
            return self.mscratch
        if a == 0x341:
            return self.mepc
        if a == 0x342:
            return self.mcause
        if a == 0x343:
            return self.mtval
        if a == 0x344:
            return MIP_MTIP if (self.P.timer_irq and self.soc.mtip()) else 0
        if a == 0xB00:
            return self.mcycle & MASK
        if a == 0xB80:
            return self.mcycle >> 32
        if a == 0xB02:
            return self.minstret & MASK
        if a == 0xB82:
            return self.minstret >> 32
        if a == 0xF13:
            return self.P.mimpid
        return 0                            # mvendorid, marchid, mhartid, mconfigptr

    def csr_write(self, a, v):
        """Returns True if the write suppresses the minstret increment."""
        v &= MASK
        if a == 0x300:
            self.mstatus = (v & (MSTATUS_MIE | MSTATUS_MPIE)) | MSTATUS_MPP
        elif a == 0x304:
            self.mie = v & (MIP_MTIP if self.P.timer_irq else 0)
        elif a == 0x305:
            self.mtvec = v & ~3
        elif a == 0x340:
            self.mscratch = v
        elif a == 0x341:
            self.mepc = v & ~3
        elif a == 0x342:
            self.mcause = v
        elif a == 0x343:
            self.mtval = v
        elif a == 0xB00:
            self.mcycle = (self.mcycle & ~MASK) | v
        elif a == 0xB80:
            self.mcycle = (self.mcycle & MASK) | (v << 32)
        elif a == 0xB02:
            self.minstret = (self.minstret & ~MASK) | v
            return True
        elif a == 0xB82:
            self.minstret = (self.minstret & MASK) | (v << 32)
            return True
        return False                        # misa, mstatush, mip: WARL, ignored

    # ---- trap entry ---------------------------------------------------------
    def take_trap(self, cause, tval, epc):
        self.mepc = epc & ~3
        self.mcause = cause & MASK
        self.mtval = tval & MASK
        mie = 1 if self.mstatus & MSTATUS_MIE else 0
        self.mstatus = (mie << 7) | MSTATUS_MPP
        self.pc = self.mtvec
        return ("T", cause & MASK, epc & MASK, tval & MASK)

    def irq_pending(self):
        return (self.P.timer_irq and (self.mstatus & MSTATUS_MIE) and (self.mie & MIP_MTIP)
                and self.soc.mtip())

    # ---- time base (standalone) -------------------------------------------
    def advance(self, n):
        self.cycles += n
        self.mcycle = (self.mcycle + n) & ((1 << 64) - 1)
        self.timer_phase += n
        d = self.P.timer_div
        if self.timer_phase >= d:
            k, self.timer_phase = divmod(self.timer_phase, d)
            self.soc.mtime = (self.soc.mtime + k) & ((1 << 64) - 1)

    # ---- one step -----------------------------------------------------------
    def step(self):
        """Execute one instruction or take one trap. Returns a trace tuple."""
        if self.follow is None:
            if self.irq_enabled_model and self.irq_pending():
                return self.take_trap(IRQ_MTIMER, 0, self.pc)
            rec = self._exec()
            self.advance(self.cycles_per_insn)
            return rec
        return self._exec()

    def _exec(self):
        pc = self.pc
        try:
            insn = self.soc.fetch(pc)
            return self._execute(pc, insn)
        except Trap as t:
            return self.take_trap(t.cause, t.tval, pc)

    def _ill(self, insn):
        raise Trap(EXC_ILLEGAL, insn)

    def _execute(self, pc, insn):
        x = self.x
        op = insn & 0x7F
        rd = (insn >> 7) & 31
        f3 = (insn >> 12) & 7
        rs1 = (insn >> 15) & 31
        rs2 = (insn >> 20) & 31
        f7 = insn >> 25
        a = x[rs1]
        b = x[rs2]
        npc = (pc + 4) & MASK
        wb = None                     # value written to rd (None = no write)
        mem = "-"
        suppress_instret = False

        if op == 0x33:                                        # OP
            if f7 == 0:
                if f3 == 0:
                    wb = a + b
                elif f3 == 1:
                    wb = a << (b & 31)
                elif f3 == 2:
                    wb = 1 if sext(a, 32) < sext(b, 32) else 0
                elif f3 == 3:
                    wb = 1 if a < b else 0
                elif f3 == 4:
                    wb = a ^ b
                elif f3 == 5:
                    wb = a >> (b & 31)
                elif f3 == 6:
                    wb = a | b
                else:
                    wb = a & b
            elif f7 == 0x20 and f3 == 0:
                wb = a - b
            elif f7 == 0x20 and f3 == 5:
                wb = sext(a, 32) >> (b & 31)
            else:
                self._ill(insn)
        elif op == 0x13:                                      # OP-IMM
            imm = sext(insn >> 20, 12)
            if f3 == 0:
                wb = a + imm
            elif f3 == 2:
                wb = 1 if sext(a, 32) < imm else 0
            elif f3 == 3:
                wb = 1 if a < (imm & MASK) else 0
            elif f3 == 4:
                wb = a ^ imm
            elif f3 == 6:
                wb = a | imm
            elif f3 == 7:
                wb = a & imm
            elif f3 == 1:
                if f7 != 0:
                    self._ill(insn)
                wb = a << rs2
            else:  # f3 == 5
                if f7 == 0:
                    wb = a >> rs2
                elif f7 == 0x20:
                    wb = sext(a, 32) >> rs2
                else:
                    self._ill(insn)
        elif op == 0x37:                                      # LUI
            wb = insn & 0xFFFFF000
        elif op == 0x17:                                      # AUIPC
            wb = pc + (insn & 0xFFFFF000)
        elif op == 0x6F:                                      # JAL
            imm = sext(((insn >> 31) << 20) | (((insn >> 12) & 0xFF) << 12) |
                       (((insn >> 20) & 1) << 11) | (((insn >> 21) & 0x3FF) << 1), 21)
            tgt = (pc + imm) & MASK
            if tgt & 3:
                raise Trap(EXC_INSN_MISALIGNED, tgt)
            wb = npc
            npc = tgt
        elif op == 0x67:                                      # JALR
            if f3 != 0:
                self._ill(insn)
            tgt = (a + sext(insn >> 20, 12)) & MASK & ~1
            if tgt & 3:
                raise Trap(EXC_INSN_MISALIGNED, tgt)
            wb = npc
            npc = tgt
        elif op == 0x63:                                      # BRANCH
            if f3 == 0:
                t = a == b
            elif f3 == 1:
                t = a != b
            elif f3 == 4:
                t = sext(a, 32) < sext(b, 32)
            elif f3 == 5:
                t = sext(a, 32) >= sext(b, 32)
            elif f3 == 6:
                t = a < b
            elif f3 == 7:
                t = a >= b
            else:
                self._ill(insn)
            if t:
                imm = sext(((insn >> 31) << 12) | (((insn >> 7) & 1) << 11) |
                           (((insn >> 25) & 0x3F) << 5) | (((insn >> 8) & 0xF) << 1), 13)
                tgt = (pc + imm) & MASK
                if tgt & 3:
                    raise Trap(EXC_INSN_MISALIGNED, tgt)
                npc = tgt
        elif op == 0x03:                                      # LOAD
            size = (1, 2, 4, 0, 1, 2, 0, 0)[f3]
            if size == 0:
                self._ill(insn)
            addr = (a + sext(insn >> 20, 12)) & MASK
            if addr & (size - 1):
                raise Trap(EXC_LOAD_MISALIGNED, addr)
            if self.follow is not None and self.soc.volatile(addr):
                self.soc.load(addr, size)                     # same fault checks
                v = self.follow[4]
            else:
                v = self.soc.load(addr, size)
                if f3 == 0:
                    v = sext(v, 8)
                elif f3 == 1:
                    v = sext(v, 16)
            wb = v
            mem = "L:%08x" % addr
        elif op == 0x23:                                      # STORE
            size = (1, 2, 4, 0, 0, 0, 0, 0)[f3]
            if size == 0:
                self._ill(insn)
            imm = sext(((insn >> 25) << 5) | ((insn >> 7) & 31), 12)
            addr = (a + imm) & MASK
            if addr & (size - 1):
                raise Trap(EXC_STORE_MISALIGNED, addr)
            self.soc.store_check(addr, size)
            v = b & ((1 << (8 * size)) - 1)
            self.soc.store(addr, size, v)
            lane = addr & 3
            strb = ((1 << size) - 1) << lane
            mem = "S:%08x:%x:%08x" % (addr, strb, (v << (8 * lane)) & MASK)
        elif op == 0x0F:                                      # MISC-MEM
            if f3 == 0:
                pass                                          # FENCE: in-order core
            elif f3 == 1 and self.zifencei:
                pass                                          # FENCE.I: no I-cache
            else:
                self._ill(insn)
        elif op == 0x73:                                      # SYSTEM
            if f3 == 0:
                if insn == 0x00000073:
                    raise Trap(EXC_ECALL_M, 0)
                elif insn == 0x00100073:
                    raise Trap(EXC_BREAKPOINT, pc)
                elif insn == 0x30200073 and self.zicsr:       # MRET
                    npc = self.mepc
                    mpie = 1 if self.mstatus & MSTATUS_MPIE else 0
                    self.mstatus = (mpie << 3) | MSTATUS_MPIE | MSTATUS_MPP
                elif insn == 0x10500073 and self.zicsr:       # WFI as NOP
                    pass
                else:
                    self._ill(insn)
            elif f3 == 4:
                self._ill(insn)
            else:
                csr = insn >> 20
                if self.csr_check and not self.csr_exists(csr):
                    self._ill(insn)
                src = rs1 if f3 >= 5 else a                   # uimm or rs1 value
                kind = f3 & 3                                 # 1 rw, 2 rs, 3 rc
                writes = kind == 1 or rs1 != 0
                if self.csr_check and writes and (csr >> 10) == 3:
                    self._ill(insn)
                if self.follow is not None and self.csr_volatile(csr) and rd != 0:
                    old = self.follow[4]
                else:
                    old = self.csr_read(csr)
                if writes:
                    if kind == 1:
                        new = src
                    elif kind == 2:
                        new = old | src
                    else:
                        new = old & ~src
                    suppress_instret = self.csr_write(csr, new)
                wb = old
        else:
            self._ill(insn)

        if wb is not None and rd != 0:
            wb &= MASK
            x[rd] = wb
        else:
            rd = 0
            wb = 0
        self.pc = npc
        if not suppress_instret:
            self.minstret = (self.minstret + 1) & ((1 << 64) - 1)
        return ("R", pc, insn, rd, wb, mem)


def fmt(rec):
    if rec[0] == "R":
        return "R %08x %08x %02d %08x %s" % rec[1:]
    return "T %08x %08x %08x" % rec[1:]


def parse(line):
    f = line.split()
    if not f:
        return None
    if f[0] == "R":
        return ("R", int(f[1], 16), int(f[2], 16), int(f[3]), int(f[4], 16), f[5])
    if f[0] == "T":
        return ("T", int(f[1], 16), int(f[2], 16), int(f[3], 16))
    return None


def load_program(iss, path):
    """Load an ELF or a hex file (32-bit words, @address lines allowed)."""
    import elf as elf_mod
    if path.endswith(".elf") or open(path, "rb").read(4) == b"\x7fELF":
        e = elf_mod.load(path)
        for addr, data, memsz in e.segments:
            if iss.soc.region(addr) == "io":
                continue        # tohost/fromhost (NOBITS) or headers mapped there
            iss.soc.load_bytes(addr, bytes(data) + bytes(memsz - len(data)))
        return e
    addr = iss.P.ram["base"]
    with open(path) as fh:
        for tok in fh.read().split():
            if tok.startswith("@"):
                addr = int(tok[1:], 16) * 4 + iss.P.ram["base"]
                continue
            w = int(tok, 16)
            iss.soc.load_bytes(addr, w.to_bytes(4, "little"))
            addr += 4
    return None


def run(iss, max_steps, trace_fh=None, tohost=True):
    """Standalone run until tohost != 0 or max_steps. Returns (steps, reason)."""
    n = 0
    soc = iss.soc
    while n < max_steps:
        rec = iss.step()
        n += 1
        if trace_fh is not None:
            trace_fh.write(fmt(rec) + "\n")
        if tohost and soc.tohost:
            return n, "tohost"
    return n, "max_steps"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="nexys_rv32 golden ISS")
    ap.add_argument("program", help="ELF or hex file")
    ap.add_argument("--trace", help="write trace file")
    ap.add_argument("--max", type=int, default=20000000, help="max steps")
    ap.add_argument("--start", help="start address (default: ELF entry or reset vector)")
    ap.add_argument("--core", default="pipe", choices=["pipe", "mc"])
    ap.add_argument("--switches", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--uart-in", default="", help="bytes queued on UART RX")
    a = ap.parse_args()
    P = params_mod.load()
    iss = Iss(P, pipelined=(a.core == "pipe"))
    e = load_program(iss, a.program)
    if a.start:
        iss.pc = int(a.start, 0)
    elif e is not None:
        iss.pc = e.entry
    iss.soc.switches = a.switches
    iss.soc.uart.rx = list(a.uart_in.encode())
    iss.soc.uart.on_tx = lambda b: (sys.stdout.write(chr(b)), sys.stdout.flush())
    fh = open(a.trace, "w") if a.trace else None
    n, why = run(iss, a.max, fh)
    if fh:
        fh.close()
    th = iss.soc.tohost
    sys.stderr.write("\n[iss] %d steps, stop=%s, tohost=0x%08x, minstret=%d\n" % (n, why, th, iss.minstret))
    sys.exit(0 if th == 1 else 1)


if __name__ == "__main__":
    main()
