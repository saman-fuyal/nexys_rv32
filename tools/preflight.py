#!/usr/bin/env python3
# =============================================================================
# preflight.py - check the home PC before board day
# -----------------------------------------------------------------------------
# Purpose : One command that says whether everything board day needs is in
#           place, and how to fix what is not. It changes nothing.
# Checks  : project path (no spaces), Python version, Python packages, RISC-V
#           GCC (xPack), Icarus Verilog 12 (C:\iverilog), Yosys and Verilator
#           (only in WSL; not needed on Windows), Vivado 2018.2, the
#           Windows version (Vivado 2018.2 support), prebuilt programs,
#           bitstreams, and the serial ports of a connected board.
# Usage   : py tools\preflight.py          (or preflight.bat)
# Output  : one line per check: OK, WARN (works, but read the note) or MISSING
#           (needed); exit code 0 if nothing is MISSING.
# =============================================================================
import os
import platform
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RESULTS = []


def report(state, what, detail="", fix=""):
    RESULTS.append(state)
    print("%-7s %-34s %s" % (state, what, detail))
    if fix and state != "OK":
        for line in fix.splitlines():
            print("        -> " + line)


def run(cmd):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           timeout=60, shell=isinstance(cmd, str))
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def check_path():
    if " " in ROOT:
        report("MISSING", "project path without spaces", ROOT,
               "Move the folder, for example to C:\\nexys_rv32 (Vivado 2018.2 breaks on spaces).")
    elif len(ROOT) > 120:
        report("WARN", "project path length", "%d characters" % len(ROOT),
               "A shorter path such as C:\\nexys_rv32 avoids Windows path-length limits in builds.")
    else:
        report("OK", "project path", ROOT)


def check_python():
    v = sys.version_info
    ok = v >= (3, 10)
    report("OK" if ok else "MISSING", "Python 3.10 or newer", platform.python_version(),
           "Install Python from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH').")
    for mod, pip, why in (("serial", "pyserial", "talking to the board"),
                          ("matplotlib", "matplotlib", "redrawing the figures")):
        try:
            __import__(mod)
            report("OK", "Python package " + pip, why)
        except ImportError:
            report("MISSING", "Python package " + pip, "needed for " + why,
                   "py -m pip install " + pip)


def check_tool(exe, what, fix, version_args=("--version",), pattern=None, need=True):
    p = shutil.which(exe)
    if not p:
        report("MISSING" if need else "WARN", what, "not on PATH", fix)
        return None
    rc, out = run([p] + list(version_args))
    first = out.strip().splitlines()[0] if out.strip() else ""
    if pattern and not re.search(pattern, out):
        report("WARN", what, first[:70], fix)
    else:
        report("OK", what, first[:70])
    return p


ICARUS_DIR = r"C:\iverilog\bin"


def check_icarus():
    """Icarus Verilog 12 from C:\\iverilog (run_sim.bat and preflight.bat add it to PATH)."""
    if not shutil.which("iverilog") and os.path.exists(os.path.join(ICARUS_DIR, "iverilog.exe")):
        os.environ["PATH"] = ICARUS_DIR + os.pathsep + os.environ.get("PATH", "")
    p = check_tool("iverilog", "Icarus Verilog 12 or newer",
                   "Install Icarus Verilog to C:\\iverilog (https://bleyer.org/icarus/), or add its bin\n"
                   "folder to PATH. run_sim.bat finds C:\\iverilog\\bin by itself.",
                   ("-V",), pattern=r"version 1[2-9]", need=False)
    if p:
        check_tool("vvp", "Icarus runtime (vvp)", "vvp.exe comes with Icarus; same bin folder.", ("-V",),
                   need=False)


def check_vivado():
    vdir = os.environ.get("VIVADO_DIR", r"C:\Xilinx\Vivado\2018.2")
    settings = os.path.join(vdir, "settings64.bat")
    if os.path.exists(settings):
        report("OK", "Vivado 2018.2", vdir)
    elif shutil.which("vivado"):
        report("WARN", "Vivado", "found on PATH but not at %s" % vdir,
               "set VIVADO_DIR to your Vivado 2018.2 folder before fpga\\build.bat")
    else:
        report("MISSING", "Vivado 2018.2", "not found at %s" % vdir,
               "Install Vivado 2018.2 (WebPACK covers the XC7A50T), or set VIVADO_DIR=<folder>.")
    drv = os.path.join(vdir, "data", "xicom", "cable_drivers", "nt64", "install_drivers_wrapper.bat")
    if os.name == "nt" and os.path.exists(vdir):
        report("OK" if os.path.exists(drv) else "WARN", "JTAG cable driver installer",
               drv if os.path.exists(drv) else "not found",
               "If Vivado cannot see the board, run the cable driver installer as Administrator.")


