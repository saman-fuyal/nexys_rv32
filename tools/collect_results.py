#!/usr/bin/env python3
# =============================================================================
# collect_results.py - gather every number into results/summary.json
# -----------------------------------------------------------------------------
# Purpose : One place that turns raw tool output into the numbers the README,
#           the paper and RESULTS.md print. Anything not measured yet is
#           the string "[TBD]" and fills in automatically when its result file
#           appears (Vivado on build day, the board on bring-up day).
# Inputs  : results/regression.json   (sim/run_sim.py)
#           sim/build/runs/verilator/*/system/*/uart.txt
#           results/yosys_synth.json  (tools/yosys_check.py)
#           results/vivado_{pipe,mc}.json  (fpga/scripts/build.tcl)
#           results/board_<core>_<name>.json (host/board_bench.py, host/board_hil.py)
#           results/coverage.json, results/mutation.json
# Output  : results/summary.json, docs/RESULTS.md
# Options : --waves  also re-runs two short simulations with VCD output for
#                    the waveform figures (sim/build/wave/)
# =============================================================================
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RES = os.path.join(ROOT, "results")
RUNS = os.path.join(ROOT, "sim", "build", "runs", "verilator")
TBD = "[TBD]"


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


SIM_UART = os.path.join(RES, "sim_uart")


def uart(core, test):
    """UART output of a system test. A fresh regression run is copied into
    results/sim_uart/ so the numbers survive on machines that only run the
    quick regression (the long benchmark runs need Verilator)."""
    p = os.path.join(RUNS, core, "system", test, "uart.txt")
    keep = os.path.join(SIM_UART, "%s_%s.txt" % (core, test))
    if os.path.exists(p):
        os.makedirs(SIM_UART, exist_ok=True)
        text = open(p, encoding="latin-1").read()
        if text.strip():
            open(keep, "w", encoding="latin-1", newline="\n").write(text)
    return open(keep, encoding="latin-1").read() if os.path.exists(keep) else ""


def bench_from_uart(text):
    out = {}
    m = re.search(r"DHRY_STATS runs=(\d+) cycles=(\d+) instret=(\d+)", text)
    if m:
        runs, cyc, ins = map(int, m.groups())
        out.update(dhrystone_runs=runs, dhrystone_cycles_per_run=round(cyc / runs, 1),
                   dhrystone_dmips_mhz=round(1e6 * runs / (cyc * 1757.0), 3), dhrystone_cpi=round(cyc / ins, 3))
    m = re.search(r"CM_STATS iterations=(\d+) cycles=(\d+) instret=(\d+)", text)
    if m:
        it, cyc, ins = map(int, m.groups())
        out.update(coremark_iterations=it, coremark_cycles_per_iter=round(cyc / it),
                   coremark_mhz=round(it * 1e6 / cyc, 3), coremark_cpi=round(cyc / ins, 3),
                   coremark_validated="Correct operation validated." in text)
    return out


def regression_summary(reg):
    if not reg:
        return TBD
    groups = {}
    for r in reg["results"]:
        g = groups.setdefault(r["group"], dict(pass_=0, total=0, na=0))
        g["total"] += 1
        g["pass_"] += r["status"] == "PASS"
        g["na"] += r["status"] == "N/A"
    return dict(date=reg["date"], total=reg["total"], passed=reg["passed"], failed=reg["failed"],
                not_applicable=reg.get("not_applicable", 0), simulators=reg["simulators"],
                compiler=reg["compiler"], seeds=reg.get("seeds"),
                groups={k: dict(passed=v["pass_"], total=v["total"], na=v["na"]) for k, v in groups.items()})


def cpi_table(reg):
    """Cycles per retired instruction for each test that ran on both cores."""
    if not reg:
        return {}
    t = {}
    for r in reg["results"]:
        if r.get("sim") != "verilator" or r["status"] != "PASS" or not r.get("retired"):
            continue
        t.setdefault(r["test"], {})[r["core"]] = round(r["cycles"] / float(r["retired"]), 3)
    return t


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def perf_events(reg, test, core="pipe"):
    if not reg:
        return None
    for r in reg["results"]:
        if r["test"] == test and r["core"] == core and r.get("sim") == "verilator" and r.get("tb"):
            tb = r["tb"]
            return dict(cycles=int(tb["cycles"]), retired=int(tb["retired"]), stall=int(tb["ev_stall"]),
                        flush=int(tb["ev_flush"]), fwd_mem=int(tb["ev_fwd_mem"]), fwd_wb=int(tb["ev_fwd_wb"]),
                        irq=int(tb["ev_irq"]), trap=int(tb["ev_trap"]),
                        irq_lat_min=int(tb.get("irq_lat_min", 0)), irq_lat_max=int(tb.get("irq_lat_max", 0)))
    return None


