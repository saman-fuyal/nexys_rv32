#!/usr/bin/env python3
# =============================================================================
# coverage_report.py - RTL code coverage and functional coverage summary
# -----------------------------------------------------------------------------
# Purpose : Turn the data of a coverage regression into one table.
#   Code coverage  : Verilator line and toggle coverage, merged over every
#                    test run with  py sim/run_sim.py --coverage  (Verilator
#                    builds with --coverage-line --coverage-toggle).
#   Functional     : counted from the retirement traces of the same runs:
#                    every RV32I/Zicsr/Zifencei mnemonic executed, every trap
#                    cause taken, and the pipeline events (stall, flush,
#                    MEM->EX and WB->EX forwarding, interrupt) from the
#                    testbench counters.
# Output  : results/coverage.json and results/coverage.md
# =============================================================================
import collections
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RUNS = os.path.join(ROOT, "sim", "build", "runs", "verilator")
OUT = os.path.join(ROOT, "results")

MNEMONICS = ["lui", "auipc", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu", "lb", "lh", "lw",
             "lbu", "lhu", "sb", "sh", "sw", "addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli",
             "srai", "add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and", "fence",
             "fence.i", "ecall", "ebreak", "mret", "wfi", "csrrw", "csrrs", "csrrc", "csrrwi", "csrrsi",
             "csrrci"]
CAUSES = {0x0: "instruction address misaligned", 0x1: "instruction access fault", 0x2: "illegal instruction",
          0x3: "breakpoint", 0x4: "load address misaligned", 0x5: "load access fault",
          0x6: "store address misaligned", 0x7: "store access fault", 0xB: "ecall from M-mode",
          0x80000007: "machine timer interrupt"}


def mnemonic(insn):
    op, f3, f7 = insn & 0x7F, (insn >> 12) & 7, insn >> 25
    if op == 0x37: return "lui"
    if op == 0x17: return "auipc"
    if op == 0x6F: return "jal"
    if op == 0x67: return "jalr"
    if op == 0x63: return {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}.get(f3)
    if op == 0x03: return {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}.get(f3)
    if op == 0x23: return {0: "sb", 1: "sh", 2: "sw"}.get(f3)
    if op == 0x13:
        if f3 == 5: return "srai" if f7 == 0x20 else "srli"
        return {0: "addi", 2: "slti", 3: "sltiu", 4: "xori", 6: "ori", 7: "andi", 1: "slli"}[f3]
    if op == 0x33:
        if f7 == 0x20: return {0: "sub", 5: "sra"}.get(f3)
        return {0: "add", 1: "sll", 2: "slt", 3: "sltu", 4: "xor", 5: "srl", 6: "or", 7: "and"}[f3]
    if op == 0x0F: return "fence.i" if f3 == 1 else "fence"
    if op == 0x73:
        if f3 == 0:
            return {0x00000073: "ecall", 0x00100073: "ebreak", 0x30200073: "mret", 0x10500073: "wfi"}.get(insn)
        return {1: "csrrw", 2: "csrrs", 3: "csrrc", 5: "csrrwi", 6: "csrrsi", 7: "csrrci"}.get(f3)
    return None


def functional():
    per_core = {}
    for core in ("pipe", "mc"):
        mn = collections.Counter()
        tr = collections.Counter()
        ev = collections.Counter()
        for log in glob.glob(os.path.join(RUNS, core, "*", "*", "sim.log")):
            m = re.search(r"TB_RESULT (.*)", open(log, errors="replace").read())
            if m:
                for kv in m.group(1).split():
                    k, _, v = kv.partition("=")
                    if k.startswith("ev_"):
                        ev[k[3:]] += int(v)
        for t in glob.glob(os.path.join(RUNS, core, "*", "*", "trace.txt")):
            with open(t) as fh:
                for line in fh:
                    if line[0] == "R":
                        n = mnemonic(int(line[11:19], 16))
                        if n:
                            mn[n] += 1
                    elif line[0] == "T":
                        tr[int(line[2:10], 16)] += 1
        per_core[core] = dict(mnemonics={k: mn.get(k, 0) for k in MNEMONICS},
                              traps={CAUSES[k]: tr.get(k, 0) for k in CAUSES},
                              events=dict(ev))
    return per_core


