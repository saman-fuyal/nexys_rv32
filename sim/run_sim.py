#!/usr/bin/env python3
# =============================================================================
# run_sim.py - the regression: every static check and every test, one command
# -----------------------------------------------------------------------------
# Purpose : "py sim/run_sim.py" rebuilds what it needs, runs all checks and
#           tests, writes results/regression.{json,md} and ends with ALL PASS
#           or a list of failures (exit code 0 / 1).
# Layers  : static   generated-file hash, rule checker (+ self-test on
#                    deliberately broken files), Verilator -Wall lint, Yosys
#                    latch proof and synthesis estimate
#           unit     self-checking block testbenches (sim/unit)
#           directed hand-written assembly tests (sim/directed)
#           rvtests  riscv-tests rv32ui + rv32mi, environment unmodified
#           arch     riscv-arch-test 2.7.4 signatures vs Sail references
#           random   random instruction streams, lockstep with the ISS
#           system   the C programs and the bootloader, checked at the pins
#           Every core-level test runs on both cores and, except unit and
#           static checks, its full retirement trace is compared with the
#           golden ISS (model/cosim.py).
# Sims    : verilator (all tests), icarus (all except long ones), xsim
#           (Vivado 2018.2, same subset as icarus; Windows). By default every
#           simulator found on PATH is used.
# Usage   : py sim/run_sim.py [--quick] [--sim verilator,icarus,xsim]
#               [--core pipe,mc] [--only REGEX] [--jobs N] [--seeds N]
#               [--coverage] [--list] [--keep-going]
# =============================================================================
import argparse
import glob
import hashlib
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BUILD = os.path.join(HERE, "build")
RESULTS = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(ROOT, "model"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import params as params_mod  # noqa: E402

P = params_mod.load()
IS_WIN = os.name == "nt"
RTL_INC = ["rtl/core", "rtl/gen"]
RTL_FILES = (sorted(glob.glob(os.path.join(ROOT, "rtl/core/*.v"))) +
             sorted(glob.glob(os.path.join(ROOT, "rtl/soc/*.v"))) +
             sorted(glob.glob(os.path.join(ROOT, "rtl/periph/*.v"))) +
             [os.path.join(ROOT, "rtl/gen/bootrom.v")])
TB = os.path.join(HERE, "tb", "tb_soc.v")
RAM_BASE = P.ram["base"]
CROSS = os.environ.get("CROSS", P.cross_prefix)


# =============================================================================
# helpers
# =============================================================================
def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def which(name):
    for n in (name, name + ".exe", name + ".bat"):
        p = shutil.which(n)
        if p:
            return p
    return None


def sh(cmd, cwd=None, timeout=None, env=None):
    """Run a command list; returns (rc, output)."""
    if IS_WIN and cmd and cmd[0].lower().endswith(".bat"):
        cmd = ["cmd", "/c"] + cmd
    try:
        r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, timeout=timeout, env=env, errors="replace")
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or "") + "\n[timeout]"
    except OSError as e:
        return 127, str(e)


def py(script, *args, timeout=None):
    return sh([sys.executable, os.path.join(ROOT, script)] + list(args), timeout=timeout)


def ensure(d):
    os.makedirs(d, exist_ok=True)
    return d


# =============================================================================
# toolchain and program builds
# =============================================================================
def gcc():
    g = which(CROSS + "gcc")
    if not g:
        raise SystemExit("RISC-V GCC '%sgcc' not found on PATH (COMMANDS.md, 'One-time setup')" % CROSS)
    return g


GCC_ASM = ["-march=rv32i_zicsr_zifencei", "-mabi=ilp32", "-static", "-nostdlib", "-nostartfiles",
           "-mno-relax"]


def build_asm(src, out_dir, name, incs, defines=(), ld=None, ram_size=None):
    ensure(out_dir)
    elf = os.path.join(out_dir, name + ".elf")
    cmd = [gcc()] + GCC_ASM + ["-I" + i for i in incs] + ["-D" + d for d in defines] + \
          ["-T", ld or os.path.join(HERE, "riscv_tests", "link.ld"), src, "-o", elf]
    rc, out = sh(cmd)
    if rc:
        errs = [l for l in out.splitlines() if "Error" in l or "error:" in l]
        raise RuntimeError("assembler failed for %s: %s\n%s" % (rel(src), "; ".join(errs[:3]) or "see below",
                                                               out[-3000:]))
    hexf = os.path.join(out_dir, name + ".hex")
    rc, out = py("tools/elf2hex.py", elf, hexf, *(["--ram-size", str(ram_size)] if ram_size else []))
    if rc:
        raise RuntimeError(out)
    return elf, hexf


def elf_symbols(elf):
    import elf as elf_mod
    return elf_mod.load(elf).symbols


_SW_BUILT = {}


def build_sw(target, variant="", defines=(), cc="gcc"):
    """Build a C program with sw/build.py into sim/build/sw/<target><variant>."""
    key = (target, variant, tuple(defines), cc)
    if key in _SW_BUILT:
        return _SW_BUILT[key]
    out = ensure(os.path.join(BUILD, "sw" + ("_" + cc if cc != "gcc" else "")))
    name = target + variant
    args = ["sw/build.py", target, "--out", os.path.join(out, "tmp_" + name), "--cc", cc, "--no-bootrom"]
    for d in defines:
        args += ["-D", d]
    rc, txt = sh([sys.executable] + [os.path.join(ROOT, args[0])] + args[1:])
    if rc:
        raise RuntimeError("sw build failed for %s:\n%s" % (name, txt[-3000:]))
    d = os.path.join(out, "tmp_" + name, target)
    _SW_BUILT[key] = (os.path.join(d, target + ".elf"), os.path.join(d, target + ".hex"), txt)
    return _SW_BUILT[key]


# =============================================================================
# simulators
# =============================================================================
class Sim(object):
    name = "?"
    def available(self):
        return False


