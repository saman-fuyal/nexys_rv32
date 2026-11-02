#!/usr/bin/env python3
# =============================================================================
# check_rules.py - enforce the project's Verilog coding rules on RTL files
# -----------------------------------------------------------------------------
# Purpose : Mechanical check of the RTL coding rules.
#           Each violation prints  <file>:<line>: [Rn] message  and the script
#           exits 1. Yosys and Verilator prove latch-freedom and lint; this
#           script checks the style rules those tools do not know about.
# Rules   :
#   R1  synthesizable: no initial, no # delays, no forever/while/repeat/wait/
#       fork, no system tasks except $signed/$unsigned, for-loops only with
#       a constant bound
#   R2  no latches by construction: every always @(*) assigns each of its
#       outputs unconditionally before any if/case, and every case has a
#       default
#   R3  sequential/combinational separation: always @(*) uses only '=',
#       always @(posedge clk) uses only '<=' with a plain right-hand side
#       (identifier, constant or indexed identifier: no logic in flops)
#   R4  sections '//== Ports', '//== Localparams/Wires',
#       '//== Combinational Logic', '//== Sequential Logic' in that order
#   R5  plain Verilog-2001: no SystemVerilog keywords or operators
#   R6  `default_nettype none first, `default_nettype wire last, a header
#       comment with Purpose and Behavior, _q names only for flops, flops
#       named *_q (memories *_mem)
#   R7  one clock: only 'posedge clk'; synchronous reset (no reset in the
#       sensitivity list)
#   R8  generated files carry 'GENERATED FILE - DO NOT EDIT'; every verilator
#       lint_off in a .v file has a 'Waiver:' comment within 3 lines above
# Usage   : py tools/check_rules.py [files...]       (default: all RTL)
#           py tools/check_rules.py --selftest        (prove on tools/rule_tests)
# =============================================================================
import glob
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RTL_GLOBS = ["rtl/core/*.v", "rtl/soc/*.v", "rtl/periph/*.v", "rtl/gen/*.v", "fpga/rtl/*.v"]
HDR_GLOBS = ["rtl/core/*.vh", "rtl/gen/*.vh"]
GENERATED = ("rtl/gen/",)

SV_WORDS = ["logic", "bit", "byte", "int", "shortint", "longint", "always_ff", "always_comb",
            "always_latch", "typedef", "enum", "struct", "union", "interface", "modport",
            "package", "import", "unique", "priority", "final", "automatic", "assert",
            "assume", "cover", "property", "sequence", "class", "string", "void"]
SECTIONS = ["//== Ports", "//== Localparams/Wires", "//== Combinational Logic", "//== Sequential Logic"]
KEYWORDS = set("""module endmodule input output inout wire reg integer genvar parameter localparam
assign always begin end if else case endcase default for generate endgenerate function
endfunction posedge negedge or and not""".split())


class Report(object):
    def __init__(self):
        self.items = []

    def add(self, path, line, rule, msg):
        self.items.append((path, line, rule, msg))


