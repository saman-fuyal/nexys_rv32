#!/usr/bin/env python3
# =============================================================================
# run_unit.py - build and run the block-level unit testbenches
# -----------------------------------------------------------------------------
# Purpose : One command for all sim/unit/tb_*.v. Generates the golden vectors
#           (gen_vectors.py), then compiles each testbench with its RTL under
#           Icarus Verilog, and also under Vivado xsim when xvlog is on PATH.
# Output  : one line per testbench and simulator:
#             UNIT <name>[@sim] PASS|FAIL <detail>
#           Exit code 1 if any failed.
# =============================================================================
import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "sim", "build", "unit")
VEC = os.path.join(OUT, "vectors")
IS_WIN = os.name == "nt"

R = lambda *p: os.path.join(ROOT, *p)
DEPS = {
    "alu": [R("rtl/core/rv_alu.v")],
    "imm": [R("rtl/core/rv_imm.v")],
    "decode": [R("rtl/core/rv_decode.v")],
    "lsu": [R("rtl/core/rv_lsu_req.v"), R("rtl/core/rv_lsu_load.v")],
    "regfile": [R("rtl/core/rv_regfile.v")],
    "csr": [R("rtl/core/rv_csr.v")],
    "uart": [R("rtl/periph/uart.v"), R("rtl/periph/uart_tx.v"), R("rtl/periph/uart_rx.v"), R("rtl/periph/sync2.v")],
    "timer": [R("rtl/periph/timer.v")],
    "seg7": [R("rtl/periph/seg7.v")],
    "gpio": [R("rtl/periph/gpio.v"), R("rtl/periph/sync2.v"), R("rtl/periph/debounce.v")],
    "bus": [R("rtl/soc/soc_bus.v")],
}
ARGS = {
    "alu": ["+vec=" + os.path.join(VEC, "alu.hex")],
    "imm": ["+vec=" + os.path.join(VEC, "imm.hex")],
    "decode": ["+vec=" + os.path.join(VEC, "dec.hex")],
    "lsu": ["+vreq=" + os.path.join(VEC, "lsu_req.hex"), "+vload=" + os.path.join(VEC, "lsu_load.hex")],
    "bus": ["+vec=" + os.path.join(VEC, "bus.hex")],
}
INC = [R("rtl/core"), R("rtl/gen")]


def which(n):
    for x in (n, n + ".exe", n + ".bat"):
        p = shutil.which(x)
        if p:
            return p
    return None


def sh(cmd, cwd=None):
    if IS_WIN and cmd[0].lower().endswith(".bat"):
        cmd = ["cmd", "/c"] + cmd
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True, errors="replace")
    return r.returncode, r.stdout


def result_line(name, sim, out):
    m = re.search(r"UNIT \S+ (PASS|FAIL) (.*)", out)
    if not m:
        return "UNIT %s@%s FAIL no result line: %s" % (name, sim, out.strip()[-200:].replace("\n", " | ")), False
    return "UNIT %s@%s %s %s" % (name, sim, m.group(1), m.group(2)), m.group(1) == "PASS"


def main():
    os.makedirs(OUT, exist_ok=True)
    rc, out = sh([sys.executable, os.path.join(HERE, "gen_vectors.py")])
    print(out.strip())
    if rc:
        sys.exit(1)
    ok_all = True
    iv, vvp, xvlog, xelab, xsim = which("iverilog"), which("vvp"), which("xvlog"), which("xelab"), which("xsim")
    for tb in sorted(glob.glob(os.path.join(HERE, "tb_*.v"))):
        name = os.path.basename(tb)[3:-2]
        deps = DEPS[name]
        if iv and vvp:
            exe = os.path.join(OUT, name + ".vvp")
            rc, out = sh([iv, "-g2005", "-Wall", "-Wno-timescale", "-o", exe, "-s", "tb_" + name]
                         + ["-I" + i for i in INC] + [tb] + deps)
            if rc or "warning" in out.lower():
                print("UNIT %s@icarus FAIL compile: %s" % (name, out.strip()[-300:].replace("\n", " | ")))
                ok_all = False
            else:
                rc, out = sh([vvp, "-n", exe] + ARGS.get(name, []), cwd=OUT)
                line, ok = result_line(name, "icarus", out)
                print(line)
                ok_all &= ok
        if xvlog and xelab and xsim:
            wd = os.path.join(OUT, "xsim_" + name)
            os.makedirs(wd, exist_ok=True)
            inc = []
            for i in INC:
                inc += ["-i", i]
            rc, out = sh([xvlog] + inc + [tb] + deps, cwd=wd)
            if rc == 0:
                rc, out = sh([xelab, "-debug", "off", "-s", "tb", "work.tb_" + name], cwd=wd)
            if rc:
                print("UNIT %s@xsim FAIL compile: %s" % (name, out.strip()[-300:].replace("\n", " | ")))
                ok_all = False
                continue
            cmd = [xsim, "tb", "-R"]
            for a in ARGS.get(name, []):
                cmd += ["-testplusarg", a.lstrip("+")]
            rc, out = sh(cmd, cwd=wd)
            line, ok = result_line(name, "xsim", out)
            print(line)
            ok_all &= ok
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
