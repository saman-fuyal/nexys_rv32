#!/usr/bin/env python3
# =============================================================================
# build.py - build the boot ROM and the C programs (Windows, Linux, WSL)
# -----------------------------------------------------------------------------
# Purpose : One build script that needs only Python and a RISC-V compiler, so
#           Windows users do not need make. sw/Makefile and sw/build.bat call
#           this script.
# Behavior: For each target, compiles and links with -march/-mabi from
#           params.json, writes <target>.elf/.hex/.bin/.lst/.map into
#           sw/build/<target>/, and prints the size. The boot target also
#           regenerates rtl/gen/bootrom.v. Generated headers are refreshed
#           first (tools/gen_all.py), so the build always matches params.json.
#           --cc clang builds the same sources with clang/lld (used as a
#           second-compiler cross-check of the core; libgcc is then replaced
#           by sw/lib/rt_arith.c).
# Usage   : py sw/build.py [targets...] [--cc gcc|clang] [--cross PREFIX]
#                          [--out DIR] [-D NAME=VALUE ...] [--opt -O2]
#           targets: boot hello switches_leds seg7_counter timer_irq
#                    dhrystone coremark   (default: all)
# =============================================================================
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "model"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import params as params_mod  # noqa: E402

LIB = ["lib/crt0.S", "lib/rt_io.c", "lib/rt_printf.c", "lib/rt_sys.c"]
CM = ["third_party/coremark/" + f for f in
      ("core_list_join.c", "core_main.c", "core_matrix.c", "core_state.c", "core_util.c")]

# Per-target: sources (relative to sw/), extra include dirs, extra flags, defines
TARGETS = {
    "boot": dict(src=["boot/boot_start.S", "boot/boot.c"], lib=False, ld="link/boot.ld",
                 opt="-Os", flags=["-msmall-data-limit=0", "-fno-jump-tables"]),
    "hello": dict(src=["apps/hello/main.c"]),
    "switches_leds": dict(src=["apps/switches_leds/main.c"]),
    "seg7_counter": dict(src=["apps/seg7_counter/main.c"]),
    "timer_irq": dict(src=["apps/timer_irq/main.c"]),
    "dhrystone": dict(src=["third_party/dhrystone/dhrystone.c", "third_party/dhrystone/dhrystone_main.c",
                           "apps/dhrystone/stats.c"],
                      inc=["apps/dhrystone", "third_party/dhrystone"],
                      opt="-O3", flags=["-fno-inline", "-std=gnu89", "-Wno-implicit-int",
                                        "-Wno-implicit-function-declaration", "-Wno-return-type",
                                        "-Wno-old-style-definition", "-Wno-unused", "-w"],
                      defs={"NUMBER_OF_RUNS": "500"}),
    "coremark": dict(src=CM + ["apps/coremark/core_portme.c"],
                     inc=["apps/coremark", "third_party/coremark"],
                     opt="-O2", flags=["-funroll-loops", "-w"],
                     defs={"ITERATIONS": "2", "PERFORMANCE_RUN": "1", "TOTAL_DATA_SIZE": "2000"}),
}
ALL = ["boot", "hello", "switches_leds", "seg7_counter", "timer_irq", "dhrystone", "coremark"]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    if r.returncode != 0:
        sys.stderr.write(" ".join(cmd) + "\n" + r.stdout)
        raise SystemExit("build failed")
    return r.stdout


def find_tool(name):
    p = shutil.which(name) or shutil.which(name + ".exe")
    if not p:
        raise SystemExit("cannot find '%s' on PATH (see COMMANDS.md, 'One-time setup')" % name)
    return p