def strip_comments(text):
    """Remove comments and strings but keep line structure."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append('"' + " " * (min(j, n) - i - 1) + '"')
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def find_blocks(code):
    """Yield (kind, start_pos, body_text, body_start) for each always block."""
    for m in re.finditer(r"\balways\s*@\s*(\(\s*\*\s*\)|\*|\([^)]*\))\s*", code):
        sens = m.group(1)
        p = m.end()
        if code.startswith("begin", p):
            depth, q = 0, p
            for t in re.finditer(r"\b(begin|end|case|endcase|function|endfunction)\b", code[p:]):
                w = t.group(1)
                if w in ("begin", "case", "function"):
                    depth += 1
                else:
                    depth -= 1
                if depth == 0:
                    q = p + t.end()
                    break
            body = code[p + 5:q - 3]
            bstart = p + 5
        else:
            q = code.find(";", p) + 1
            body = code[p:q]
            bstart = p
        yield sens, m.start(), body, bstart


def lhs_name(stmt):
    m = re.match(r"\s*([A-Za-z_][\w]*)", stmt)
    return m.group(1) if m else None


def check_comb_block(path, code, body, bstart, rep):
    """R2: default-first assignment and case defaults; R3: blocking only."""
    for m in re.finditer(r"(^|;|\bbegin\b|\belse\b|\)|:)\s*([A-Za-z_]\w*(\s*\[[^\]]*\])*)\s*<=", body, re.M):
        rep.add(path, line_of(code, bstart + m.start(2)), "R3",
                "non-blocking '<=' inside always @(*)")
    tokens = re.finditer(r"\b(begin|end|if|else|case|endcase|default|for)\b|;|=(?!=)", body)
    # Walk statements: track whether we are inside a conditional construct.
    depth_cond = 0
    stack = []
    top_assigned = set()
    pos_stmt_start = 0
    pending_if = False
    for t in tokens:
        tok = t.group(0)
        if tok in ("if", "for"):
            pending_if = True
        elif tok == "case":
            stack.append("case")
            depth_cond += 1
        elif tok == "endcase":
            if stack and stack[-1] == "case":
                stack.pop()
                depth_cond -= 1
        elif tok == "begin":
            stack.append("cbegin" if pending_if else "begin")
            if pending_if:
                depth_cond += 1
            pending_if = False
        elif tok == "end":
            if stack:
                k = stack.pop()
                if k == "cbegin":
                    depth_cond -= 1
        elif tok == "else":
            pending_if = True
        elif tok == "=":
            prev = body[t.start() - 1] if t.start() else ""
            if prev in "<>!=":
                continue
            stmt_start = max(body.rfind(";", 0, t.start()), body.rfind("begin", 0, t.start()) + 4,
                             body.rfind("end", 0, t.start()) + 2, body.rfind(":", 0, t.start()),
                             body.rfind(")", 0, t.start()) if pending_if else -1, 0)
            seg = body[stmt_start + 1 if stmt_start else 0:t.start()]
            seg = re.sub(r"\b(else|begin|end|default)\b", " ", seg)
            name = lhs_name(seg.split(")")[-1])
            if not name or name in KEYWORDS:
                continue
            in_cond = depth_cond > 0 or pending_if
            if not in_cond:
                top_assigned.add(name)
            elif name not in top_assigned:
                rep.add(path, line_of(code, bstart + t.start()), "R2",
                        "'%s' assigned under a condition without a default assignment first" % name)
        elif tok == ";":
            pending_if = False


def check_case_defaults(path, code, rep):
    """R2: every case (in always blocks and functions) has a default at its own level."""
    for m in re.finditer(r"\bcase\b", code):
        depth, has_default = 0, False
        for t in re.finditer(r"\b(case|endcase|default)\b", code[m.start():]):
            w = t.group(1)
            if w == "case":
                depth += 1
            elif w == "endcase":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1:
                has_default = True
        if not has_default:
            rep.add(path, line_of(code, m.start()), "R2", "case without default")


def check_seq_block(path, code, sens, body, bstart, rep):
    if not re.fullmatch(r"\(\s*posedge\s+clk\s*\)", sens.strip()):
        rep.add(path, line_of(code, bstart), "R7",
                "sensitivity must be exactly @(posedge clk) (single clock, synchronous reset)")
    for m in re.finditer(r"(?<![<>=!])=(?!=)", body):
        # '=' that is not part of '<=', '==', '>=', '!='
        before = body[max(0, m.start() - 1)]
        if before in "<>!=":
            continue
        rep.add(path, line_of(code, bstart + m.start()), "R3", "blocking '=' in a sequential block")
    for m in re.finditer(r"([A-Za-z_][\w]*)\s*(\[[^\]]*\]\s*)*<=\s*([^;]*);", body):
        name, rhs = m.group(1), m.group(3).strip()
        if not (name.endswith("_q") or name.endswith("_mem")):
            rep.add(path, line_of(code, bstart + m.start()), "R6",
                    "flip-flop '%s' must be named *_q (or *_mem for a memory)" % name)
        if not re.fullmatch(r"([A-Za-z_][\w]*(\s*\[[^\]]+\])*|\d+'[bdhoBDHO][0-9a-fA-F_xXzZ]+|\d+|"
                            r"\{\s*\w+\s*\{\s*1'b[01]\s*\}\s*\}|[A-Z_][A-Z0-9_]*)", rhs):
            rep.add(path, line_of(code, bstart + m.start()), "R3",
                    "logic on the right-hand side of '%s <= %s' (compute it in a combinational block)"
                    % (name, rhs))


def check_file(path, rep):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    raw = open(path).read()
    code = strip_comments(raw)
    lines = raw.splitlines()

    # R8 generated banner
    if rel.startswith(GENERATED) and "GENERATED FILE - DO NOT EDIT" not in raw:
        rep.add(rel, 1, "R8", "generated file without DO NOT EDIT banner")
    if path.endswith(".vh"):
        for i, l in enumerate(strip_comments(raw).splitlines(), 1):
            s = l.strip()
            if s and not s.startswith("localparam"):
                rep.add(rel, i, "R1", "header may contain only localparam declarations")
        return

    # R6 nettype and header
    code_lines = [(i, l) for i, l in enumerate(code.splitlines(), 1) if l.strip()]
    if not code_lines or code_lines[0][1].strip() != "`default_nettype none":
        rep.add(rel, code_lines[0][0] if code_lines else 1, "R6",
                "first statement must be `default_nettype none")
    if not code_lines or code_lines[-1][1].strip() != "`default_nettype wire":
        rep.add(rel, code_lines[-1][0] if code_lines else 1, "R6",
                "file must end with `default_nettype wire (Vivado carries the directive into the next file)")
    head = raw.split("`default_nettype", 1)[0]
    if "Purpose" not in head or "Behavior" not in head:
        rep.add(rel, 1, "R6", "header comment must state Purpose and Behavior")

    # R8 waivers
    for i, l in enumerate(lines):
        if "lint_off" in l:
            ctx = "\n".join(lines[max(0, i - 3):i + 1])
            if "Waiver:" not in ctx:
                rep.add(rel, i + 1, "R8", "lint_off without a 'Waiver:' explanation")

    # R4 sections
    pos = []
    for s in SECTIONS:
        idx = [i for i, l in enumerate(lines) if l.strip() == s]
        if len(idx) != 1:
            rep.add(rel, 1, "R4", "section marker '%s' must appear exactly once" % s)
        pos.append(idx[0] if idx else -1)
    if all(p >= 0 for p in pos) and pos != sorted(pos):
        rep.add(rel, pos[0] + 1, "R4", "section markers out of order")

    # R1 synthesizable
    for m in re.finditer(r"\b(initial|forever|while|repeat|wait|fork|join|deassign|force|release)\b", code):
        rep.add(rel, line_of(code, m.start()), "R1", "'%s' is not allowed in RTL" % m.group(1))
    for m in re.finditer(r"#", code):
        after = code[m.end():m.end() + 20].lstrip()
        before = code[:m.start()].rstrip()
        if not after.startswith("(") or not re.search(r"[\w\)]$", before) or before.endswith(";"):
            rep.add(rel, line_of(code, m.start()), "R1", "delay '#' is not allowed in RTL")
    for m in re.finditer(r"\$(\w+)", code):
        if m.group(1) not in ("signed", "unsigned"):
            rep.add(rel, line_of(code, m.start()), "R1", "system task/function $%s in RTL" % m.group(1))
    for m in re.finditer(r"\bfor\s*\(([^;]*);([^;]*);([^)]*)\)", code):
        cond = m.group(2)
        if not re.fullmatch(r"\s*\w+\s*<=?\s*([0-9]+|[A-Z_][A-Z0-9_]*)\s*", cond):
            rep.add(rel, line_of(code, m.start()), "R1", "for-loop bound must be a constant")

    # R5 SystemVerilog
    for w in SV_WORDS:
        for m in re.finditer(r"\b%s\b" % w, code):
            rep.add(rel, line_of(code, m.start()), "R5", "SystemVerilog keyword '%s'" % w)
    for pat, what in ((r"'[01xXzZ](?![\w'])", "unsized fill literal"), (r"\+\+|--", "++/--"),
                      (r"[+\-*/|&^]=(?!=)", "compound assignment"), (r"\$clog2", "$clog2")):
        for m in re.finditer(pat, code):
            if what == "compound assignment" and code[m.start() - 1:m.start() + 1] in ("<=", ">=", "!="):
                continue
            if what == "compound assignment" and code[m.start():m.start() + 2] in ("<=", ">=", "!=", "=="):
                continue
            rep.add(rel, line_of(code, m.start()), "R5", "SystemVerilog construct: " + what)

    # R7 clocks anywhere
    for m in re.finditer(r"\b(negedge)\b", code):
        rep.add(rel, line_of(code, m.start()), "R7", "negedge is not allowed (one clock edge)")

    check_case_defaults(rel, code, rep)

    # R2 / R3 / R6 per block
    for sens, start, body, bstart in find_blocks(code):
        s = sens.replace(" ", "")
        if s in ("(*)", "*"):
            check_comb_block(rel, code, body, bstart, rep)
            for m in re.finditer(r"\b([a-z_][\w]*_q)\s*=(?!=)", body):
                rep.add(rel, line_of(code, bstart + m.start()), "R6",
                        "'%s' is assigned combinationally but named like a flip-flop" % m.group(1))
        else:
            check_seq_block(rel, code, sens, body, bstart, rep)


def rtl_files():
    files = []
    for g in RTL_GLOBS + HDR_GLOBS:
        files += sorted(glob.glob(os.path.join(ROOT, g)))
    return files


def selftest():
    tdir = os.path.join(ROOT, "tools", "rule_tests")
    ok = True
    for f in sorted(glob.glob(os.path.join(tdir, "*.v"))):
        rep = Report()
        check_file(f, rep)
        name = os.path.basename(f)
        rules = sorted(set(r for _, _, r, _ in rep.items))
        if name.startswith("good"):
            good = not rules
            print("%-34s expect PASS       got %-10s %s" % (name, "PASS" if good else ",".join(rules),
                                                          "ok" if good else "WRONG"))
            ok &= good
        else:
            want = name.split("_")[1].upper()
            good = want in rules
            print("%-34s expect FAIL %-5s got %-10s %s" % (name, want, ",".join(rules) or "PASS",
                                                          "ok" if good else "WRONG"))
            ok &= good
    print("rule checker self-test: %s" % ("PASS" if ok else "FAIL"))
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    files = [os.path.abspath(f) for f in sys.argv[1:]] or rtl_files()
    rep = Report()
    for f in files:
        check_file(f, rep)
    for path, line, rule, msg in rep.items:
        print("%s:%d: [%s] %s" % (path, line, rule, msg))
    print("check_rules: %d file(s), %d violation(s)" % (len(files), len(rep.items)))
    sys.exit(1 if rep.items else 0)


if __name__ == "__main__":
    main()