class Verilator(Sim):
    name = "verilator"
    def __init__(self, coverage=False):
        self.exe = which("verilator")
        self.coverage = coverage
        self._built = {}
    def available(self):
        # Verilator compiles C++: without make and a C++ compiler (typical on plain
        # Windows) it is skipped, and the long tests are left to WSL (COMMANDS.md, 'Full regression in WSL').
        return self.exe is not None and which("make") is not None and \
            (which("g++") is not None or which("clang++") is not None)
    def build(self, core, start_pc, ram_aw=0):
        key = (core, start_pc, ram_aw)
        if key in self._built:
            return self._built[key]
        tag = "%s_%08x_r%d%s" % (core, start_pc, ram_aw, "_cov" if self.coverage else "")
        mdir = ensure(os.path.join(BUILD, "verilator", tag))
        binp = os.path.join(mdir, "tb_soc")
        stamp = os.path.join(mdir, "stamp")
        sig = srcsig()
        if not (os.path.exists(binp) and os.path.exists(stamp) and open(stamp).read() == sig):
            cmd = [self.exe, "--binary", "--timing", "-j", "2", "-Wno-fatal", "-Wno-lint", "-Wno-style",
                   "-Wno-TIMESCALEMOD", "--Mdir", mdir, "-o", "tb_soc", "--top-module", "tb_soc",
                   "-GCORE_PIPE=%d" % (1 if core == "pipe" else 0), "-GSTART_PC=32'h%08x" % start_pc,
                   "-GSIM_RAM_AW=%d" % ram_aw]
            if self.coverage:
                cmd += ["--coverage-line", "--coverage-toggle"]
            cmd += ["-I" + os.path.join(ROOT, i) for i in RTL_INC] + [TB] + RTL_FILES
            rc, out = sh(cmd, timeout=1800)
            if rc:
                raise RuntimeError("verilator build failed:\n" + out[-4000:])
            open(stamp, "w").write(sig)
        self._built[key] = binp
        return binp
    def run(self, core, start_pc, ram_aw, plusargs, workdir, timeout):
        exe = self.build(core, start_pc, ram_aw)
        args = [exe] + plusargs
        if self.coverage:
            args.append("+verilator+coverage+file+" + os.path.join(workdir, "coverage.dat"))
        return sh(args, cwd=workdir, timeout=timeout)


class Icarus(Sim):
    name = "icarus"
    def __init__(self):
        self.iv = which("iverilog")
        self.vvp = which("vvp")
        self._built = {}
    def available(self):
        return self.iv is not None and self.vvp is not None
    def build(self, core, start_pc, ram_aw=0):
        key = (core, start_pc, ram_aw)
        if key in self._built:
            return self._built[key]
        out = ensure(os.path.join(BUILD, "icarus"))
        vvp = os.path.join(out, "tb_%s_%08x_r%d.vvp" % (core, start_pc, ram_aw))
        stamp = vvp + ".stamp"
        sig = srcsig()
        if not (os.path.exists(vvp) and os.path.exists(stamp) and open(stamp).read() == sig):
            cmd = [self.iv, "-g2005", "-Wall", "-Wno-timescale", "-o", vvp, "-s", "tb_soc",
                   "-P", "tb_soc.CORE_PIPE=%d" % (1 if core == "pipe" else 0),
                   "-P", "tb_soc.START_PC=32'h%08x" % start_pc, "-P", "tb_soc.SIM_RAM_AW=%d" % ram_aw]
            cmd += ["-I" + os.path.join(ROOT, i) for i in RTL_INC] + [TB] + RTL_FILES
            rc, txt = sh(cmd)
            if rc or "warning" in txt.lower():
                raise RuntimeError("iverilog build failed or warned:\n" + txt[-4000:])
            open(stamp, "w").write(sig)
        self._built[key] = vvp
        return vvp
    def run(self, core, start_pc, ram_aw, plusargs, workdir, timeout):
        return sh([self.vvp, "-n", self.build(core, start_pc, ram_aw)] + plusargs, cwd=workdir, timeout=timeout)


def xsim_wrapper(core, start_pc, ram_aw):
    """Top module that sets the testbench parameters for one configuration."""
    return ("`timescale 1ns / 1ps\n"
            "// generated by sim/run_sim.py for xsim: tb_soc with this configuration\n"
            "module tb_xsim_cfg;\n"
            "    tb_soc #(.CORE_PIPE(%d), .START_PC(32'h%08x), .SIM_RAM_AW(%d)) tb_soc ();\n"
            "endmodule\n" % (1 if core == "pipe" else 0, start_pc, ram_aw))


class Xsim(Sim):
    """Vivado 2018.2 simulator: xvlog / xelab / xsim (Windows .bat or Linux)."""
    name = "xsim"
    def __init__(self):
        self.xvlog, self.xelab, self.xsim = which("xvlog"), which("xelab"), which("xsim")
        self._built = {}
    def available(self):
        return all((self.xvlog, self.xelab, self.xsim))
    def build(self, core, start_pc, ram_aw=0):
        key = (core, start_pc, ram_aw)
        if key in self._built:
            return self._built[key]
        wd = ensure(os.path.join(BUILD, "xsim", "%s_%08x_r%d" % (core, start_pc, ram_aw)))
        snap = "tb_%s" % core
        stamp = os.path.join(wd, "stamp")
        sig = srcsig()
        if not (os.path.exists(stamp) and open(stamp).read() == sig):
            inc = []
            for i in RTL_INC:
                inc += ["-i", os.path.join(ROOT, i)]
            # Parameters go through a generated wrapper module rather than
            # xelab -generic_top, so Verilog literals such as 32'h80000000 need
            # no command-line quoting (and the same file works on Windows).
            wrap = os.path.join(wd, "tb_xsim_cfg.v")
            with open(wrap, "w") as fh:
                fh.write(xsim_wrapper(core, start_pc, ram_aw))
            rc, out = sh([self.xvlog] + inc + [TB, wrap] + RTL_FILES, cwd=wd)
            if rc:
                raise RuntimeError("xvlog failed:\n" + out[-4000:])
            rc, out = sh([self.xelab, "-debug", "off", "-s", snap, "work.tb_xsim_cfg"], cwd=wd)
            if rc:
                raise RuntimeError("xelab failed:\n" + out[-4000:])
            open(stamp, "w").write(sig)
        self._built[key] = (wd, snap)
        return self._built[key]
    def run(self, core, start_pc, ram_aw, plusargs, workdir, timeout):
        wd, snap = self.build(core, start_pc, ram_aw)
        args = [self.xsim, snap, "-R"]
        for p in plusargs:
            args += ["-testplusarg", p.lstrip("+")]
        return sh(args, cwd=wd, timeout=timeout)


