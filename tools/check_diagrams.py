#!/usr/bin/env python3
# =============================================================================
# check_diagrams.py - the block, flow and state diagrams obey the drawing rules
# -----------------------------------------------------------------------------
# Purpose : 1. the diagram rule checker itself works (tools/diagram.py
#              self-test: diagonal, crossing, line through a block, text on
#              a line or outline, lines too close are all rejected);
#           2. every diagram of tools/make_diagrams.py passes those rules
#              (redrawn into a temporary folder).
# Usage   : py tools/check_diagrams.py
# =============================================================================
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def run(args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run([sys.executable] + args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True, env=e)
    return r.returncode, r.stdout


def main():
    errs = []
    rc, out = run([os.path.join("tools", "diagram.py")])
    print(out.strip())
    if rc:
        errs.append("diagram rule checker self-test failed")
    tmp = tempfile.mkdtemp()
    rc, out = run([os.path.join("tools", "make_diagrams.py")], {"NRV_FIG_OUT": tmp})
    print(out.strip().splitlines()[-1] if out.strip() else "")
    if rc:
        errs.append("a diagram breaks the drawing rules:\n" + out[-1500:])
    for e in errs:
        print("FAIL " + e)
    print("check_diagrams: %s" % ("PASS" if not errs else "%d problem(s)" % len(errs)))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
