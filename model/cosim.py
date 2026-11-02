#!/usr/bin/env python3
# =============================================================================
# cosim.py - check an RTL retirement trace against the golden ISS
# -----------------------------------------------------------------------------
# Purpose : Step the ISS once per RTL trace record and compare every field.
#           This is the lockstep check: the first differing record is a bug.
# Rules   : - 'R' records must match exactly (pc, insn, rd, rd value, memory
#             address/strobe/data), except the rd value of reads that depend on
#             timing (mcycle, mcycleh, mip, timer mtime, UART/GPIO inputs),
#             which the ISS takes from the RTL record. The address and size of
#             those reads are still checked.
#           - 'T' records for exceptions must be produced by the ISS itself.
#           - 'T' records for interrupts are injected at the RTL point; the ISS
#             checks the interrupt was enabled and that mepc is its own pc.
# Usage   : py model/cosim.py <program.elf|hex> <rtl_trace.txt> [--start ADDR]
# Exit    : 0 = traces match, 1 = mismatch (details printed)
# =============================================================================
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iss as iss_mod     # noqa: E402
import params as params_mod  # noqa: E402


def compare(iss, rtl_lines, context=8):
    """Returns (ok, n_records, message)."""
    hist = collections.deque(maxlen=context)
    n = 0
    for lineno, line in enumerate(rtl_lines, 1):
        rec = iss_mod.parse(line)
        if rec is None:
            continue
        n += 1
        if rec[0] == "T" and rec[1] >> 31:
            # interrupt: RTL decides when; the ISS checks it was legal
            if not (iss.mstatus & iss_mod.MSTATUS_MIE and iss.mie & iss_mod.MIP_MTIP):
                return False, n, _msg(lineno, line, "interrupt taken while disabled", hist)
            if rec[2] != iss.pc:
                return False, n, _msg(lineno, line, "interrupt mepc %08x, ISS pc %08x" % (rec[2], iss.pc), hist)
            got = iss.take_trap(rec[1], rec[3], iss.pc)
        else:
            iss.follow = rec if rec[0] == "R" else ("R", 0, 0, 0, 0, "-")
            got = iss.step()
        exp_line = iss_mod.fmt(got)
        rtl_line = iss_mod.fmt(rec)
        if exp_line != rtl_line:
            return False, n, _msg(lineno, rtl_line, "ISS expected: " + exp_line, hist)
        hist.append(rtl_line)
    return True, n, "match"


def _msg(lineno, line, why, hist):
    out = ["MISMATCH at trace line %d" % lineno, "  RTL: " + line.strip(), "  " + why,
           "  previous records:"]
    out += ["    " + h for h in hist]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("program")
    ap.add_argument("trace")
    ap.add_argument("--start", help="start pc (default ELF entry / RAM base)")
    ap.add_argument("--core", default="pipe", choices=["pipe", "mc"])
    ap.add_argument("--boot", help="boot ROM ELF loaded into the ISS (same image as rtl/gen/bootrom.v)")
    ap.add_argument("--ram-size", type=lambda s: int(s, 0), help="override RAM size (arch-test config)")
    ap.add_argument("--no-load", action="store_true",
                    help="do not preload the program (it arrives over the UART bootloader)")
    a = ap.parse_args()
    P = params_mod.load(overrides={"memory.ram.size": a.ram_size} if a.ram_size else None)
    iss = iss_mod.Iss(P, pipelined=(a.core == "pipe"))
    if a.boot:
        if not os.path.exists(a.boot):
            sys.exit("cosim: boot ROM ELF %s not found (build it: py sw/build.py boot)" % a.boot)
        iss_mod.load_program(iss, a.boot)
    e = None if a.no_load else iss_mod.load_program(iss, a.program)
    if a.start:
        iss.pc = int(a.start, 0)
    elif e is not None:
        iss.pc = e.entry
    else:
        iss.pc = P.ram["base"]
    with open(a.trace) as fh:
        ok, n, msg = compare(iss, fh)
    print("cosim: %d records, %s" % (n, msg))
    sys.exit(0 if ok and n > 0 else 1)


if __name__ == "__main__":
    main()