_SRCSIG = None


def srcsig():
    global _SRCSIG
    if _SRCSIG is None:
        h = hashlib.sha256()
        for f in [TB] + RTL_FILES + glob.glob(os.path.join(ROOT, "rtl/*/*.vh")):
            h.update(open(f, "rb").read())
        _SRCSIG = h.hexdigest()[:20]
    return _SRCSIG


# =============================================================================
# result parsing and checks
# =============================================================================
def parse_tb(out):
    m = re.search(r"TB_RESULT (.*)", out)
    if not m:
        return None
    d = {}
    for kv in m.group(1).split():
        k, _, v = kv.partition("=")
        d[k] = v
    m = re.search(r"TB_IRQ count=(\d+) lat_min=(\d+) lat_max=(\d+)", out)
    if m:
        d["irq_count"], d["irq_lat_min"], d["irq_lat_max"] = m.groups()
    return d


def cosim(elf, trace, core, start=None, preload=True, ram_size=None):
    args = ["model/cosim.py", elf, trace, "--core", core, "--boot", BOOT_ELF]
    if ram_size:
        args += ["--ram-size", str(ram_size)]
    if not preload:
        args.append("--no-load")
    if start is not None:
        args += ["--start", "0x%08x" % start]
    rc, out = py(*args, timeout=3600)
    return rc == 0, out.strip().splitlines()[-1] if out.strip() else "no output"


BOOT_ELF = os.path.join(ROOT, "sw", "build", "boot", "boot.elf")


# =============================================================================
# tests
# =============================================================================
class Test(object):
    """One program run on the SoC: build -> simulate -> check -> cosim."""

    def __init__(self, name, group, build, check=None, max_cycles=200000, long=False,
                 cores=("pipe", "mc"), start_pc=None, plus=(), do_cosim=True, note="", na=None, ram_aw=0):
        self.name, self.group, self._build, self.check = name, group, build, check
        self.na, self.ram_aw = na, ram_aw
        self.max_cycles, self.long, self.cores = max_cycles, long, cores
        self.start_pc = RAM_BASE if start_pc is None else start_pc
        self.plus, self.do_cosim, self.note = list(plus), do_cosim, note


TESTS = []


def all_tests(quick, seeds):
    return directed_tests() + riscv_tests() + arch_tests() + random_tests(4 if quick else seeds) + system_tests() + \
        hil_tests()


def init_worker(sim_names, coverage, quick, seeds):
    """Pool initializer: rebuild the simulator objects and the test list in the
    worker (Windows starts workers fresh, and test build functions are closures)."""
    global TESTS
    cands = {"verilator": lambda: Verilator(coverage), "icarus": Icarus, "xsim": Xsim}
    for n in sim_names:
        SIMS[n] = cands[n]()
    TESTS[:] = all_tests(quick, seeds)


def build_one(ti):
    """Worker: build one test program. Run once per test, before any simulation,
    so parallel runs of the same test never rewrite a file another one reads."""
    try:
        b = TESTS[ti]._build()
        return ti, (b[0], b[1], list(b[2]) if len(b) > 2 else []), None
    except Exception as e:
        return ti, None, "%s: %s" % (type(e).__name__, str(e)[-1500:])


def run_one(job):
    """Worker: job = (test index, core, sim_name, opts, build). Returns a result dict."""
    ti, core, simname, opts, built = job
    t = TESTS[ti]
    sim = SIMS[simname]
    t0 = time.time()
    res = dict(test=t.name, group=t.group, core=core, sim=simname, status="FAIL", detail="", note=t.note)
    work = ensure(os.path.join(BUILD, "runs", simname, core, t.group, re.sub(r"[^\w.-]", "_", t.name)))
    try:
        if built[1] is not None:
            raise RuntimeError(built[1])
        elf, hexf, extra = built[0]
        trace = os.path.join(work, "trace.txt")
        uartlog = os.path.join(work, "uart.txt")
        plus = ["+max_cycles=%d" % t.max_cycles, "+trace=" + trace, "+uartlog=" + uartlog] + t.plus + extra
        if hexf:
            plus.append("+hex=" + hexf)
        rc, out = sim.run(core, t.start_pc, t.ram_aw, plus, work, timeout=opts["timeout"])
        open(os.path.join(work, "sim.log"), "w").write(out)
        tb = parse_tb(out)
        if tb is None:
            res["detail"] = "no TB_RESULT (rc=%d): %s" % (rc, out[-400:].strip().replace("\n", " | "))
            return res
        res.update(cycles=int(tb.get("cycles", 0)), retired=int(tb.get("retired", 0)), tb=tb)
        uart = open(uartlog, encoding="latin-1").read() if os.path.exists(uartlog) else ""
        ok, msg = t.check(tb, uart, work) if t.check else (tb["status"] == "TOHOST" and tb["tohost"] == "00000001",
                                                             "tohost=%s status=%s" % (tb["tohost"], tb["status"]))
        res["detail"] = msg
        if ok and t.do_cosim:
            cok, cmsg = cosim(elf, trace, core, None if t.start_pc == RAM_BASE else t.start_pc,
                              preload=hexf is not None,
                              ram_size=(1 << t.ram_aw) if t.ram_aw else None)
            res["cosim"] = cmsg
            if not cok:
                ok = False
                res["detail"] = "cosim: " + cmsg
        if ok:
            res["status"] = "PASS"
            if not opts.get("keep_traces"):
                for f in (trace,):
                    if os.path.exists(f) and os.path.getsize(f) > 5e6:
                        os.remove(f)
    except Exception as e:     # a build or tool failure is a test failure
        res["detail"] = "%s: %s" % (type(e).__name__, str(e)[-1500:])
    res["seconds"] = round(time.time() - t0, 2)
    return res


# ---- check helpers ----------------------------------------------------------
def expect_tohost(value, extra=None):
    def chk(tb, uart, work):
        ok = tb["status"] == "TOHOST" and int(tb["tohost"], 16) == value
        msg = "tohost=%s (expected %08x)" % (tb["tohost"], value)
        if ok and extra:
            ok, m2 = extra(tb, uart, work)
            msg += "; " + m2
        return ok, msg
    return chk


