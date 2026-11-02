#!/usr/bin/env python3
# =============================================================================
# mutation_test.py - check that the regression catches deliberate RTL bugs
# -----------------------------------------------------------------------------
# Purpose : A test suite that passes on a correct design proves little unless
#           it also fails on a wrong one. Each mutant below injects one
#           realistic bug (a missing forwarding path, a wrong compare, a lost
#           stall, ...) into a copy of the project; the quick regression and
#           the unit tests must then fail ("mutant killed").
# Behavior: For each mutant: copy the tree (without build outputs) to
#           sim/build/mutation/<id>, apply the one-line change, run
#           sim/unit/run_unit.py and sim/run_sim.py --quick --sim verilator
#           --no-static (pipeline-only mutants run on the pipelined core
#           only), and record which test caught it first.
# Output  : results/mutation.json and results/mutation.md
# Usage   : py tools/mutation_test.py [--only ID]
# =============================================================================
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WORK = os.path.join(ROOT, "sim", "build", "mutation")

MUTANTS = [
    ("M01", "rtl/core/rv_core_pipe.v", "fwd_a_mem = m_valid_q && m_rd_we_q && (m_rd_q == e_rs1_q);",
     "fwd_a_mem = 1'b0;", "pipe", "no MEM->EX forwarding for rs1"),
    ("M02", "rtl/core/rv_core_pipe.v", "fwd_b_wb  = w_we && (w_rd_q == e_rs2_q);",
     "fwd_b_wb  = 1'b0;", "pipe", "no WB->EX forwarding for rs2"),
    ("M03", "rtl/core/rv_core_pipe.v", "stall = d_valid_q && e_valid_q && (e_load_q || e_csr_q) && e_rd_we_q &&",
     "stall = d_valid_q && e_valid_q && e_csr_q && e_rd_we_q &&", "pipe", "load-use interlock removed"),
    ("M04", "rtl/core/rv_core_pipe.v", "d_rs1_val = (w_we && (w_rd_q == d_rs1)) ? w_rd_data : rf_rdata1;",
     "d_rs1_val = rf_rdata1;", "pipe", "register-file write-through bypass removed"),
    ("M05", "rtl/core/rv_core_pipe.v", "e_valid_d = d_valid_q && !stall && !ex_redirect && !mem_redirect;",
     "e_valid_d = d_valid_q && !stall && !mem_redirect;", "pipe", "instruction after a taken branch not flushed"),
    ("M06", "rtl/core/rv_core_pipe.v", ".trap_epc(m_pc_q[31:2]),", ".trap_epc(e_pc_q[31:2]),", "pipe",
     "mepc taken from the wrong stage"),
    ("M07", "rtl/core/rv_core_pipe.v", "mem_redirect = trap || (commit && (m_mret_q || m_fencei_q));",
     "mem_redirect = trap || (commit && m_mret_q);", "pipe", "FENCE.I does not flush"),
    ("M08", "rtl/core/rv_alu.v", "ALU_SRA:  y = sra_y;", "ALU_SRA:  y = a >> shamt;", "both",
     "SRA computed as SRL"),
    ("M09", "rtl/core/rv_alu.v", "3'b111:  br_taken = ~ltu;", "3'b111:  br_taken = ~lt;", "both",
     "BGEU uses the signed compare"),
    ("M10", "rtl/core/rv_decode.v", "illegal = (funct7 != 7'b0000000);\n                end else if (funct3 == 3'b101) begin",
     "illegal = 1'b0;\n                end else if (funct3 == 3'b101) begin", "both",
     "SLLI with shamt[5] = 1 accepted"),
    ("M11", "rtl/core/rv_csr.v", "A_MINSTRET:  minstret_d = {minstret_q[63:32], wval};",
     "A_MINSTRET:  minstret_d = {minstret_q[63:32], wval} + 64'd1;", "both",
     "minstret write does not suppress the increment"),
    ("M12", "rtl/core/rv_lsu_load.v", "SZ_H:    data = {{16{~is_unsigned & half_sel[15]}}, half_sel};",
     "SZ_H:    data = {16'd0, half_sel};", "both", "LH not sign-extended"),
    ("M13", "rtl/soc/soc_bus.v", "dbus_fault = !( d_ram || (d_rom && !dbus_we) || io_ok );",
     "dbus_fault = !( d_ram || d_rom || io_ok );", "both", "stores to the boot ROM do not fault"),
    ("M14", "rtl/core/rv_core_mc.v", "end else if (taken && target[1]) begin",
     "end else if (1'b0) begin", "mc", "misaligned jump target not trapped (multi-cycle)"),
    ("M15", "rtl/core/rv_csr.v", "mpie_d   = mie_q;\n            mie_d    = 1'b0;",
     "mpie_d   = mie_q;\n            mie_d    = mie_q;", "both", "trap entry leaves interrupts enabled"),
    ("M16", "rtl/core/rv_lsu_req.v", "wstrb = 4'b0001 << addr_lo;", "wstrb = 4'b0001;", "both",
     "SB always writes byte lane 0"),
]


