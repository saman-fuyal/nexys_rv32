#!/usr/bin/env python3
# =============================================================================
# board_hil.py - on-board self-test: board output vs golden model, byte by byte
# -----------------------------------------------------------------------------
# Purpose : The board-day key result. Loads test programs onto the FPGA through
#           the UART bootloader, captures everything each one prints, and
#           compares it with what the golden ISS (model/iss.py) prints for the
#           same ELF on this PC. One differing byte is a failure.
# Programs: sw/prebuilt/hil/ (tools/make_prebuilt.py):
#             probe.elf         reports the core in the bitstream (pipe / mc)
#             rand_NNNN.elf     random RV32I/Zicsr programs with traps; each
#                               prints all registers and its 2 KB data window
#             rv_*.elf          riscv-tests rv32ui + rv32mi; each prints its
#                               result code (pass = 1; four tests have a
#                               documented expected failure, as in simulation)
#           Every program returns to the bootloader when done, so the whole
#           run needs one CPU_RESET at the start. With --fresh, random
#           programs beyond the prebuilt ones are generated and built here
#           (needs riscv-none-elf-gcc).
#           The same programs were first run on the RTL in the regression
#           (group "hil"), where the UART pin output equals the ISS output.
# Output  : results/board_<core>_hil.json and .log
# Usage   : py host/board_hil.py --port auto [--seeds 100] [--no-rvtests]
#           py host/board_hil.py --port sim --seeds 2      (dry run, software board)
# Time    : about 4 s per random program and 1.5 s per riscv-test at 115200
#           baud: roughly 10 minutes for the default set.
# =============================================================================
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "model"))
import rvload  # noqa: E402
import hil     # noqa: E402

PRE = os.path.join(ROOT, "sw", "prebuilt", "hil")


def capture(port, timeout):
    """Bytes the program prints, until its end marker or the timeout."""
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        b = port.read_any()
        if b:
            buf += b
            if hil.complete(buf):
                return buf, True
    return buf, False


def run_one(port, elf, timeout):
    ver, base, size, limit = rvload.ping(port)
    entry, segs = rvload.ram_image(elf, base, limit)
    rvload.load(port, entry, segs, verify=False, log=lambda *a, **k: None)   # CRC-checked per block
    return capture(port, timeout)


def program_list(a):
    rands = sorted(glob.glob(os.path.join(PRE, "rand_*.elf")))[:a.seeds]
    if a.fresh and len(rands) < a.seeds:
        out = os.path.join(ROOT, "sw", "build_board", "hil")
        have = len(rands)
        for seed in range(have + 1, a.seeds + 1):
            print("building random program %d ..." % seed)
            rands.append(hil.build_rand(seed, out))
    elif len(rands) < a.seeds:
        print("note: only %d prebuilt random programs; use --fresh to build more" % len(rands))
    rvs = [] if a.no_rvtests else sorted(glob.glob(os.path.join(PRE, "rv_*.elf")))
    return rands + rvs


def main():
    ap = argparse.ArgumentParser(description="nexys_rv32 on-board self-test against the golden model")
    ap.add_argument("--port", required=True, help="COMn, 'auto' (search) or 'sim' (software board)")
    ap.add_argument("--seeds", type=int, default=100, help="number of random programs (default 100)")
    ap.add_argument("--no-rvtests", action="store_true", help="skip the riscv-tests")
    ap.add_argument("--fresh", action="store_true", help="build random programs beyond the prebuilt ones")
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds per program")
    ap.add_argument("--results", default=os.path.join(ROOT, "results"), help=argparse.SUPPRESS)
    a = ap.parse_args()

    progs = program_list(a)
    if not progs:
        raise SystemExit("no programs in %s (unzip complete? py tools/make_prebuilt.py)" % PRE)
    if a.port != "sim":
        input("Press CPU_RESET on the board (SW15 down), then Enter ... ")
    port = rvload.open_port(a.port, rvload.CFG["baud"])

    # which core is in the bitstream
    txt, ok = run_one(port, os.path.join(PRE, "probe.elf"), 10) if os.path.exists(os.path.join(PRE, "probe.elf")) \
        else (b"", False)
    core = "mc" if b"CORE mc" in txt else ("pipe" if b"CORE pipe" in txt else None)
    if core is None:
        raise SystemExit("the probe program did not report the core (got %r)" % txt[:60])
    print("core in the bitstream: %s; %d programs to run" % (core, len(progs)))

    log, res = [], dict(core=core, programs=0, passed=0, failed=0, instructions=0, bytes_compared=0,
                        failures=[], port=a.port, date=time.strftime("%Y-%m-%d %H:%M"))
    t0 = time.time()
    for k, elf in enumerate(progs, 1):
        name = os.path.basename(elf)[:-4]
        exp, n = hil.expected_output(elf)
        got, done = run_one(port, elf, a.timeout)
        ok, msg = hil.compare(got, exp)
        if not done and ok:
            ok, msg = False, "incomplete output (timeout)"
        res["programs"] += 1
        res["passed" if ok else "failed"] += 1
        res["instructions"] += n
        res["bytes_compared"] += len(exp)
        if not ok:
            res["failures"].append(dict(program=name, detail=msg))
        line = "%-4s %-28s %7d instructions  %s" % ("PASS" if ok else "FAIL", name, n, msg)
        print("[%3d/%d] %s" % (k, len(progs), line))
        log.append(line)
    res["seconds"] = round(time.time() - t0, 1)
    res["random_programs"] = sum(1 for p in progs if os.path.basename(p).startswith("rand_"))
    res["riscv_tests"] = sum(1 for p in progs if os.path.basename(p).startswith("rv_"))
    tag = "sim" if a.port == "sim" else core
    os.makedirs(a.results, exist_ok=True)
    out = os.path.join(a.results, "board_%s_hil.json" % tag)
    if a.port != "sim":
        json.dump(res, open(out, "w"), indent=1)
        open(out[:-5] + ".log", "w").write("\n".join(log) + "\n")
    print("\nboard_hil (%s core): %d of %d programs identical to the model, %d instructions, %d bytes compared, "
          "%.0f s%s" % (core, res["passed"], res["programs"], res["instructions"], res["bytes_compared"],
                        res["seconds"], "" if a.port == "sim" else "; saved " + os.path.relpath(out, ROOT)))
    sys.exit(0 if res["failed"] == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except rvload.ProtocolError as e:
        sys.exit("board_hil: " + str(e))
