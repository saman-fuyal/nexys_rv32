#!/usr/bin/env python3
# =============================================================================
# check_tcl.py - static check of the Vivado Tcl scripts (no Vivado needed)
# -----------------------------------------------------------------------------
# Purpose : Catch the mistakes that would only show up on build day: an
#           unbalanced brace or bracket, an unterminated string, or a command
#           name that is neither core Tcl, a proc defined in the scripts, nor a
#           Vivado command used in this project's 2018.2 flow.
# Behavior: Splits each script into commands the way Tcl does (braces, quotes,
#           brackets, backslash-newline, ';' and newlines), checks nesting, and
#           checks the first word of every command and of every [ ] command
#           substitution. Scripts inside braces (if/for/proc bodies) are
#           checked recursively.
# Limits  : It is not a Tcl interpreter: wrong arguments to a valid command
#           are not found. The list of Vivado commands is the set this flow
#           relies on, all present in Vivado 2018.2 (UG835 command reference).
# Usage   : py tools/check_tcl.py [--selftest]
# =============================================================================
import glob
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

TCL_CORE = set("""
after append array break catch cd clock close concat continue dict else elseif encoding eof error eval exec exit
expr fconfigure file flush for foreach format gets glob global if incr info join lappend lassign lindex linsert list
llength lmap lrange lrepeat lreplace lreverse lsearch lset lsort namespace open package proc puts pwd read regexp
regsub rename return scan seek set source split string subst switch tell then time trace unset update uplevel
upvar variable vwait while
""".split())

VIVADO = set("""
read_verilog read_xdc synth_design write_checkpoint report_utilization report_timing_summary opt_design
place_design phys_opt_design route_design report_timing report_clock_utilization report_drc report_methodology
report_power get_timing_paths get_property get_clocks get_cells version write_bitstream set_property
open_hw open_hw_manager close_hw close_hw_manager connect_hw_server disconnect_hw_server refresh_hw_server
get_hw_targets current_hw_target open_hw_target close_hw_target get_hw_devices current_hw_device
refresh_hw_device program_hw_devices write_cfgmem get_cfgmem_parts create_hw_cfgmem create_hw_bitstream
program_hw_cfgmem boot_hw_device get_hw_cfgmems
""".split())

KEYWORD_ARGS = {"else", "elseif", "then"}


class TclError(Exception):
    pass


def split_commands(text, line0=1):
    """Yield (line, [words]) for each command; words keep their delimiters."""
    i, n, line = 0, len(text), line0
    words, word, start_line = [], "", line0
    depth_b = 0

    def flush_word():
        nonlocal word
        if word:
            words.append(word)
            word = ""

    while i < n:
        c = text[i]
        if not words and not word and c in " \t":
            i += 1
            continue
        if not words and not word and c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "\\" and i + 1 < n:
            if text[i + 1] == "\n":
                flush_word()
                i += 2
                line += 1
                continue
            word += text[i:i + 2]
            i += 2
            continue
        if c == "{" and not word:
            depth_b, j = 1, i + 1
            while j < n and depth_b:
                if text[j] == "\\":
                    j += 2
                    continue
                depth_b += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            if depth_b:
                raise TclError("line %d: unbalanced '{'" % line)
            word = text[i:j]
            line += word.count("\n")
            i = j
            if i < n and text[i] not in " \t\n;]":
                raise TclError("line %d: extra characters after close-brace" % line)
            continue
        if c == '"' and not word:
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    j = skip_bracket(text, j, line)
                    continue
                j += 1
            if j >= n:
                raise TclError("line %d: unterminated string" % line)
            word = text[i:j + 1]
            line += word.count("\n")
            i = j + 1
            continue
        if c == "[":
            j = skip_bracket(text, i, line)
            word += text[i:j]
            line += text[i:j].count("\n")
            i = j
            continue
        if c in " \t":
            flush_word()
            i += 1
            continue
        if c in "\n;":
            flush_word()
            if words:
                yield start_line, words
            words = []
            if c == "\n":
                line += 1
            start_line = line
            i += 1
            continue
        if c == "}":
            raise TclError("line %d: unexpected '}'" % line)
        word += c
        i += 1
    flush_word()
    if words:
        yield start_line, words


