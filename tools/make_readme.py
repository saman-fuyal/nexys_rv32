#!/usr/bin/env python3
# =============================================================================
# make_readme.py - write README.md from params.json and results/summary.json
# -----------------------------------------------------------------------------
# Purpose : Keep the README's status table and memory map in step with the
#           results and the parameter file. Run after collect_results.py:
#               py tools/collect_results.py
#               py tools/make_readme.py
# Output  : README.md (generated; edit this script, not the README)
# =============================================================================
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TBD = "[TBD]"


def load(*p):
    path = os.path.join(ROOT, *p)
    return json.load(open(path)) if os.path.exists(path) else None


def main():
    P = load("params.json")
    S = load("results", "summary.json") or {}
    reg = S.get("regression", TBD)
    bp, bm = S.get("bench_sim", {}).get("pipe", {}), S.get("bench_sim", {}).get("mc", {})
    y = S.get("yosys", TBD)
    viv = S.get("vivado", {})
    mut = S.get("mutation", TBD)
    cov = S.get("coverage", TBD)
    board = S.get("board", TBD)

    def bb(core, prog, k):
        return board.get(core, {}).get(prog, {}).get(k, TBD) if board != TBD else TBD

    def vv(core, k):
        d = viv.get(core, TBD)
        return TBD if d == TBD else d.get(k, TBD)

    if reg != TBD:
        g = reg["groups"]
        reg_line = "%d / %d runs pass, %d failed (%s; %s)" % (reg["passed"], reg["total"], reg["failed"],
                                                               reg["date"], ", ".join(reg["simulators"].values()))
        static = "%d / %d pass" % (g["static"]["passed"], g["static"]["total"])
    else:
        reg_line = static = TBD
    if cov != TBD:
        lines = sum(r["lines"] for r in cov["code"])
        lh = sum(r["lines_hit"] for r in cov["code"])
        cov_line = "%.1f %% of RTL lines hit (Verilator coverage build)" % (100.0 * lh / lines)
    else:
        cov_line = TBD
    hil_rows = ["%s: %d of %d programs identical, %d bytes" % (c, v["hil"]["passed"], v["hil"]["programs"],
                                                                v["hil"]["bytes_compared"])
                for c, v in (sorted(board.items()) if board != TBD else []) if "hil" in v]
    rows = [
        ("RTL: multi-cycle core, 5-stage pipeline, SoC, peripherals", "done",
         "Verilog-2001, `rtl/`"),
        ("Static checks (rule checker, Verilator -Wall, Yosys no-latch proof, Vivado Tcl check)", "done", static),
        ("Regression (unit, directed, riscv-tests, arch-test, random lockstep, C programs)", "done", reg_line),
        ("Code coverage", "done", cov_line),
        ("Fault injection", "done", TBD if mut == TBD else "%d of %d injected bugs caught" % (mut["killed"], mut["total"])),
        ("Benchmarks in RTL simulation", "done",
         "Dhrystone %s / %s DMIPS/MHz, CoreMark %s / %s per MHz (multi-cycle / pipeline)" % (
             bm.get("dhrystone_dmips_mhz", TBD), bp.get("dhrystone_dmips_mhz", TBD),
             bm.get("coremark_mhz", TBD), bp.get("coremark_mhz", TBD))),
        ("Resource estimate (Yosys)", "done", TBD if y == TBD else "SoC %s / %s LUT, %s / %s FF" % (
            y["soc_mc"]["lut"], y["soc_pipe"]["lut"], y["soc_mc"]["ff"], y["soc_pipe"]["ff"])),
        ("Vivado 2018.2 build: utilisation and timing", "yours" if vv("pipe", "fmax_mhz") == TBD else "done",
         "Fmax %s / %s MHz, LUT %s / %s" % (vv("mc", "fmax_mhz"), vv("pipe", "fmax_mhz"), vv("mc", "lut"),
                                            vv("pipe", "lut"))),
        ("Board bring-up and on-board benchmarks", "yours" if board == TBD else "done",
         TBD if board == TBD else "Dhrystone %s / %s DMIPS/MHz, CoreMark %s / %s per MHz at %d MHz (multi-cycle / pipeline)" % (
             bb("mc", "dhrystone", "dmips_mhz"), bb("pipe", "dhrystone", "dmips_mhz"),
             bb("mc", "coremark", "coremark_per_mhz"), bb("pipe", "coremark", "coremark_per_mhz"),
             P["clock"]["cpu_hz"] // 1000000)),
        ("On-board self-test (UART output vs golden model)", "yours" if not hil_rows else "done",
         TBD if not hil_rows else "; ".join(hil_rows)),
        ("Paper, IEEE conference format, 6 pages", "done", "[`docs/paper/`](docs/paper/) (PDF and Word)"),
    ]
    L = []
    L += ["<!-- GENERATED FILE - DO NOT EDIT. Source: tools/make_readme.py -->", "",
          "# nexys_rv32", "",
          json.load(open(os.path.join(ROOT, "docs", "slots", "paper.json")))["title"] + ".", "",
          "Two RV32I cores (with machine-mode Zicsr, a timer interrupt and Zifencei) in Verilog-2001 for the "
          "Digilent Nexys A7-50T (XC7A50T), one SoC, a UART bootloader in a case-statement boot ROM, a C runtime "
          "and a regression that checks every retired instruction against a Python golden model.", "",
          "Author: Saman Fuyal, Department of Electrical and Electronics Engineering, Kathmandu University.", "",
          "![Nexys A7-50T board with its parts labelled](docs/slots/board_photo.jpg)", "",
          "## Status", "",
          "| Item | State | Evidence |", "|---|---|---|"]
    for a, b, c in rows:
        L.append("| %s | %s | %s |" % (a, b, c))
    L += ["", "Full numbers: [`docs/RESULTS.md`](docs/RESULTS.md). Decisions and open items: "
          "[`docs/STATUS.md`](docs/STATUS.md).", ""]

    L += ["## Memory map", "", "| Region | Base | Size | Execute | Write |", "|---|---|---|---|---|"]
    for name in ("bootrom", "ram", "io"):
        m = P["memory"][name]
        L.append("| %s | `%s` | %d KB | %s | %s |" % (name, m["base"], m["size"] // 1024,
                                                    "yes" if m["exec"] else "no", "yes" if m["write"] else "no"))
    L += ["", "Anything else raises an access fault. Peripheral and CSR tables: "
          "[`docs/generated/memory_map.md`](docs/generated/memory_map.md).", ""]

    L += ["## Board controls", "",
          "| Control | Function |", "|---|---|",
          "| CPU_RESET (red button) | Resets the SoC; the bootloader starts and shows `B0070001` |",
          "| SW15 up at reset | Bootloader skips the host and re-runs the program already in RAM |",
          "| SW0-SW15 | Read by programs (`switches_leds` mirrors them on the LEDs) |",
          "| BTNC/U/L/R/D | Read by programs; `seg7_counter`: pause, reset, count down, count up, stop |",
          "| LED0-LED15 | Written by programs (`timer_irq` blinks LED0 at 1 Hz) |",
          "| 7-segment display | 8 hex digits written by programs |",
          "| USB-UART (J6) | %d baud, 8N1: bootloader and program console |" % P["uart"]["baud"], ""]

    L += ["## Quick start (Windows)", "",
          "Every command, in order, with what it does: [`COMMANDS.md`](COMMANDS.md). Board checklist: "
          "[`docs/BRINGUP.md`](docs/BRINGUP.md).", "",
          "Tools: Python 3.10 or newer, Icarus Verilog 12, Vivado 2018.2, and the xPack RISC-V GCC 14.2.0-3 "
          "(only to rebuild the software; `sw/prebuilt/` has every program ready-made). From the project folder "
          "(the path must not contain spaces):", "",
          "```bat",
          "py -m pip install matplotlib pyserial",
          "preflight.bat",
          "run_sim.bat --quick",
          "```", "",
          "The last line ends with `ALL PASS`. The full regression (Verilator, Yosys and the long tests) runs in "
          "WSL or Linux with `bash wsl_regression.sh`. Then build both bitstreams:", "",
          "```bat",
          "fpga\\build.bat pipe",
          "fpga\\build.bat mc",
          "update_docs.bat",
          "```", "",
          "With the board on (JP1 on JTAG, cable in J6, SW15 down):", "",
          "```bat",
          "board_day.bat pipe",
          "```", "",
          "It programs the FPGA, loads `sw\\prebuilt\\hello.elf`, runs the benchmarks and the on-board self-test "
          "(158 programs whose UART output must match the golden model byte for byte) and updates the results. "
          "The tools find the COM port themselves (`--port auto`).", ""]

    L += ["## Folder layout", "", "| Folder | Contents |", "|---|---|",
          "| `params.json` | Single source of truth: clock, memory map, peripherals, CSRs |",
          "| `rtl/` | Verilog: `core/` (both cores and shared units), `soc/`, `periph/`, `gen/` (generated) |",
          "| `fpga/` | FPGA top, constraints, Vivado Tcl and `.bat` scripts |",
          "| `sim/` | Testbench, regression runner, unit/directed tests, riscv-tests and arch-test ports |",
          "| `model/` | Golden ISS, lockstep compare, random test generator, software board model |",
          "| `sw/` | Runtime, bootloader, programs, benchmarks, build script, Makefile; `sw/prebuilt/` ready-made programs |",
          "| `host/` | UART loader, on-board benchmark and on-board self-test scripts |",
          "| `tools/` | Generators, static checks, coverage, fault injection, figures |",
          "| `docs/` | Paper, board checklist, design decisions, results, figures, Vivado RTL schematics |",
          "| `*.bat`, `*.sh` (top) | `preflight.bat`, `board_day.bat`, `update_docs.bat`, `run_sim.bat`; `wsl_regression.sh` |",
          "| `results/` | Tool output that every document reads |", ""]
    L += ["## Licences of included third-party code", "",
          "`sim/riscv_tests/upstream`, `sim/arch_test/upstream`, `sw/third_party/coremark` and "
          "`sw/third_party/dhrystone` keep their original licence files.", ""]
    open(os.path.join(ROOT, "README.md"), "w", newline="\n").write("\n".join(L))
    print("README.md written")


if __name__ == "__main__":
    main()