def code_coverage():
    vc = shutil.which("verilator_coverage")
    dats = glob.glob(os.path.join(RUNS, "*", "*", "*", "coverage.dat"))
    if not vc or not dats:
        return None
    merged = os.path.join(ROOT, "sim", "build", "coverage_merged.dat")
    info = os.path.join(ROOT, "sim", "build", "coverage_merged.info")
    subprocess.run([vc, "--write", merged] + dats, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    subprocess.run([vc, "--write-info", info, merged], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    files = {}
    if os.path.exists(info):
        cur = None
        for line in open(info):
            if line.startswith("SF:"):
                cur = os.path.relpath(line[3:].strip(), ROOT).replace("\\", "/")
                files[cur] = dict(lines=0, hit=0)
            elif line.startswith("DA:") and cur:
                n = int(line.strip().split(",")[1])
                files[cur]["lines"] += 1
                files[cur]["hit"] += n > 0
    toggles = collections.defaultdict(lambda: [0, 0])
    for line in open(merged, errors="replace"):
        if not line.startswith("C '"):
            continue
        body, cnt = line.rsplit("'", 1)
        if "\x01page\x02v_toggle" not in body:
            continue
        m = re.search(r"\x01f\x02([^\x01]+)", body)
        if not m:
            continue
        f = os.path.relpath(m.group(1), ROOT).replace("\\", "/")
        toggles[f][0] += 1
        toggles[f][1] += int(cnt.strip()) > 0
    rows = []
    for f in sorted(set(files) | set(toggles)):
        if not f.startswith("rtl/"):
            continue
        l = files.get(f, dict(lines=0, hit=0))
        t = toggles.get(f, [0, 0])
        rows.append(dict(file=f, lines=l["lines"], lines_hit=l["hit"], toggles=t[0], toggles_hit=t[1]))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    fc = functional()
    cc = code_coverage()
    json.dump(dict(functional=fc, code=cc), open(os.path.join(OUT, "coverage.json"), "w"), indent=1)
    md = ["# Coverage", "", "Generated by `tools/coverage_report.py` from the Verilator coverage regression. Do not edit.", ""]
    if cc:
        tl = sum(r["lines"] for r in cc); th = sum(r["lines_hit"] for r in cc)
        gl = sum(r["toggles"] for r in cc); gh = sum(r["toggles_hit"] for r in cc)
        md += ["## Code coverage (Verilator)", "", "| File | Lines hit | Toggle points hit |", "|---|---|---|"]
        for r in cc:
            md.append("| %s | %d / %d (%.1f %%) | %d / %d (%.1f %%) |" % (
                r["file"], r["lines_hit"], r["lines"], 100.0 * r["lines_hit"] / max(1, r["lines"]),
                r["toggles_hit"], r["toggles"], 100.0 * r["toggles_hit"] / max(1, r["toggles"])))
        md += ["| **all RTL** | %d / %d (%.1f %%) | %d / %d (%.1f %%) |" % (th, tl, 100.0 * th / max(1, tl),
                                                                       gh, gl, 100.0 * gh / max(1, gl)), ""]
    for core, d in fc.items():
        missing = [k for k, v in d["mnemonics"].items() if v == 0]
        md += ["## Functional coverage, %s core" % core, "",
               "Instructions executed: %d of %d mnemonics%s." % (
                   len(MNEMONICS) - len(missing), len(MNEMONICS),
                   (" (never executed: " + ", ".join(missing) + ")") if missing else ""), "",
               "| Trap cause | Taken |", "|---|---|"]
        for k, v in d["traps"].items():
            md.append("| %s | %d |" % (k, v))
        md += ["", "| Pipeline event | Count |", "|---|---|"]
        for k, v in sorted(d["events"].items()):
            md.append("| %s | %d |" % (k, v))
        md.append("")
    open(os.path.join(OUT, "coverage.md"), "w").write("\n".join(md) + "\n")
    print("coverage: written results/coverage.{json,md}")


if __name__ == "__main__":
    main()
