#!/usr/bin/env python3
# =============================================================================
# params.py - loads params.json and computes every derived constant
# -----------------------------------------------------------------------------
# Purpose : One loader shared by the generators, the golden ISS, the host
#           bootloader tool and the test runner, so a derived number (UART
#           divisor, address decode width, ...) is computed in exactly one
#           place.
# Behavior: load() returns a Params object. Integers given as hex strings in
#           the JSON are converted. Derived values are checked for sanity and
#           a ValueError is raised for an inconsistent memory map.
# =============================================================================
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARAMS_JSON = os.path.join(ROOT, "params.json")


def _int(v):
    return int(v, 0) if isinstance(v, str) else int(v)


def _log2_exact(n, what):
    if n <= 0 or (n & (n - 1)) != 0:
        raise ValueError("%s must be a power of two, got %d" % (what, n))
    return n.bit_length() - 1


class Params(object):
    """Derived view of params.json."""

    def __init__(self, raw):
        self.raw = raw
        p = raw
        self.name = p["project"]["name"]
        self.version = p["project"]["version"]
        self.build_id = _int(p["project"]["build_id"])
        self.part = p["board"]["part"]
        self.osc_hz = _int(p["board"]["osc_hz"])
        self.cpu_hz = _int(p["clock"]["cpu_hz"])
        self.default_core = p["core"]["default_core"]
        self.reset_vector = _int(p["core"]["reset_vector"])
        f = p["core"]["features"]
        self.zicsr = int(f["zicsr"])
        self.timer_irq = int(f["timer_irq"])
        self.zifencei = int(f["zifencei"])
        self.misaligned = f["misaligned"]
        if self.misaligned != "trap":
            raise ValueError("only misaligned='trap' is implemented")
        if self.timer_irq and not self.zicsr:
            raise ValueError("timer_irq needs zicsr")

        # ---- memory map -----------------------------------------------------
        self.regions = {}
        for name, r in p["memory"].items():
            base, size = _int(r["base"]), _int(r["size"])
            aw = _log2_exact(size, name + ".size")
            if base & (size - 1):
                raise ValueError("%s.base must be aligned to its size" % name)
            self.regions[name] = dict(base=base, size=size, aw=aw,
                                      exec=int(r["exec"]), write=int(r["write"]))
        names = sorted(self.regions, key=lambda n: self.regions[n]["base"])
        for a, b in zip(names, names[1:]):
            ra, rb = self.regions[a], self.regions[b]
            if ra["base"] + ra["size"] > rb["base"]:
                raise ValueError("regions %s and %s overlap" % (a, b))
        self.rom = self.regions["bootrom"]
        self.ram = self.regions["ram"]
        self.io = self.regions["io"]
        if not (self.rom["base"] <= self.reset_vector < self.rom["base"] + self.rom["size"]):
            raise ValueError("reset_vector must be inside the boot ROM")

        self.compliance_ram_size = _int(p.get("sim", {}).get("compliance_ram_size", self.ram["size"]))
        self.compliance_ram_aw = _log2_exact(self.compliance_ram_size, "sim.compliance_ram_size")

        # ---- software -------------------------------------------------------
        s = p["software"]
        self.stack_size = _int(s["stack_size"])
        self.march = s["march"]
        self.mabi = s["mabi"]
        self.cross_prefix = s["cross_prefix"]

        # ---- peripherals ----------------------------------------------------
        self.baud = _int(p["uart"]["baud"])
        self.uart_div = int(round(self.cpu_hz / float(self.baud)))
        self.uart_baud_err = (self.cpu_hz / float(self.uart_div) - self.baud) / self.baud
        if abs(self.uart_baud_err) > 0.02:
            raise ValueError("UART baud error %.2f%% exceeds 2%%" % (100 * self.uart_baud_err))
        self.tick_hz = _int(p["timer"]["tick_hz"])
        if self.cpu_hz % self.tick_hz:
            raise ValueError("cpu_hz must be a multiple of timer.tick_hz")
        self.timer_div = self.cpu_hz // self.tick_hz
        self.debounce_ms = _int(p["gpio"]["debounce_ms"])
        self.debounce_cycles = self.cpu_hz // 1000 * self.debounce_ms
        self.seg7_digit_hz = _int(p["seg7"]["digit_hz"])
        self.seg7_div = self.cpu_hz // self.seg7_digit_hz
        refresh_ms = 8 * 1000.0 / self.seg7_digit_hz
        if not (1.0 <= refresh_ms <= 16.0):
            raise ValueError("7-seg full refresh %.1f ms outside 1-16 ms" % refresh_ms)

        self.periph = {}
        for pname, pd in p["peripherals"].items():
            off = _int(pd["offset"])
            regs = []
            for rname, roff, acc, desc in pd["regs"]:
                regs.append(dict(name=rname, off=_int(roff), acc=acc, desc=desc,
                                 addr=self.io["base"] + off + _int(roff)))
            for i, r in enumerate(regs):
                if r["off"] != 4 * i:
                    raise ValueError("%s registers must be dense, 4-byte spaced" % pname)
            self.periph[pname] = dict(offset=off, base=self.io["base"] + off,
                                      regs=regs, nregs=len(regs), index=off >> 8)
            if off & 0xFF or off >= self.io["size"]:
                raise ValueError("%s offset must be a multiple of 0x100 inside io" % pname)

        self.csrs = [dict(name=n, addr=_int(a), acc=acc, desc=d)
                     for n, a, acc, d in p["csr"]["list"]]
        self.misa = 0x40000100
        self.mimpid = 0x00010000

    # FEATURES register value (sysctrl) - depends on the core being simulated
    def features_word(self, pipelined):
        return (self.zicsr << 0) | (self.timer_irq << 1) | (self.zifencei << 2) | \
               ((1 if pipelined else 0) << 3)

    def reg(self, periph, name):
        for r in self.periph[periph]["regs"]:
            if r["name"] == name:
                return r["addr"]
        raise KeyError(periph + "." + name)


def load(path=PARAMS_JSON, overrides=None):
    with open(path) as fh:
        raw = json.load(fh)
    if overrides:
        for dotted, val in overrides.items():
            node = raw
            keys = dotted.split(".")
            for k in keys[:-1]:
                node = node[k]
            node[keys[-1]] = val
    return Params(raw)


if __name__ == "__main__":
    P = load()
    print("UART divisor %d (baud error %+.4f%%)" % (P.uart_div, 100 * P.uart_baud_err))
    print("timer div %d, seg7 div %d, debounce %d cycles" % (P.timer_div, P.seg7_div, P.debounce_cycles))