def check_windows():
    if os.name != "nt":
        report("OK", "operating system", platform.platform())
        return
    ver = platform.version()          # e.g. 10.0.22631
    build = int(ver.split(".")[-1]) if ver.split(".")[-1].isdigit() else 0
    if build >= 22000:
        report("WARN", "Windows version", "Windows 11 (build %d)" % build,
               "Vivado 2018.2 officially supports Windows 10 1709/1803 only. It often works on 11;\n"
               "if the installer or a build fails, see 'If Vivado 2018.2 fails' in docs/BRINGUP.md.")
    else:
        report("OK", "Windows version", "Windows 10 (build %d)" % build)


def check_files():
    pre = os.path.join(ROOT, "sw", "prebuilt")
    need = ["hello.elf", "switches_leds.elf", "seg7_counter.elf", "timer_irq.elf", "dhrystone_board.elf",
            "coremark_board.elf"]
    missing = [f for f in need if not os.path.exists(os.path.join(pre, f))]
    report("OK" if not missing else "WARN", "prebuilt programs (sw/prebuilt)",
           "%d of %d present" % (len(need) - len(missing), len(need)),
           "They ship in the zip; sw\\build.bat builds your own copies with GCC.")
    hil = os.path.join(pre, "hil")
    n_hil = len([f for f in os.listdir(hil) if f.endswith(".elf")]) if os.path.isdir(hil) else 0
    report("OK" if n_hil else "WARN", "self-test programs (sw/prebuilt/hil)", "%d programs" % n_hil,
           "They ship in the zip; py tools\\make_prebuilt.py rebuilds them with GCC.")
    for core in ("pipe", "mc"):
        bit = os.path.join(ROOT, "fpga", "build", core, "nexys_rv32_%s.bit" % core)
        report("OK" if os.path.exists(bit) else "WARN", "bitstream (%s)" % core,
               "built" if os.path.exists(bit) else "not built yet",
               "fpga\\build.bat %s   (about 10 to 20 minutes, needs Vivado)" % core)


def check_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        report("WARN", "serial ports", "pyserial missing, cannot list", "py -m pip install pyserial")
        return
    ports = list(list_ports.comports())
    ftdi = [p for p in ports if p.vid == 0x0403]
    if ftdi:
        names = ", ".join("%s (%s)" % (p.device, p.description) for p in ftdi)
        report("OK", "board USB serial ports", names)
        print("        -> usually one port (COM6 on the laptop this project was set up for); some PCs show")
        print("           two. py host\\rvload.py --port auto ...  finds the right one by itself.")
    else:
        report("WARN", "board USB serial ports", "none (board not connected, off, or driver missing)",
               "Normal before board day. On board day: board on, cable in J6 PROG/UART.")


def main():
    print("nexys_rv32 preflight - %s\n" % ROOT)
    check_path()
    check_windows()
    check_python()
    check_tool("riscv-none-elf-gcc", "RISC-V GCC (xPack 14.2.0-3)",
               "Install xPack riscv-none-elf-gcc 14.2.0-3 (COMMANDS.md). Needed for run_sim.bat;\n"
               "not needed on board day (sw/prebuilt has ready-made programs).", pattern=r"14\.2", need=False)
    check_icarus()
    check_tool("yosys", "Yosys (latch check)",
               "Not needed on Windows: the latch check and Verilator lint run in the WSL full\n"
               "regression (COMMANDS.md) and show N/A in a Windows run.", ("-V",), need=False)
    check_vivado()
    check_files()
    check_ports()
    n_miss, n_warn = RESULTS.count("MISSING"), RESULTS.count("WARN")
    print("\npreflight: %d OK, %d WARN, %d MISSING" % (RESULTS.count("OK"), n_warn, n_miss))
    if n_miss:
        print("Fix the MISSING lines first; the arrows say how.")
    sys.exit(1 if n_miss else 0)


if __name__ == "__main__":
    main()