def copy_tree(dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    ign = shutil.ignore_patterns("build", ".git", "__pycache__", "*.dcp", "results")
    shutil.copytree(ROOT, dst, ignore=ign)
    os.makedirs(os.path.join(dst, "results"), exist_ok=True)


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True, errors="replace")
    return r.returncode, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--jobs", default="2")
    a = ap.parse_args()
    results = []
    for mid, f, old, new, cores, desc in MUTANTS:
        if a.only and a.only != mid:
            continue
        t0 = time.time()
        d = os.path.join(WORK, mid)
        copy_tree(d)
        p = os.path.join(d, f)
        s = open(p).read()
        if s.count(old) != 1:
            results.append(dict(id=mid, file=f, desc=desc, status="ERROR", killed_by="mutation site not found"))
            print("%s ERROR site not found in %s" % (mid, f))
            continue
        open(p, "w").write(s.replace(old, new))
        killed_by = None
        rc, out = run([sys.executable, "sim/unit/run_unit.py"], d)
        if rc:
            m = re.search(r"UNIT (\S+) FAIL", out)
            killed_by = "unit/" + (m.group(1) if m else "?")
        if not killed_by:
            core = {"pipe": "pipe", "mc": "mc", "both": "pipe,mc"}[cores]
            rc, out = run([sys.executable, "sim/run_sim.py", "--quick", "--sim", "verilator", "--no-static",
                           "--core", core, "--jobs", a.jobs], d)
            fails = re.findall(r"^FAIL (\S+) \[(\w+)/", out, re.M)
            if rc and fails:
                killed_by = "%s (%d failing runs)" % (fails[0][0], len(fails))
            elif rc:
                killed_by = "regression error: " + out.strip().splitlines()[-1][:120]
        st = "KILLED" if killed_by else "SURVIVED"
        results.append(dict(id=mid, file=f, desc=desc, status=st, killed_by=killed_by or "-",
                            seconds=round(time.time() - t0)))
        print("%s %-8s %-48s %s" % (mid, st, desc, killed_by or ""))
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    name = "mutation" if not a.only else "mutation_partial"
    json.dump(results, open(os.path.join(ROOT, "results", name + ".json"), "w"), indent=1)
    md = ["# Mutation test", "", "Generated by `tools/mutation_test.py`. Do not edit.", "",
          "Each mutant injects one bug into a copy of the RTL; the unit tests and the quick regression "
          "(Verilator) must fail.", "", "| ID | File | Injected bug | Result | First test that failed |",
          "|---|---|---|---|---|"]
    for r in results:
        md.append("| %s | `%s` | %s | %s | %s |" % (r["id"], r["file"], r["desc"], r["status"], r["killed_by"]))
    k = sum(r["status"] == "KILLED" for r in results)
    md += ["", "**%d of %d mutants killed.**" % (k, len(results))]
    open(os.path.join(ROOT, "results", name + ".md"), "w").write("\n".join(md) + "\n")
    sys.exit(0 if k == len(results) else 1)


if __name__ == "__main__":
    main()