def build(target, a, P):
    t = TARGETS[target]
    out = os.path.join(a.out, target)
    os.makedirs(out, exist_ok=True)
    opt = a.opt or t.get("opt", "-O2")
    defs = dict(t.get("defs", {}))
    for d in a.define:
        k, _, v = d.partition("=")
        defs[k] = v or "1"
    common = ["-march=" + P.march, "-mabi=" + P.mabi, opt, "-g", "-Wall", "-Wextra",
              "-ffreestanding", "-fno-common", "-ffunction-sections", "-fdata-sections",
              "-I" + os.path.join(HERE, "include")]
    for i in t.get("inc", []):
        common.append("-I" + os.path.join(HERE, i))
    for k, v in defs.items():
        common.append("-D%s=%s" % (k, v))
    flags_str = " ".join([opt] + t.get("flags", []))
    if target == "coremark":
        common.append('-DCOMPILER_FLAGS="%s"' % flags_str)
    if a.cc == "clang":
        cc = [find_tool("clang"), "--target=riscv32-unknown-elf"]
        ldflags = ["-fuse-ld=lld", "-nostdlib", "-static"]
        libflags = ["-fno-builtin"]
        tail = []
    else:
        cc = [find_tool(a.cross + "gcc")]
        ldflags = ["-nostdlib", "-nostartfiles", "-static"]
        libflags = ["-fno-tree-loop-distribute-patterns"]   # keep memset() from calling itself
        tail = ["-lgcc"]
    srcs = [os.path.join(HERE, s) for s in t["src"]]
    if t.get("lib", True):
        srcs += [os.path.join(HERE, s) for s in LIB]
        if a.cc == "clang":
            srcs.append(os.path.join(HERE, "lib", "rt_arith.c"))
    objs = []
    for s in srcs:
        o = os.path.join(out, os.path.basename(s) + ".o")
        is_lib = "/lib/" in s.replace("\\", "/")
        # target flags (e.g. Dhrystone's -std=gnu89) apply to the target's own sources only
        extra = libflags if is_lib else t.get("flags", [])
        if "third_party" not in s.replace("\\", "/"):
            extra = extra + ["-Werror"]          # our own code builds warning-free
        run(cc + common + extra + ["-c", s, "-o", o])
        objs.append(o)
    elf = os.path.join(out, target + ".elf")
    ld = os.path.join(HERE, t.get("ld", "link/app.ld"))
    run(cc + common + ldflags + ["-T", ld, "-Wl,--gc-sections", "-Wl,-Map=" + os.path.join(out, target + ".map")]
        + objs + tail + ["-o", elf])
    objdump = (shutil.which("llvm-objdump") if a.cc == "clang" else shutil.which(a.cross + "objdump"))
    if objdump:
        with open(os.path.join(out, target + ".lst"), "w") as fh:
            fh.write(run([objdump, "-d", "-S" if a.cc != "clang" else "-d", elf]))
    import elf2hex
    if target == "boot":
        import gen_bootrom
        words, used, digest = gen_bootrom.build_words(P, elf)
        print("%-14s %6d bytes of %d ROM bytes" % (target, used * 4, P.rom["size"]))
    else:
        e, img = elf2hex.ram_image(P, elf)
        with open(os.path.join(out, target + ".hex"), "w", newline="\n") as fh:
            fh.write("@00000000\n")
            for i in range(0, len(img), 4):
                fh.write("%08x\n" % int.from_bytes(img[i:i + 4], "little"))
        with open(os.path.join(out, target + ".bin"), "wb") as fh:
            fh.write(img)
        print("%-14s %6d bytes, entry 0x%08x  (%s %s)" % (target, len(img), e.entry, a.cc, flags_str))
    return elf


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--cc", default="gcc", choices=["gcc", "clang"])
    ap.add_argument("--cross", default=None, help="GCC prefix (default from params.json)")
    ap.add_argument("--out", default=os.path.join(HERE, "build"))
    ap.add_argument("-D", dest="define", action="append", default=[])
    ap.add_argument("--opt", default=None)
    ap.add_argument("--no-bootrom", action="store_true", help="do not regenerate rtl/gen/bootrom.v")
    a = ap.parse_args()
    P = params_mod.load()
    if a.cross is None:
        a.cross = P.cross_prefix
    run([sys.executable, os.path.join(ROOT, "tools", "gen_all.py")])
    for tname in a.targets or ALL:
        if tname not in TARGETS:
            raise SystemExit("unknown target '%s' (have: %s)" % (tname, " ".join(ALL)))
        elf = build(tname, a, P)
        if tname == "boot" and not a.no_bootrom:
            print(run([sys.executable, os.path.join(ROOT, "tools", "gen_bootrom.py"), "--elf", elf]).strip())


if __name__ == "__main__":
    main()
