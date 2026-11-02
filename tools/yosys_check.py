#!/usr/bin/env python3
# =============================================================================
# yosys_check.py - latch-freedom proof and a synthesis estimate with Yosys
# -----------------------------------------------------------------------------
# Purpose : 1. Prove no latch is inferred anywhere: after 'proc', no $dlatch,
#              $adlatch, $dlatchsr or $sr cell may exist in any module of the
#              SoC (both core variants) or the FPGA top. The check is first
#              shown to work on a deliberately latching file.
#           2. Estimate resources with synth_xilinx (XC7 family) for both cores
#              and for the core alone, so the two microarchitectures can be
#              compared before Vivado runs. These are Yosys estimates; the
#              Vivado numbers come from fpga/scripts on board day.
# Output  : results/yosys_synth.json and a summary on stdout. Exit 1 on any
#           latch or tool failure.
# =============================================================================
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
YOSYS = shutil.which("yosys") or shutil.which("yosys.exe")
WORK = os.path.join(ROOT, "sim", "build", "yosys")
INC = "-I%s -I%s" % (os.path.join(ROOT, "rtl", "core"), os.path.join(ROOT, "rtl", "gen"))
RTL = (sorted(glob.glob(os.path.join(ROOT, "rtl/core/*.v"))) + sorted(glob.glob(os.path.join(ROOT, "rtl/soc/*.v"))) +
       sorted(glob.glob(os.path.join(ROOT, "rtl/periph/*.v"))) + [os.path.join(ROOT, "rtl/gen/bootrom.v")])
LATCH = "t:$dlatch t:$adlatch t:$dlatchsr t:$sr"


def yosys(script, name):
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, name + ".ys")
    with open(path, "w") as fh:
        fh.write(script)
    r = subprocess.run([YOSYS, "-q", "-l", os.path.join(WORK, name + ".log"), "-s", path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    log = open(os.path.join(WORK, name + ".log")).read() if os.path.exists(os.path.join(WORK, name + ".log")) else ""
    return r.returncode, r.stdout + log


def read_all(extra=()):
    files = " ".join(f.replace("\\", "/") for f in list(RTL) + list(extra))
    # fpga_top.v instantiates MMCME2_BASE and BUFG when the clock is not 100 MHz
    lib = "read_verilog -lib +/xilinx/cells_sim.v +/xilinx/cells_xtra.v\n" if extra else ""
    return lib + "read_verilog %s %s\n" % (INC.replace("\\", "/"), files)


def latch_check(top, chparam=""):
    s = read_all([os.path.join(ROOT, "fpga/rtl/fpga_top.v")] if top == "fpga_top" else [])
    s += "hierarchy -check -top %s %s\nproc\nopt_clean\nselect -assert-none %s\n" % (top, chparam, LATCH)
    return yosys(s, "latch_" + top + chparam.replace(" ", "_").replace("-", ""))


def synth(top, chparam=""):
    s = read_all([os.path.join(ROOT, "fpga/rtl/fpga_top.v")] if top == "fpga_top" else [])
    s += "hierarchy -check -top %s %s\nsynth_xilinx -family xc7 -flatten -top %s\nstat\n" % (top, chparam, top)
    rc, out = yosys(s, "synth_" + top + chparam.replace(" ", "_").replace("-", ""))
    cells = {}
    blk = out[out.rfind("Printing statistics"):] if "Printing statistics" in out else out
    for m in re.finditer(r"^\s+(\d+)\s+(\$?[A-Za-z_][\w$]*)\s*$", blk, re.M):
        cells[m.group(2)] = int(m.group(1))
    lut = sum(v for k, v in cells.items() if re.match(r"LUT[1-6]$", k))
    lutram = sum(v for k, v in cells.items() if k.startswith("RAM") and "RAMB" not in k)
    ff = sum(v for k, v in cells.items() if re.match(r"FD[CPRSE]+", k))
    bram36 = cells.get("RAMB36E1", 0)
    bram18 = cells.get("RAMB18E1", 0)
    carry = cells.get("CARRY4", 0)
    dsp = cells.get("DSP48E1", 0)
    return rc, dict(lut=lut, lutram=lutram, ff=ff, ramb36=bram36, ramb18=bram18, carry4=carry, dsp=dsp,
                    raw=cells)


def main():
    if not YOSYS:
        print("yosys not found")
        sys.exit(1)
    ok = True
    # 0. the check must catch a real latch
    bad = os.path.join(ROOT, "tools", "rule_tests", "bad_r2_latch.v")
    rc, out = yosys("read_verilog %s\nhierarchy -top bad_r2_latch\nproc\nselect -assert-none %s\n"
                    % (bad.replace("\\", "/"), LATCH), "latch_selftest")
    caught = rc != 0
    print("latch check self-test on bad_r2_latch.v: %s" % ("latch detected (good)" if caught else "NOT detected"))
    ok &= caught
    # 1. no latch anywhere
    for top, cp in (("rv_soc", "-chparam CORE_PIPE 1"), ("rv_soc", "-chparam CORE_PIPE 0"), ("fpga_top", "")):
        rc, out = latch_check(top, cp)
        print("no-latch proof %s %s: %s" % (top, cp, "PASS" if rc == 0 else "FAIL"))
        if rc:
            print(out[-1500:])
        ok &= rc == 0
    # 2. synthesis estimates
    res = {"tool": "", "note": "Yosys synth_xilinx -family xc7 estimates; Vivado results replace these on board day"}
    vr = subprocess.run([YOSYS, "-V"], stdout=subprocess.PIPE, universal_newlines=True)
    res["tool"] = vr.stdout.strip()
    for label, top, cp in (("soc_pipe", "fpga_top", "-chparam CORE_PIPE 1"),
                           ("soc_mc", "fpga_top", "-chparam CORE_PIPE 0"),
                           ("core_pipe", "rv_core_pipe", ""),
                           ("core_mc", "rv_core_mc", "")):
        rc, d = synth(top, cp)
        res[label] = d
        print("synth %-10s LUT %5d  LUTRAM %3d  FF %5d  RAMB36 %2d  RAMB18 %2d  CARRY4 %4d  DSP %d%s"
              % (label, d["lut"], d["lutram"], d["ff"], d["ramb36"], d["ramb18"], d["carry4"], d["dsp"],
                 "" if rc == 0 else "  (synthesis FAILED)"))
        ok &= rc == 0
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "yosys_synth.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    print("yosys checks: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