def waves():
    """Short VCD runs for the waveform figures (sim/build/wave/*.vcd).

    Uses the Icarus build of the pipelined SoC from the regression: the
    regression's Verilator binaries are compiled without trace support (for
    speed), and Icarus is available on Windows too. tools/make_figures.py
    picks the window to draw from the dumps themselves."""
    wd = os.path.join(ROOT, "sim", "build", "wave")
    os.makedirs(wd, exist_ok=True)
    vvp = os.path.join(ROOT, "sim", "build", "icarus", "tb_pipe_80000000_r0.vvp")
    if not os.path.exists(vvp):
        print("waves: run the regression first (no Icarus build of the pipelined SoC)")
        return
    exe = ["vvp", "-n", vvp]
    hexf = os.path.join(ROOT, "sim", "build", "prog", "directed", "hazards.hex")
    subprocess.run(exe + ["+hex=" + hexf, "+vcd=" + os.path.join(wd, "hazards.vcd"), "+max_cycles=1500"],
                   cwd=wd, stdout=subprocess.PIPE)
    hello = os.path.join(ROOT, "sim", "build", "sw", "tmp_hello", "hello", "hello.hex")
    if os.path.exists(hello):
        # the first character only: one 8N1 frame is 10 x 868 cycles at 115200 baud
        subprocess.run(exe + ["+hex=" + hello, "+vcd=" + os.path.join(wd, "uart.vcd"),
                              "+max_cycles=9500"], cwd=wd, stdout=subprocess.PIPE)
    print("waves: written to sim/build/wave")


def main():
    if "--waves" in sys.argv:
        waves()
    reg = load("regression.json")
    s = {"note": "Generated by tools/collect_results.py. Every number names the tool that produced it."}
    s["regression"] = regression_summary(reg)
    s["bench_sim"] = {}
    for core in ("pipe", "mc"):
        b = bench_from_uart(uart(core, "system_dhrystone") + uart(core, "system_coremark"))
        if b:
            b["tool"] = "RTL simulation (Verilator), exact cycle counts; CoreMark run shorter than the 10 s its rules require"
        s["bench_sim"][core] = b
    cpis = cpi_table(reg)
    s["cpi"] = {k: v for k, v in cpis.items() if k.startswith(("system/", "directed/hazards"))}
    s["cpi_rvtests_avg"] = {c: avg([v.get(c) for k, v in cpis.items() if k.startswith("rvtests/")])
                            for c in ("pipe", "mc")}
    s["cpi_random_avg"] = {c: avg([v.get(c) for k, v in cpis.items() if k.startswith("random/")])
                           for c in ("pipe", "mc")}
    s["perf_pipe"] = {t: perf_events(reg, t) for t in ("system/dhrystone", "system/coremark")}
    s["irq"] = {c: perf_events(reg, "system/timer_irq", c) for c in ("pipe", "mc")}
    s["yosys"] = load("yosys_synth.json") or TBD
    s["vivado"] = {c: (load("vivado_%s.json" % c) or TBD) for c in ("pipe", "mc")}
    s["board"] = {}
    for f in sorted(glob.glob(os.path.join(RES, "board_*_*.json"))):
        m = re.match(r"board_(pipe|mc)_(\w+)\.json$", os.path.basename(f))
        if m:
            s["board"].setdefault(m.group(1), {})[m.group(2)] = json.load(open(f))
    if not s["board"]:
        s["board"] = TBD
    s["coverage"] = load("coverage.json") or TBD
    mut = load("mutation.json")
    s["mutation"] = (dict(killed=sum(m["status"] == "KILLED" for m in mut), total=len(mut), mutants=mut)
                     if mut else TBD)
    json.dump(s, open(os.path.join(RES, "summary.json"), "w"), indent=1)
    write_md(s)
    print("collect_results: results/summary.json, docs/RESULTS.md")


