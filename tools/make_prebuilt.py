#!/usr/bin/env python3
# =============================================================================
# make_prebuilt.py - ready-made programs for board day (sw/prebuilt/)
# -----------------------------------------------------------------------------
# Purpose : Board day must not depend on the compiler install. This script
#           builds every program the board needs with GCC and keeps the ELF
#           files in sw/prebuilt/, with a manifest of how each was made.
#             <app>.elf         interactive programs (hello, switches_leds,
#                               seg7_counter, timer_irq, dhrystone, coremark)
#             <name>_board.elf  the variants host/board_bench.py runs
#                               (benchmarks long enough for a valid result)
#             hil/              the on-board self-test set (model/hil.py):
#                               probe, HIL_SEEDS random programs, riscv-tests
#             boot.elf          the boot ROM image, used by the software
#                               board (rvload --port sim) when sw/build is absent
# Usage   : py tools/make_prebuilt.py           build and write sw/prebuilt/
#           py tools/make_prebuilt.py --check   rebuild in a temporary folder
#                                               and check every shipped ELF
#                                               loads exactly the same bytes
# Needs   : riscv-none-elf-gcc (the check is skipped with a note without it)
# =============================================================================
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "sw", "prebuilt")
sys.path.insert(0, os.path.join(ROOT, "model"))
sys.path.insert(0, os.path.join(ROOT, "host"))
import elf as elf_mod  # noqa: E402

HIL_SEEDS = 100      # random programs for the on-board self-test
APPS = ["hello", "switches_leds", "seg7_counter", "timer_irq", "dhrystone", "coremark"]


def board_programs():
    import board_bench
    return [(name, defs) for name, defs, _, _ in board_bench.PROGRAMS]


def build(target, defs, out):
    cmd = [sys.executable, os.path.join(ROOT, "sw", "build.py"), target, "--out", out, "--no-bootrom"]
    for d in defs:
        cmd += ["-D", d]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode:
        raise SystemExit("build of %s failed:\n%s" % (target, r.stdout[-2000:]))
    return os.path.join(out, target, target + ".elf")


def image_digest(path):
    """sha256 over the loadable bytes and addresses: what the board receives."""
    h = hashlib.sha256()
    e = elf_mod.load(path)
    for addr, data, memsz in e.segments:
        if memsz:
            h.update(("%08x:%d:" % (addr, memsz)).encode())
            h.update(bytes(data))
    h.update(("entry %08x" % e.entry).encode())
    return h.hexdigest()[:16]


def all_items():
    items = [(a + ".elf", a, []) for a in APPS]
    items += [(n + "_board.elf", n, d) for n, d in board_programs()]
    return items


def gcc_version():
    gcc = shutil.which("riscv-none-elf-gcc")
    if not gcc:
        return None
    r = subprocess.run([gcc, "--version"], stdout=subprocess.PIPE, universal_newlines=True)
    return r.stdout.splitlines()[0]


def main():
    check = "--check" in sys.argv
    ver = gcc_version()
    if not ver:
        print("prebuilt: riscv-none-elf-gcc not on PATH; %s skipped" % ("check" if check else "build"))
        sys.exit(0 if check else 1)
    tmp = tempfile.mkdtemp(prefix="nrv_prebuilt_")
    try:
        bad, lines = [], []
        for fname, target, defs in all_items():
            elf = build(target, defs, os.path.join(tmp, fname[:-4]))
            dig = image_digest(elf)
            dst = os.path.join(OUT, fname)
            if check:
                if not os.path.exists(dst):
                    bad.append(fname + " missing")
                elif image_digest(dst) != dig:
                    bad.append(fname + " differs from a fresh build")
            else:
                os.makedirs(OUT, exist_ok=True)
                shutil.copyfile(elf, dst)
                lines.append("%-24s %s  %s" % (fname, dig, " ".join("-D" + d for d in defs) or "(default)"))
        # the on-board self-test set (host/board_hil.py): probe, random programs, riscv-tests
        import hil
        hil_tmp = os.path.join(tmp, "hil")
        hil_items = [("hil/probe.elf", lambda: hil.build_probe(hil_tmp))]
        hil_items += [("hil/rand_%04d.elf" % sd, lambda sd=sd: hil.build_rand(sd, hil_tmp))
                      for sd in range(1, HIL_SEEDS + 1)]
        hil_items += [("hil/rv_%s.elf" % n, lambda n=n, sr=sr: hil.build_rvtest(n, sr, hil_tmp))
                      for n, sr in hil.rvtest_sources()]
        if not check:
            if os.path.isdir(os.path.join(OUT, "hil")):
                shutil.rmtree(os.path.join(OUT, "hil"))
            os.makedirs(os.path.join(OUT, "hil"))
        for fname, make in hil_items:
            elf = make()
            dst = os.path.join(OUT, fname)
            if check:
                if not os.path.exists(dst):
                    bad.append(fname + " missing")
                elif image_digest(dst) != image_digest(elf):
                    bad.append(fname + " differs from a fresh build")
            else:
                shutil.copyfile(elf, dst)
        if not check:
            lines.append("%-24s %d programs (probe, %d random, %d riscv-tests); digests in hil/MANIFEST.txt"
                         % ("hil/", len(hil_items), HIL_SEEDS, len(hil_items) - 1 - HIL_SEEDS))
            with open(os.path.join(OUT, "hil", "MANIFEST.txt"), "w", newline="\n") as fh:
                fh.write("GENERATED FILE - DO NOT EDIT. Made by tools/make_prebuilt.py\n")
                for fname, _ in hil_items:
                    fh.write("%-32s %s\n" % (os.path.basename(fname), image_digest(os.path.join(OUT, fname))))
        n_hil = len(hil_items)
        # the boot ROM image, for the software board (rvload --port sim) without a compiler
        boot = os.path.join(ROOT, "sw", "build", "boot", "boot.elf")
        if check:
            if image_digest(os.path.join(OUT, "boot.elf")) != image_digest(boot):
                bad.append("boot.elf differs from sw/build/boot/boot.elf")
        else:
            shutil.copyfile(boot, os.path.join(OUT, "boot.elf"))
            lines.append("%-24s %s  %s" % ("boot.elf", image_digest(boot), "boot ROM image (copy of sw/build/boot)"))
        if check:
            print("prebuilt: %d files %s" % (len(all_items()) + 1 + n_hil, "match a fresh build: PASS" if not bad
                                                 else "FAIL: " + "; ".join(bad)))
            sys.exit(1 if bad else 0)
        with open(os.path.join(OUT, "MANIFEST.txt"), "w", newline="\n") as fh:
            fh.write("GENERATED FILE - DO NOT EDIT. Made by tools/make_prebuilt.py\n")
            fh.write("Compiler: %s\n" % ver)
            fh.write("Digest = sha256/16 of the bytes the bootloader loads (addresses, data, entry).\n\n")
            fh.write("\n".join(lines) + "\n")
        print("prebuilt: %d programs in sw/prebuilt (%s)" % (len(lines), ver))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
