#!/usr/bin/env python3
# =============================================================================
# test_host.py - test the board-day host tools through a real serial port
# -----------------------------------------------------------------------------
# Purpose : Run host/rvload.py and host/board_bench.py exactly as on board day,
#           through pyserial and an operating-system serial device, with the
#           software board (model/board_model.py --pty: the golden ISS running
#           the real boot ROM image) at the other end of a pseudo-terminal.
# Checks  : 1. rvload loads sw/prebuilt/hello.elf, verifies it and sees
#              "Hello from nexys_rv32!"
#           2. --port auto finds the board among several ports (a missing
#              port, a silent port, the board) and skips the others
#           3. board_bench --only hello --prebuilt writes results/board_hello
#              with the core type (into a temporary results folder)
#           4. board_hil runs the probe and two random self-test programs,
#              chained through the bootloader, and finds them identical
# Needs   : Linux or WSL (pseudo-terminals) and pyserial. On Windows the
#           script prints SKIPPED: the same code is exercised on board day.
# Usage   : py tools/test_host.py
# =============================================================================
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HELLO = os.path.join(ROOT, "sw", "prebuilt", "hello.elf")


def start_board():
    p = subprocess.Popen([sys.executable, "-u", os.path.join(ROOT, "model", "board_model.py"), "--pty"],
                         stdout=subprocess.PIPE, universal_newlines=True)
    dev = p.stdout.readline().strip()
    if not dev.startswith("/dev/"):
        p.kill()
        raise SystemExit("board model did not open a pseudo-terminal: %r" % dev)
    return p, dev


def main():
    if os.name == "nt":
        print("host tools: SKIPPED on Windows (needs pseudo-terminals); board day exercises them")
        return 0
    try:
        import serial  # noqa: F401
    except ImportError:
        print("host tools: SKIPPED (pyserial missing: pip install pyserial)")
        return 0
    if not os.path.exists(HELLO):
        print("host tools: FAIL (sw/prebuilt/hello.elf missing: py tools/make_prebuilt.py)")
        return 1
    ok = True
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [os.environ.get("PYTHONPATH")] + sys.path)))

    # 1. plain load over the serial device
    board, dev = start_board()
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "host", "rvload.py"), HELLO, "--port", dev,
                            "--expect", "Hello from nexys_rv32!", "--timeout", "60"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=env,
                           timeout=300)
        good = r.returncode == 0 and "verify ok" in r.stdout
        print("rvload over %s: %s" % (dev, "PASS" if good else "FAIL\n" + r.stdout[-1500:]))
        ok &= good
    finally:
        board.kill()

    # 2. --port auto among a missing port, a silent port and the board
    board, dev = start_board()
    import pty
    silent_master, silent_slave = pty.openpty()
    silent = os.ttyname(silent_slave)
    try:
        code = r"""
import sys
sys.path.insert(0, %r)
import rvload
from serial.tools import list_ports
class P(object):
    def __init__(s, d, vid): s.device, s.vid, s.description = d, vid, "test"
list_ports.comports = lambda: [P("/dev/does-not-exist", 0x0403), P(%r, 0x0403), P(%r, 0x0403)]
print("FOUND", rvload.find_port(rvload.CFG["baud"]))
""" % (os.path.join(ROOT, "host"), silent, dev)
        r = subprocess.run([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, env=env, timeout=120)
        good = ("FOUND " + dev) in r.stdout
        print("--port auto picks the board out of 3 ports: %s" % ("PASS" if good else "FAIL\n" + r.stdout[-1500:]))
        ok &= good
    finally:
        board.kill()
        os.close(silent_master)
        os.close(silent_slave)

    # 3. board_bench, hello only, prebuilt, results into a scratch copy
    board, dev = start_board()
    tmp = tempfile.mkdtemp(prefix="nrv_host_")
    try:
        shutil.copytree(os.path.join(ROOT, "host"), os.path.join(tmp, "host"))
        shutil.copytree(os.path.join(ROOT, "model"), os.path.join(tmp, "model"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(ROOT, "sw", "prebuilt"), os.path.join(tmp, "sw", "prebuilt"))
        shutil.copy(os.path.join(ROOT, "params.json"), tmp)
        os.makedirs(os.path.join(tmp, "sw", "build", "boot"))
        shutil.copy(os.path.join(ROOT, "sw", "build", "boot", "boot.elf"), os.path.join(tmp, "sw", "build", "boot"))
        r = subprocess.run([sys.executable, os.path.join(tmp, "host", "board_bench.py"), "--port", dev, "--only",
                            "hello", "--prebuilt"], input="\n", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, env=env, timeout=300)
        res = os.path.join(tmp, "results", "board_pipe_hello.json")
        d = json.load(open(res)) if os.path.exists(res) else {}
        good = r.returncode == 0 and d.get("ok") and d.get("core") in ("5-stage pipeline", "multi-cycle")
        print("board_bench --only hello --prebuilt: %s" % ("PASS (core: %s)" % d.get("core") if good
                                                          else "FAIL\n" + r.stdout[-1500:]))
        ok &= bool(good)
    finally:
        board.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    # 4. board_hil over the serial device: probe, two random programs, chained through the bootloader
    board, dev = start_board()
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "host", "board_hil.py"), "--port", dev, "--seeds", "2",
                            "--no-rvtests", "--timeout", "120", "--results", tempfile.mkdtemp(prefix="nrv_hil_")], input="\n", stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True, env=env, timeout=900)
        good = r.returncode == 0 and "2 of 2 programs identical" in r.stdout
        print("board_hil over %s (2 programs, chained): %s" % (dev, "PASS" if good else "FAIL\n" + r.stdout[-1500:]))
        ok &= good
    finally:
        board.kill()
    print("host tools: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