def uart_contains(*needles):
    def chk(tb, uart, work):
        missing = [n for n in needles if n not in uart]
        return (not missing, "uart ok" if not missing else "uart missing %r" % missing)
    return chk


def all_of(*checks):
    def chk(tb, uart, work):
        msgs = []
        for c in checks:
            ok, m = c(tb, uart, work)
            msgs.append(m)
            if not ok:
                return False, "; ".join(msgs)
        return True, "; ".join(msgs)
    return chk


# ---- test definitions --------------------------------------------------------
def directed_tests():
    tests = []
    for src in sorted(glob.glob(os.path.join(HERE, "directed", "*.S"))):
        name = os.path.splitext(os.path.basename(src))[0]
        def b(src=src, name=name):
            return build_asm(src, os.path.join(BUILD, "prog", "directed"), name,
                             [os.path.join(HERE, "directed")], defines=("CLK_HZ=%d" % P.cpu_hz,))
        tests.append(Test("directed/" + name, "directed", b, max_cycles=200000))
    return tests


RV_UP = os.path.join(HERE, "riscv_tests", "upstream")
# Tests whose expected outcome is a documented failure code, not 'pass'. They
# still run on both cores and their traces must match the ISS exactly, so the
# failure is the specified behaviour of this core, reproduced instruction by
# instruction.
RV_EXPECT = {
    "rv32ui-ma_data": (0x539, "requires misaligned loads/stores to succeed; this core traps on them "
                              "(allowed by the ISA), so the test reports failure 1337, as the ISS does"),
    "rv32mi-breakpoint": (0x5, "needs the Sdtrig trigger module (not implemented): the tselect write "
                               "traps as illegal and test 2 reports failure, as the ISS does"),
    "rv32mi-pmpaddr": (0x3, "needs PMP (not implemented): pmpaddr0 traps as illegal and test 1 "
                            "reports failure, as the ISS does"),
    "rv32mi-zicntr": (0x5, "needs the Zicntr user counters cycle/time/instret (not implemented: "
                           "machine counters only); test 2 reports failure, as the ISS does"),
}


def riscv_tests():
    tests = []
    for suite in ("rv32ui", "rv32mi"):
        for src in sorted(glob.glob(os.path.join(RV_UP, "isa", suite, "*.S"))):
            name = os.path.splitext(os.path.basename(src))[0]
            full = "%s-%s" % (suite, name)
            def b(src=src, full=full):
                return build_asm(src, os.path.join(BUILD, "prog", "rvtests"), full,
                                 [os.path.join(RV_UP, "env", "p"), os.path.join(RV_UP, "isa", "macros", "scalar")])
            chk, note = None, ""
            if full in RV_EXPECT:
                v, note = RV_EXPECT[full]
                chk = expect_tohost(v)
            tests.append(Test("rvtests/" + full, "rvtests", b, check=chk, note=note))
    return tests


AT_UP = os.path.join(HERE, "arch_test", "upstream")
# 2.7.4 ships one reference per test. For these, Sail ran an RV32IC
# configuration, where a 2-byte-aligned branch/jump target is legal. This core
# has no C extension, so the ISA requires the instruction-address-misaligned
# trap it takes. Their signature is checked against the golden ISS instead.
AT_RV32IC_REF = {"misalign-beq-01", "misalign-bge-01", "misalign-bgeu-01", "misalign-blt-01",
                 "misalign-bltu-01", "misalign-bne-01", "misalign-jal-01", "misalign2-jalr-01"}


def arch_defines(src):
    """The 'def NAME=VALUE' entries of a test's RVTEST_CASE strings (as RISCOF does)."""
    defs = set(re.findall(r"def\s+([A-Za-z_]\w*)\s*=\s*(\w+)", open(src, encoding="utf-8", errors="replace").read()))
    return ["XLEN=32"] + sorted("%s=%s" % d for d in defs)


def iss_signature(elf, begin, end, ram_size):
    import iss as iss_mod
    Pc = params_mod.load(overrides={"memory.ram.size": ram_size})
    m = iss_mod.Iss(Pc)
    if os.path.exists(BOOT_ELF):
        iss_mod.load_program(m, BOOT_ELF)
    e = iss_mod.load_program(m, elf)
    m.pc = e.entry
    iss_mod.run(m, 5000000)
    return ["%08x" % m.soc.load(a, 4) for a in range(begin, end, 4)]


LA_UPSTREAM = "la reg,val;"
LA_FIXED = "9999: auipc reg, %pcrel_hi(val); addi reg, reg, %pcrel_lo(9999b);"


def arch_env():
    """riscv-arch-test 2.7.4's LA() macro uses the 'la' pseudo-instruction, and jalr-01 calls it
    with rd = x0. Binutils 2.42 and later reject 'la x0, sym' (xPack GCC 14.2.0-3 ships 2.43.1),
    while 2.41 expanded it to auipc + addi. This writes a copy of arch_test.h whose LA() emits
    that same auipc + addi pair explicitly: the same 8 bytes, accepted by every binutils release,
    so the Sail reference signatures still apply. The upstream file stays untouched, and the
    copy differs from it only in the two LA() definitions (checked here)."""
    d = os.path.join(BUILD, "arch_env")
    ensure(d)
    # bytes, not text: the header contains UTF-8 punctuation, which Windows' default codec cannot read
    src = open(os.path.join(AT_UP, "env", "arch_test.h"), "rb").read()
    old_b, new_b = LA_UPSTREAM.encode("ascii"), LA_FIXED.encode("ascii")
    if src.count(old_b) != 2:
        raise RuntimeError("arch_test.h: expected 2 LA() definitions using '%s', found %d"
                           % (LA_UPSTREAM, src.count(old_b)))
    out = os.path.join(d, "arch_test.h")
    new = src.replace(old_b, new_b)
    if not os.path.exists(out) or open(out, "rb").read() != new:
        tmp = "%s.%d" % (out, os.getpid())      # parallel workers: write, then rename atomically
        with open(tmp, "wb") as fh:
            fh.write(new)
        try:
            os.replace(tmp, out)
        except OSError:
            # Windows refuses the rename while another worker's assembler has the file open;
            # that worker wrote the same bytes, so the existing file is the right one
            os.remove(tmp)
            if open(out, "rb").read() != new:
                raise
    return d


