#!/usr/bin/env python3
# =============================================================================
# package.py - make the delivery zip
# -----------------------------------------------------------------------------
# Purpose : One zip with everything needed to rebuild and re-verify the
#           project, and nothing that the scripts regenerate locally.
# Behavior: Walks the project, skips build output (sim/build, sw/build*,
#           fpga/build), Python caches and VCD dumps, and writes
#           nexys_rv32.zip with the top folder nexys_rv32/. Generated files
#           that the documents need (docs/*, rtl/gen/*, results/*) are kept.
# Usage   : py tools/package.py [OUT.zip]
# =============================================================================
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKIP_DIRS = {os.path.join("sim", "build"), os.path.join("fpga", "build"), "__pycache__", ".git"}
SKIP_PREFIX = (os.path.join("sw", "build"),)
SKIP_EXT = (".pyc", ".vcd", ".vvp", ".o")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "nexys_rv32.zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(ROOT):
            rel = os.path.relpath(d, ROOT)
            dirs[:] = sorted(x for x in dirs if os.path.normpath(os.path.join(rel, x)) not in SKIP_DIRS
                             and x not in SKIP_DIRS
                             and not os.path.normpath(os.path.join(rel, x)).startswith(SKIP_PREFIX))
            for f in sorted(files):
                if f.endswith(SKIP_EXT) or f.startswith(("regression_partial.", "regression_quick.")):
                    continue
                p = os.path.join(d, f)
                z.write(p, os.path.join("nexys_rv32", os.path.relpath(p, ROOT)))
                n += 1
    print("package: %s (%d files, %.1f MB)" % (out, n, os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    main()