def skip_bracket(text, i, line):
    depth, j, n = 0, i, len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                return j + 1
        elif text[j] == "{":
            d2, k = 1, j + 1
            while k < n and d2:
                if text[k] == "\\":
                    k += 2
                    continue
                d2 += {"{": 1, "}": -1}.get(text[k], 0)
                k += 1
            j = k
            continue
        j += 1
    raise TclError("line %d: unbalanced '['" % line)


def bracket_cmds(word):
    """First word of every [ ] substitution in a word (outside braces)."""
    out = []
    for m in re.finditer(r"\[\s*([A-Za-z_][\w:]*)", word):
        out.append(m.group(1))
    return out


BODY_ARGS = {"if": None, "for": None, "foreach": -1, "while": -1, "proc": -1, "catch": 0}


def check_script(text, known, path, line0=1, errors=None):
    errors = [] if errors is None else errors
    try:
        cmds = list(split_commands(text, line0))
    except TclError as e:
        errors.append("%s: %s" % (path, e))
        return errors
    for line, words in cmds:
        name = words[0]
        if name.startswith("[") or name.startswith("$"):
            name = None
        if name and name not in known:
            errors.append("%s:%d: unknown command '%s'" % (path, line, name))
        for w in words:
            if w.startswith("{"):
                continue
            for b in bracket_cmds(w):
                if b not in known:
                    errors.append("%s:%d: unknown command '%s' in [ ]" % (path, line, b))
        # recurse into script bodies
        bodies = []
        if name in ("if",):
            for k, w in enumerate(words):
                if w.startswith("{") and k > 1 and words[k - 1] not in ("if", "elseif"):
                    bodies.append(w)
                if k >= 1 and words[k - 1] in ("if", "elseif") and w.startswith("{"):
                    check_expr(w, known, path, line, errors)
        elif name in ("for",):
            bodies = [w for k, w in enumerate(words) if w.startswith("{") and k in (1, 3, 4)]
        elif name in ("foreach", "while", "proc", "catch"):
            if words[-1].startswith("{"):
                bodies = [words[-1]] if name != "catch" else [words[1]] if words[1].startswith("{") else []
        for b in bodies:
            check_script(b[1:-1], known, path, line, errors)
    return errors


def check_expr(word, known, path, line, errors):
    for b in bracket_cmds(word):
        if b not in known:
            errors.append("%s:%d: unknown command '%s' in condition" % (path, line, b))


def procs_in(texts):
    names = set()
    for t in texts:
        names.update(re.findall(r"^\s*proc\s+([\w:]+)", t, re.M))
    return names


def run(paths):
    texts = {p: open(p, encoding="utf-8").read() for p in paths}
    known = TCL_CORE | VIVADO | procs_in(texts.values())
    errs = []
    for p, t in texts.items():
        check_script(t, known, os.path.relpath(p, ROOT), 1, errs)
    return errs


def selftest():
    import tempfile
    bad = {
        "brace.tcl": "if {1} {\n puts x\n",
        "bracket.tcl": "set a [get_property X [get_cells y]\n",
        "string.tcl": "puts \"abc\n",
        "unknown.tcl": "open_hw\nopen_hw_targett\n",
        "unknown_in_bracket.tcl": "set d [get_hw_device xc7*]\n",
        "unknown_in_body.tcl": "proc p {} {\n  conect_hw_server\n}\np\n",
    }
    good = "proc p {a} {\n  if {[llength $a] > 0} { puts \"n=[llength $a]\" } else { error \"none\" }\n}\np {1 2}\n"
    d = tempfile.mkdtemp()
    ok = True
    for name, text in bad.items():
        f = os.path.join(d, name)
        open(f, "w").write(text)
        caught = bool(run([f]))
        ok &= caught
        print("selftest %-24s %s" % (name, "caught" if caught else "NOT caught"))
    f = os.path.join(d, "good.tcl")
    open(f, "w").write(good)
    e = run([f])
    print("selftest %-24s %s" % ("good.tcl", "clean" if not e else "false alarm: %s" % e))
    ok &= not e
    return ok


def main():
    if "--selftest" in sys.argv:
        ok = selftest()
        print("check_tcl self-test: %s" % ("PASS" if ok else "FAIL"))
        sys.exit(0 if ok else 1)
    paths = sorted(glob.glob(os.path.join(ROOT, "fpga", "scripts", "*.tcl")))
    errs = run(paths)
    for e in errs:
        print(e)
    print("check_tcl: %d file(s), %d problem(s)" % (len(paths), len(errs)))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