def arch_tests():
    tests = []
    for suite in ("I", "privilege", "Zifencei"):
        for src in sorted(glob.glob(os.path.join(AT_UP, "rv32i_m", suite, "src", "*.S"))):
            name = os.path.splitext(os.path.basename(src))[0]
            ref = os.path.join(AT_UP, "rv32i_m", suite, "references", name + ".reference_output")
            def b(src=src, name=name, suite=suite):
                out = os.path.join(BUILD, "prog", "arch", suite)
                elf, hexf = build_asm(src, out, name,
                                      [arch_env(), os.path.join(HERE, "arch_test"),
                                       os.path.join(AT_UP, "env")],
                                      defines=arch_defines(src),
                                      ld=os.path.join(HERE, "arch_test", "link.ld"),
                                      ram_size=P.compliance_ram_size)
                s = elf_symbols(elf)
                return elf, hexf, ["+sigfile=signature.txt", "+sig_begin=%08x" % s["begin_signature"],
                                   "+sig_end=%08x" % s["end_signature"]]
            def chk(tb, uart, work, ref=ref, name=name, suite=suite):
                if tb["status"] != "TOHOST" or tb["tohost"] != "00000001":
                    return False, "did not halt (tohost=%s)" % tb["tohost"]
                got = [l.strip() for l in open(os.path.join(work, "signature.txt")) if l.strip()]
                if name in AT_RV32IC_REF:
                    elf = os.path.join(BUILD, "prog", "arch", suite, name + ".elf")
                    sy = elf_symbols(elf)
                    exp = iss_signature(elf, sy["begin_signature"], sy["end_signature"], P.compliance_ram_size)
                else:
                    exp = [l.strip() for l in open(ref) if l.strip()]
                if got != exp:
                    for i, (g, e) in enumerate(zip(got, exp)):
                        if g != e:
                            return False, "signature word %d: got %s expected %s" % (i, g, e)
                    return False, "signature length %d expected %d" % (len(got), len(exp))
                return True, "signature %d words match %s" % (
                    len(exp), "the golden ISS (Sail reference is RV32IC)" if name in AT_RV32IC_REF
                    else "the Sail reference")
            note = "compliance configuration: %d KB simulated RAM (tests up to 1.75 MB)" % (
                P.compliance_ram_size // 1024)
            if name in AT_RV32IC_REF:
                note = ("2.7.4 reference was generated for RV32IC (misaligned-by-2 target legal); without C "
                        "the ISA requires the trap, so the signature is checked against the golden ISS")
            tests.append(Test("arch/%s/%s" % (suite, name), "arch", b, check=chk, max_cycles=1500000,
                              ram_aw=P.compliance_ram_aw, note=note))
    return tests


def random_tests(n):
    tests = []
    for seed in range(1, n + 1):
        def b(seed=seed):
            out = ensure(os.path.join(BUILD, "prog", "random"))
            src = os.path.join(out, "rand_%04d.S" % seed)
            rc, txt = py("model/rand_gen.py", "--seed", str(seed), "--count", "1500", "-o", src)
            if rc:
                raise RuntimeError(txt)
            return build_asm(src, out, "rand_%04d" % seed, [])
        tests.append(Test("random/seed%04d" % seed, "random", b, max_cycles=300000, long=seed > 4))
    return tests


def coremark_crcs_ok(uart):
    """A short simulated CoreMark run is correct when the seed and the three
    result CRCs equal CoreMark's own reference values for the 2K performance
    run (core_main.c, known_id 0xe9f5) and the only reported error is the
    10-second minimum run time, which a simulation cannot meet."""
    want = {"seedcrc": "0xe9f5", "[0]crclist": "0xe714", "[0]crcmatrix": "0x1fd7", "[0]crcstate": "0x8e3a"}
    for k, v in want.items():
        if not re.search(re.escape(k) + r"\s*:\s*" + v + r"\b", uart):
            return False
    if re.search(r"ERROR! (list|matrix|state) crc", uart):
        return False
    return "Correct operation validated." in uart or "Must execute for at least 10 secs" in uart


# ---- on-board self-test programs, proven on the RTL first ------------------
HIL_SEEDS = (1, 2, 3)
HIL_QUICK_RV = ("rv32ui-add", "rv32mi-breakpoint")


def hil_uart_check(elf, tail=None):
    """The RTL's UART output must equal the golden ISS's, byte for byte."""
    def chk(tb, uart, work):
        sys.path.insert(0, os.path.join(ROOT, "model"))
        import hil
        exp, n = hil.expected_output(elf)
        ok, msg = hil.compare(uart.encode("latin-1"), exp)
        msg = "UART vs ISS: " + msg + " (%d instructions)" % n
        if ok and tail:
            rest = uart.encode("latin-1")[len(exp):]
            ok = tail in rest
            msg += "; then %s" % ("the bootloader banner (back in the boot ROM)" if ok else "NO bootloader banner")
        return ok, msg
    return chk


def hil_tests():
    sys.path.insert(0, os.path.join(ROOT, "model"))
    import hil
    out_dir = os.path.join(BUILD, "prog", "hil")
    tests = []

    def hexed(elf):
        hexf = elf[:-4] + ".hex"
        rc, txt = py("tools/elf2hex.py", elf, hexf)
        if rc:
            raise RuntimeError(txt)
        return elf, hexf

    for seed in HIL_SEEDS:
        elf = os.path.join(out_dir, "rand_%04d.elf" % seed)
        tests.append(Test("hil/rand_%04d" % seed, "hil", lambda seed=seed: hexed(hil.build_rand(seed, out_dir)),
                          check=all_of(expect_tohost(1), hil_uart_check(elf)), max_cycles=50000000, long=True))
    # the jump back into the bootloader, as on the board (no lockstep after TOHOST: the boot ROM runs on)
    elf = os.path.join(out_dir, "rand_0001.elf")
    tests.append(Test("hil/return_to_bootloader", "hil", lambda: hexed(hil.build_rand(1, out_dir)),
                      check=all_of(expect_tohost(1), hil_uart_check(elf, b"nexys_rv32 boot v1")),
                      max_cycles=50000000, long=True, plus=["+settle=400000"], do_cosim=False))
    for name, src in hil.rvtest_sources():
        elf = os.path.join(out_dir, "rv_%s.elf" % name)
        code = RV_EXPECT[name][0] if name in RV_EXPECT else 1
        tests.append(Test("hil/rv_" + name, "hil", lambda name=name, src=src: hexed(hil.build_rvtest(name, src, out_dir)),
                          check=all_of(expect_tohost(code), hil_uart_check(elf)), max_cycles=400000,
                          long=name not in HIL_QUICK_RV))
    return tests


def system_tests():
    T = []
    T.append(Test("system/hello", "system", lambda: build_sw("hello"),
                  check=expect_tohost(1, uart_contains("Hello from nexys_rv32!", "clock     : %d Hz" % P.cpu_hz,
                                                       "misa      : 40000100")),
                  max_cycles=3000000, long=True))

    def sl_check(tb, uart, work):
        ok = tb["led"] == "00a5" and "SW=1234" in uart and "SW=00a5" in uart and "BTND pressed" in uart
        return ok, "led=%s uart=%r" % (tb["led"], uart[-60:])
    T.append(Test("system/switches_leds", "system", lambda: build_sw("switches_leds"),
                  check=expect_tohost(1, sl_check), max_cycles=4000000, long=True,
                  plus=["+sw=1234", "+sw2=00a5", "+sw2_at=800000", "+btn=10", "+btn_at=1600000",
                        "+btn_len=400"]))

    def seg_check(tb, uart, work):
        ok = "count=25" in uart and tb["seg7_pins"] == "------25" and tb["seg7_reg"] == "00000025"
        return ok, "seg7 pins=%s reg=%s" % (tb["seg7_pins"], tb["seg7_reg"])
    T.append(Test("system/seg7_counter", "system",
                  lambda: build_sw("seg7_counter", "_sim", ("TICK_US=500", "MAX_COUNT=25")),
                  check=expect_tohost(1, seg_check), max_cycles=3000000, long=True,
                  plus=["+settle=1000000"]))

    def irq_check(tb, uart, work):
        ok = "ticks=20 (expected 20)" in uart and int(tb.get("irq_count", 0)) >= 20
        return ok, "irq count=%s latency %s..%s cycles" % (tb.get("irq_count"), tb.get("irq_lat_min"),
                                                           tb.get("irq_lat_max"))
    T.append(Test("system/timer_irq", "system",
                  lambda: build_sw("timer_irq", "_sim", ("PERIOD_US=200", "TICKS=20")),
                  check=expect_tohost(1, irq_check), max_cycles=3000000, long=True))

    def dhry_check(tb, uart, work):
        m = re.search(r"DHRY_STATS runs=(\d+) cycles=(\d+) instret=(\d+)", uart)
        ok = m is not None and "Int_Glob:            5" in uart and "should be:   DHRYSTONE PROGRAM, 2'ND STRING" in uart
        if not m:
            return False, "no DHRY_STATS"
        runs, cyc, ins = map(int, m.groups())
        return ok, "DMIPS/MHz=%.3f CPI=%.3f" % (1e6 * runs / (cyc * 1757.0), cyc / float(ins))
    T.append(Test("system/dhrystone", "system", lambda: build_sw("dhrystone", "_sim", ("NUMBER_OF_RUNS=200",)),
                  check=expect_tohost(1, dhry_check), max_cycles=20000000, long=True))

    def cm_check(tb, uart, work):
        m = re.search(r"CM_STATS iterations=(\d+) cycles=(\d+) instret=(\d+)", uart)
        ok = m is not None and coremark_crcs_ok(uart)
        if not m:
            return False, "no CM_STATS"
        it, cyc, ins = map(int, m.groups())
        return ok, "CoreMark/MHz=%.3f CPI=%.3f (%s)" % (it * 1e6 / cyc, cyc / float(ins),
                                                       "CRCs match reference" if ok else "CRC MISMATCH")
    T.append(Test("system/coremark", "system", lambda: build_sw("coremark", "_sim", ("ITERATIONS=2",)),
                  check=expect_tohost(1, cm_check), max_cycles=30000000, long=True))

    # second compiler: same programs built with clang, still lockstep with the ISS
    T.append(Test("system/clang_hello", "system", lambda: build_sw("hello", cc="clang"),
                  check=expect_tohost(1, uart_contains("Hello from nexys_rv32!")), max_cycles=3000000,
                  long=True, note="clang/lld build (second compiler)"))
    T.append(Test("system/clang_coremark", "system",
                  lambda: build_sw("coremark", "_sim", ("ITERATIONS=1",), cc="clang"),
                  check=expect_tohost(1, lambda tb, u, w: (coremark_crcs_ok(u), "CoreMark CRCs")),
                  max_cycles=30000000, long=True, note="clang/lld build (second compiler)"))

    # bootloader: real boot ROM from reset, program sent on the RX pin by the
    # byte stream host/rvload.py produces, at the real baud rate
    def boot_build():
        elf, hexf, _ = build_sw("hello", "_boot")    # own copy: tests build in parallel
        out = ensure(os.path.join(BUILD, "prog", "boot"))
        stream = os.path.join(out, "hello_stream.hex")
        rc, txt = py("host/rvload.py", "--emit-stream", stream, elf, "--no-verify")
        if rc:
            raise RuntimeError(txt)
        return elf, None, ["+uartin=" + stream, "+uartin_at=700000"]
    T.append(Test("system/bootloader_uart", "system", boot_build,
                  check=expect_tohost(1, uart_contains("nexys_rv32 boot v1", "Hello from nexys_rv32!")),
                  max_cycles=80000000, long=True, start_pc=P.reset_vector))
    return T


# =============================================================================
# static checks and unit tests (simulator independent or Icarus-based)
# =============================================================================
def static_checks(opts):
    res = []
    def add(name, ok, detail):
        res.append(dict(test=name, group="static", core="-", sim="-",
                        status="PASS" if ok else "FAIL", detail=detail.strip()[-600:]))

    def na(name, detail):
        res.append(dict(test=name, group="static", core="-", sim="-", status="N/A", detail=detail))
    rc, out = py("tools/gen_all.py", "--check")
    add("static/generated_files_current", rc == 0, out)
    rc, out = py("tools/check_rules.py", "--selftest")
    add("static/rule_checker_selftest", rc == 0, out.strip().splitlines()[-1] if out else "")
    rc, out = py("tools/check_rules.py")
    add("static/rule_checker", rc == 0, out)
    rc, out = py("tools/check_tcl.py", "--selftest")
    add("static/tcl_checker_selftest", rc == 0, out.strip().splitlines()[-1] if out else "")
    rc, out = py("tools/check_tcl.py")
    add("static/vivado_tcl_scripts", rc == 0, out)
    vl = which("verilator")
    if vl:
        for top, extra, gen in (("rv_soc", [], "-GCORE_PIPE=1"), ("rv_soc", [], "-GCORE_PIPE=0"),
                                ("fpga_top", [os.path.join(ROOT, "fpga/rtl/fpga_top.v"),
                                              os.path.join(HERE, "stubs", "xilinx_prims.v")], "")):
            cmd = [vl, "--lint-only", "-Wall", "--top-module", top] + ([gen] if gen else []) + \
                  ["-I" + os.path.join(ROOT, i) for i in RTL_INC] + RTL_FILES + extra
            rc, out = sh(cmd)
            warn = len(re.findall(r"^%Warning", out, re.M))
            tag = top + ("_pipe" if gen.endswith("=1") else "_mc" if gen else "")
            add("static/verilator_lint_wall_" + tag, rc == 0 and warn == 0,
                "%d warnings%s" % (warn, ("\n" + out[-500:]) if warn or rc else ""))
    else:
        na("static/verilator_lint_wall", "verilator not on PATH: lint runs in the WSL full regression "
           "(COMMANDS.md)")
    ys = which("yosys")
    if ys:
        rc, out = py("tools/yosys_check.py")
        add("static/yosys_no_latch_and_synth", rc == 0, out)
    else:
        na("static/yosys_no_latch_and_synth", "yosys not on PATH: the latch proof runs in the WSL full regression "
           "(COMMANDS.md)")
    return res


def docs_checks(opts):
    """Board material must match the code: sw/prebuilt must equal a fresh
    build, the board-mode riscv-tests environment must equal upstream's, the
    host tools must work through a serial device (tools/test_host.py; N/A on
    Windows), and the diagrams must pass the drawing rules
    (tools/check_diagrams.py)."""
    res = []
    rc, out = sh([sys.executable, "-c", "import sys; sys.path.insert(0, 'model'); import hil; "
                  "ok = hil.env_matches_upstream(); print('env_hil RVTEST_CODE_BEGIN equals upstream except "
                  "write_tohost: %s' % ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)"], cwd=ROOT)
    res.append(dict(test="docs/hil_env_matches_upstream", group="docs", core="-", sim="-",
                    status="PASS" if rc == 0 else "FAIL", detail=out.strip()[-600:]))
    rc, out = py("tools/check_diagrams.py", timeout=1800)
    res.append(dict(test="docs/diagram_rules", group="docs", core="-", sim="-",
                    status="PASS" if rc == 0 else "FAIL", detail=out.strip()[-600:]))
    rc, out = py("tools/make_prebuilt.py", "--check", timeout=1800)
    res.append(dict(test="docs/prebuilt_programs_current", group="docs", core="-", sim="-",
                    status="PASS" if rc == 0 else "FAIL", detail=out.strip()[-600:]))
    rc, out = py("tools/test_host.py", timeout=1800)
    skipped = "SKIPPED" in out
    res.append(dict(test="docs/host_tools_over_serial_port", group="docs", core="-", sim="-",
                    status="N/A" if skipped else ("PASS" if rc == 0 else "FAIL"), detail=out.strip()[-600:]))
    return res


def unit_tests(opts):
    res = []
    rc, out = py("sim/unit/run_unit.py", timeout=3600)
    for line in out.splitlines():
        m = re.match(r"UNIT (\S+) (PASS|FAIL) (.*)", line)
        if m:
            res.append(dict(test="unit/" + m.group(1), group="unit", core="-", sim="icarus",
                            status=m.group(2), detail=m.group(3)))
    if not res:
        res.append(dict(test="unit/run_unit", group="unit", core="-", sim="icarus", status="FAIL",
                        detail=out[-800:]))
    return res


# =============================================================================
# main
# =============================================================================
SIMS = {}


def main():
    ap = argparse.ArgumentParser(description="nexys_rv32 regression")
    ap.add_argument("--quick", action="store_true", help="skip long tests and use 4 random seeds")
    ap.add_argument("--sim", default="auto", help="comma list: verilator,icarus,xsim (default: all found)")
    ap.add_argument("--core", default="pipe,mc")
    ap.add_argument("--only", default=None, help="regex on test names")
    ap.add_argument("--jobs", type=int, default=max(1, multiprocessing.cpu_count()))
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--coverage", action="store_true", help="Verilator line/toggle coverage build")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-static", action="store_true")
    ap.add_argument("--keep-traces", action="store_true")
    a = ap.parse_args()

    cands = {"verilator": Verilator(a.coverage), "icarus": Icarus(), "xsim": Xsim()}
    want = list(cands) if a.sim == "auto" else a.sim.split(",")
    for s in want:
        if cands[s].available():
            SIMS[s] = cands[s]
        elif a.sim != "auto":
            raise SystemExit("simulator '%s' requested but not found on PATH" % s)
    if not SIMS:
        raise SystemExit("no simulator found (need verilator, iverilog/vvp or Vivado xsim on PATH)")
    cores = a.core.split(",")

    TESTS[:] = all_tests(a.quick, a.seeds)
    arch_env()      # written once here, before the parallel workers read it
    tests = [t for t in TESTS if not a.only or re.search(a.only, t.name)]
    jobs, na = [], []
    for t in tests:
        if t.na:
            na.append(dict(test=t.name, group=t.group, core="-", sim="-", status="N/A", detail=t.na,
                           note=t.na))
            continue
        for c in cores:
            if c not in t.cores:
                continue
            for s in SIMS:
                # Long tests (millions of cycles) run on Verilator only: Icarus and
                # xsim simulate this SoC at roughly 10 k cycles/s.
                if t.long and (a.quick or s != "verilator"):
                    continue
                jobs.append((TESTS.index(t), c, s, dict(timeout=a.timeout, keep_traces=a.keep_traces or a.coverage)))
    if a.list:
        for ti, c, s, _o in jobs:
            print("%-45s %-5s %s" % (TESTS[ti].name, c, s))
        print("%d runs" % len(jobs))
        return

    t0 = time.time()
    print("nexys_rv32 regression: simulators %s, cores %s, %d runs" % (",".join(SIMS), ",".join(cores), len(jobs)))
    # boot ROM image is needed by every test (the ISS loads it too)
    rc, out = sh([sys.executable, os.path.join(ROOT, "sw", "build.py"), "boot"])
    if rc:
        print(out)
        raise SystemExit("boot ROM build failed")
    results = []
    if not a.no_static and not a.only:
        results += static_checks(a)
        results += unit_tests(a)
        for r in results:
            print("%-4s %-50s %s" % (r["status"], r["test"], r["detail"].splitlines()[-1] if r["detail"] else ""))
    # build simulators once in the parent so workers reuse them
    for s in SIMS:
        for c in cores:
            for pc, raw in sorted(set((TESTS[ti].start_pc, TESTS[ti].ram_aw) for ti, cc, ss, _ in jobs
                                      if ss == s and cc == c)):
                SIMS[s].build(c, pc, raw)
    # build every test program once, then attach the result to each run
    need = sorted(set(j[0] for j in jobs))
    if a.jobs > 1 and len(need) > 1:
        with multiprocessing.Pool(a.jobs, initializer=init_worker,
                                  initargs=(list(SIMS), a.coverage, a.quick, a.seeds)) as pool:
            built = {ti: (b, err) for ti, b, err in pool.imap_unordered(build_one, need)}
    else:
        built = {ti: (b, err) for ti, b, err in map(build_one, need)}
    jobs = [j + (built[j[0]],) for j in jobs]
    if a.jobs > 1 and len(jobs) > 1:
        with multiprocessing.Pool(a.jobs, initializer=init_worker,
                                  initargs=(list(SIMS), a.coverage, a.quick, a.seeds)) as pool:
            for r in pool.imap_unordered(run_one, jobs):
                results.append(r)
                print("%-4s %-50s %-4s %-9s %s" % (r["status"], r["test"], r["core"], r["sim"], r["detail"][:110]))
    else:
        for j in jobs:
            r = run_one(j)
            results.append(r)
            print("%-4s %-50s %-4s %-9s %s" % (r["status"], r["test"], r["core"], r["sim"], r["detail"][:110]))

    if not a.no_static and not a.only and not a.coverage:
        results += docs_checks(a)
        for r in [x for x in results if x["group"] == "docs"]:
            print("%-4s %-50s %s" % (r["status"], r["test"], r["detail"].splitlines()[-1] if r["detail"] else ""))
    ensure(RESULTS)
    results += na
    fails = [r for r in results if r["status"] not in ("PASS", "N/A")]
    summary = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), seconds=round(time.time() - t0, 1),
                   simulators={s: tool_version(s) for s in SIMS}, compiler=compiler_version(),
                   total=len(results), passed=len([r for r in results if r["status"] == "PASS"]),
                   not_applicable=len([r for r in results if r["status"] == "N/A"]), failed=len(fails),
                   quick=a.quick, seeds=4 if a.quick else a.seeds, results=results)
    name = ("regression_coverage" if a.coverage else "regression_quick" if a.quick
            else "regression" if not a.only else "regression_partial")
    with open(os.path.join(RESULTS, name + ".json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    write_md(summary, os.path.join(RESULTS, name + ".md"))
    if a.coverage:
        py("tools/coverage_report.py")
    print("")
    print("%d checks/runs: %d passed, %d not applicable (documented), %d failed, %.0f s"
          % (len(results), summary["passed"], summary["not_applicable"], len(fails), time.time() - t0))
    if fails:
        for r in fails:
            print("FAIL %s [%s/%s] %s" % (r["test"], r["core"], r["sim"], r["detail"][:300]))
        sys.exit(1)
    print("ALL PASS")


def tool_version(s):
    exe = {"verilator": which("verilator"), "icarus": which("iverilog"), "xsim": which("xsim")}[s]
    flag = {"verilator": "--version", "icarus": "-V", "xsim": "-version"}[s]
    rc, out = sh([exe, flag]) if exe else (1, "")
    return out.strip().splitlines()[0] if out.strip() else "?"


def compiler_version():
    g = which(CROSS + "gcc")
    if not g:
        return "?"
    rc, out = sh([g, "--version"])
    return out.splitlines()[0] if out else "?"


def write_md(s, path):
    groups = {}
    for r in s["results"]:
        k = (r["group"], r["sim"], r["core"])
        g = groups.setdefault(k, [0, 0])
        g[0] += 1
        g[1] += r["status"] == "PASS"
    lines = ["# Regression results", "",
             "Generated by `sim/run_sim.py` on %s in %.0f s. Do not edit." % (s["date"], s["seconds"]), "",
             "Simulators: " + ", ".join("%s (%s)" % kv for kv in s["simulators"].items()), "",
             "Compiler: " + s["compiler"], "",
             "| Group | Simulator | Core | Passed / Run |", "|---|---|---|---|"]
    for (g, sim, core), (n, ok) in sorted(groups.items()):
        lines.append("| %s | %s | %s | %d / %d |" % (g, sim, core, ok, n))
    lines += ["", "**%d passed, %d not applicable, %d failed (of %d).**"
              % (s["passed"], s["not_applicable"], s["failed"], s["total"]), ""]
    notes = sorted(set((r["test"], r["note"]) for r in s["results"] if r.get("note")))
    if notes:
        lines += ["## Notes", ""] + ["- `%s`: %s" % n for n in notes] + [""]
    fails = [r for r in s["results"] if r["status"] not in ("PASS", "N/A")]
    if fails:
        lines += ["## Failures", ""] + ["- `%s` [%s/%s]: %s" % (r["test"], r["core"], r["sim"], r["detail"][:200])
                                       for r in fails]
    open(path, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