def fmt(v, f="%s"):
    return TBD if v in (None, TBD) else f % v


def write_md(s):
    L = ["# Results", "", "Generated by `tools/collect_results.py` from `results/`. Do not edit.", ""]
    r = s["regression"]
    L += ["## Regression", ""]
    if r == TBD:
        L.append(TBD)
    else:
        L += ["%s: %d passed, %d not applicable (documented), %d failed. Simulators: %s. Compiler: %s." % (
            r["date"], r["passed"], r["not_applicable"], r["failed"],
            ", ".join(r["simulators"].values()), r["compiler"]), "",
              "| Layer | Passed / Run | Not applicable |", "|---|---|---|"]
        for g, v in sorted(r["groups"].items()):
            L.append("| %s | %d / %d | %d |" % (g, v["passed"], v["total"] - v["na"], v["na"]))
    L += ["", "## Performance (RTL simulation, exact cycles)", "",
          "| Metric | Multi-cycle | 5-stage pipeline |", "|---|---|---|"]
    bm, bp = s["bench_sim"].get("mc", {}), s["bench_sim"].get("pipe", {})
    for key, label, f in (("dhrystone_dmips_mhz", "Dhrystone DMIPS/MHz", "%.3f"),
                          ("dhrystone_cpi", "Dhrystone CPI", "%.3f"),
                          ("coremark_mhz", "CoreMark/MHz (short run)", "%.3f"),
                          ("coremark_cpi", "CoreMark CPI", "%.3f")):
        L.append("| %s | %s | %s |" % (label, fmt(bm.get(key), f), fmt(bp.get(key), f)))
    L.append("| riscv-tests average CPI | %s | %s |" % (fmt(s["cpi_rvtests_avg"].get("mc"), "%.3f"),
                                                      fmt(s["cpi_rvtests_avg"].get("pipe"), "%.3f")))
    L += ["", "## Resources and timing", "", "| | Multi-cycle | 5-stage pipeline | Tool |", "|---|---|---|---|"]
    y = s["yosys"]
    if y != TBD:
        for k, lab in (("lut", "LUT (SoC)"), ("ff", "FF (SoC)"), ("ramb36", "RAMB36 (SoC)")):
            L.append("| %s | %s | %s | %s |" % (lab, y["soc_mc"][k], y["soc_pipe"][k], "Yosys estimate"))
        L.append("| LUT (core only) | %s | %s | Yosys estimate |" % (y["core_mc"]["lut"], y["core_pipe"]["lut"]))
    for k, lab, f in (("lut", "LUT (SoC)", "%s"), ("ff", "FF (SoC)", "%s"), ("ramb36", "RAMB36", "%s"),
                      ("fmax_mhz", "Fmax (MHz)", "%s"), ("wns_ns", "WNS at 100 MHz (ns)", "%s")):
        vm, vp = s["vivado"]["mc"], s["vivado"]["pipe"]
        L.append("| %s | %s | %s | Vivado 2018.2 |" % (lab, vm[k] if vm != TBD else TBD, vp[k] if vp != TBD else TBD))
    L += ["", "## On the board", ""]
    if s["board"] == TBD:
        L.append(TBD + " (host/board_bench.py and host/board_hil.py write results/board_<core>_<name>.json)")
    else:
        L += ["| Program | Core | Result |", "|---|---|---|"]
        for core, progs in sorted(s["board"].items()):
            for name, v in sorted(progs.items()):
                keys = [k for k in ("ok", "programs", "passed", "failed", "bytes_compared", "dmips_mhz", "cpi", "coremark_per_mhz", "seconds", "valid_run_length",
                                    "validated", "clock_hz") if k in v and v[k] is not None]
                L.append("| %s | %s | %s |" % (name, core, ", ".join("%s=%s" % (k, v[k]) for k in keys)))
    m = s["mutation"]
    L += ["", "## Mutation test", "", TBD if m == TBD else "%d of %d injected bugs caught." % (m["killed"], m["total"])]
    if any(TBD in line for line in L):
        L[3:3] = ["[TBD] marks numbers that need Vivado or the board; they fill in when those result files exist.", ""]
    open(os.path.join(ROOT, "docs", "RESULTS.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
