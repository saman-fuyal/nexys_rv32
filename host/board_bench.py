#!/usr/bin/env python3
# =============================================================================
# board_bench.py - board-day checks and measurements, one command
# -----------------------------------------------------------------------------
# Purpose : After the FPGA is programmed, load each program over the UART
#           bootloader, capture its output, check it, and write the numbers to
#           results/board_<core>_<name>.json (collect_results.py picks them up;
#           run it once per core to fill both columns of the results).
# Steps   : hello        UART text, core type, clock
#           timer_irq    1000 timer interrupts at 1 kHz (about 1 s)
#           dhrystone    1,000,000 runs (about 20 s at 0.5 DMIPS/MHz)
#           coremark     ITERATIONS chosen for >= 10 s (CoreMark run rule)
#           Each program is rebuilt here with its board-length parameters
#           (sw/build.py -D ...) into sw/build_board/. Without a RISC-V GCC,
#           or with --prebuilt, the ready-made sw/prebuilt/<name>_board.elf
#           files are used instead (tools/make_prebuilt.py makes them).
#           Between programs press CPU_RESET on the board when asked: the
#           programs end by stopping, and reset returns to the bootloader.
# Usage   : py host/board_bench.py --port auto [--only coremark] [--prebuilt]
# =============================================================================
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import rvload  # noqa: E402

PROGRAMS = [
    ("hello", [], ["Hello from nexys_rv32!", "clock     : "], 10),
    ("timer_irq", ["TICKS=1000"], ["ticks=1000 (expected 1000)"], 15),
    ("dhrystone", ["NUMBER_OF_RUNS=1000000"], ["DHRY_STATS", "Dhrystones per Second"], 120),
    ("coremark", ["ITERATIONS=1500"], ["CM_STATS", "Correct operation validated."], 120),
]


def build(name, defs, prebuilt=False):
    pre = os.path.join(ROOT, "sw", "prebuilt", name + "_board.elf")
    if prebuilt or not shutil.which(rvload.CFG.get("cross_prefix", "riscv-none-elf-") + "gcc"):
        if not os.path.exists(pre):
            raise SystemExit("no compiler and no %s" % pre)
        print("using prebuilt %s" % os.path.relpath(pre, ROOT))
        return pre
    out = os.path.join(ROOT, "sw", "build_board")
    cmd = [sys.executable, os.path.join(ROOT, "sw", "build.py"), name, "--out", out, "--no-bootrom"]
    for d in defs:
        cmd += ["-D", d]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode:
        raise SystemExit(r.stdout)
    return os.path.join(out, name, name + ".elf")


def capture(port, until, timeout):
    text = ""
    end = time.time() + timeout
    while time.time() < end:
        b = port.read_any()
        if b:
            s = b.decode("latin-1")
            sys.stdout.write(s)
            sys.stdout.flush()
            text += s
            if all(u in text for u in until) and text.endswith(("\n", "\r")):
                time.sleep(0.5)
                text += port.read_any().decode("latin-1")
                return text, True
    return text, False


def parse(name, text):
    d = {}
    m = re.search(r"DHRY_STATS runs=(\d+) cycles=(\d+) instret=(\d+)", text)
    if m:
        runs, cyc, ins = map(int, m.groups())
        d.update(runs=runs, cycles=cyc, instret=ins, dmips_mhz=round(1e6 * runs / (cyc * 1757.0), 3),
                 cpi=round(cyc / float(ins), 3))
    m = re.search(r"Dhrystones per Second:\s+(\d+)", text)
    if m:
        d["dhrystones_per_second_per_mhz_reported"] = int(m.group(1))
    m = re.search(r"CM_STATS iterations=(\d+) cycles=(\d+) instret=(\d+)", text)
    if m:
        it, cyc, ins = map(int, m.groups())
        d.update(iterations=it, cycles_low32=cyc, instret_low32=ins)
    m = re.search(r"Total ticks\s+:\s+(\d+)", text)
    if m:
        d["total_ticks_us"] = int(m.group(1))
        if "iterations" in d:
            d["coremark_per_mhz"] = round(d["iterations"] / (d["total_ticks_us"] / 1e6)
                                          / (rvload.CFG["cpu_hz"] / 1e6), 3)
            d["seconds"] = round(d["total_ticks_us"] / 1e6, 2)
            d["valid_run_length"] = d["seconds"] >= 10
    d["validated"] = "Correct operation validated." in text if name == "coremark" else None
    m = re.search(r"clock\s+:\s+(\d+) Hz", text)
    if m:
        d["clock_hz"] = int(m.group(1))
    m = re.search(r"core\s+:\s+(.+)", text)
    if m:
        d["core"] = m.group(1).strip()
    return d


def default_core():
    return json.load(open(os.path.join(ROOT, "params.json")))["core"]["default_core"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="COMn, /dev/ttyUSBn, 'auto' (search) or 'sim' (dry run)")
    ap.add_argument("--only")
    ap.add_argument("--prebuilt", action="store_true", help="use sw/prebuilt even if GCC is installed")
    ap.add_argument("--core", choices=["pipe", "mc"], default=None,
                    help="core in the bitstream (default: what hello reports, else params.json default_core)")
    a = ap.parse_args()
    core = a.core
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    allok = True
    for name, defs, until, timeout in PROGRAMS:
        if a.only and a.only != name:
            continue
        elf = build(name, defs, a.prebuilt)
        if a.port != "sim":
            input("\n=== %s: press CPU_RESET on the board (SW15 down), then Enter ... " % name)
        port = rvload.open_port(a.port, rvload.CFG["baud"])
        if a.port == "auto":
            a.port = port.s.port            # found it once; reuse the name
        ver, base, size, limit = rvload.ping(port)
        entry, segs = rvload.ram_image(elf, base, limit)
        rvload.load(port, entry, segs, verify=True)
        t0 = time.time()
        text, ok = capture(port, until, timeout)
        if hasattr(port, "s"):
            port.s.close()                  # Windows refuses a second open of a port that is still open
        d = parse(name, text)
        if d.get("core"):
            seen = "mc" if d["core"].startswith("multi") else "pipe"
            if core and core != seen:
                raise SystemExit("the board runs the %s core, but --core %s was given" % (seen, core))
            core = seen
        if core is None:
            core = default_core()
        d.update(core_tag=core, ok=ok, wall_seconds=round(time.time() - t0, 1), port=a.port,
                 date=time.strftime("%Y-%m-%d %H:%M"), defines=defs)
        json.dump(d, open(os.path.join(ROOT, "results", "board_%s_%s.json" % (core, name)), "w"), indent=1)
        open(os.path.join(ROOT, "results", "board_%s_%s.log" % (core, name)), "w").write(text)
        print("\n--- %s: %s %s" % (name, "OK" if ok else "FAILED", json.dumps(d)))
        allok &= ok
    print("\nboard_bench: %s. Next: py tools/collect_results.py" % ("ALL OK" if allok else "SOME FAILED"))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
