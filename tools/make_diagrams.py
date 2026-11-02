#!/usr/bin/env python3
# =============================================================================
# make_diagrams.py - the block, flow and state diagrams (rule-checked)
# -----------------------------------------------------------------------------
# Purpose : Draws the hand-made diagrams of the paper with
#           tools/diagram.py, which refuses to save a drawing that has a
#           diagonal or crossing line, a line through a block, or text
#           touching a line, an outline or other text. Black and white,
#           8 pt Times (Liberation Serif on Linux), one column wide (241 pt).
# Output  : docs/figures/fig_soc, fig_fsm, fig_pipe_datapath, fig_flow,
#           fig_pipe_timing, fig_mc_datapath (.png at 600 dpi and .svg)
# Usage   : py tools/make_diagrams.py   (also called by tools/make_figures.py)
# =============================================================================
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "model"))
from diagram import Diagram   # noqa: E402
import params as params_mod   # noqa: E402

OUT = os.environ.get("NRV_FIG_OUT") or os.path.join(ROOT, "docs", "figures")
W = 241.0                      # one column of the IEEE A4 template (3.35 in)


def out(name):
    os.makedirs(OUT, exist_ok=True)
    return os.path.join(OUT, name)


# =============================================================================
# System-on-chip
# =============================================================================
def fig_soc():
    P = params_mod.load().raw
    rom_kb = P["memory"]["bootrom"]["size"] // 1024
    ram_kb = P["memory"]["ram"]["size"] // 1024
    d = Diagram(W, 166)
    # core and bus decoder
    d.box("core", 4, 92, 64, 56, "RV32I core\n(multi-cycle or\n5-stage pipeline)")
    d.box("bus", 104, 30, 34, 126, "bus\ndecoder")
    # targets, top to bottom; the timer is last so its interrupt line leaves downwards
    targets = [("rom", "boot ROM, %d KB" % rom_kb), ("ram", "RAM, %d KB" % ram_kb), ("uart", "UART"),
               ("gpio", "GPIO"), ("seg", "7-segment"), ("sys", "system control"), ("timer", "timer")]
    y = 140
    for name, label in targets:
        d.box(name, 166, y, 71, 14, label)
        d.wire("bus_" + name, [(138, y + 7), (166, y + 7)])
        y -= 18
    # core ports
    d.wire("fetch", [(68, 138), (104, 138)])
    d.text(86, 144, "fetch")
    d.wire("data", [(68, 120), (104, 120)])
    d.text(86, 126, "data")
    d.wire("fault", [(104, 102), (68, 102)], style="--")
    d.text(86, 108, "fault")
    # timer interrupt: below everything, back to the core
    ty = 140 - 6 * 18
    d.wire("irq", [(201, ty), (201, 10), (36, 10), (36, 92)], style="--")
    d.text(70, 17, "timer interrupt")
    return d.save(out("fig_soc"))


# =============================================================================
# Multi-cycle control states
# =============================================================================
def fig_fsm():
    d = Diagram(W, 118)
    cy = 70
    states = [("fetch", 24, "FETCH"), ("decode", 108, "DECODE"), ("exec", 190, "EXEC")]
    for name, x, label in states:
        d.box(name, x, cy - 10, 46, 20, label, round_=True)
    d.box("mem", 190, 14, 46, 20, "MEM", round_=True)
    d.wire("f2d", [(70, cy), (108, cy)])
    d.wire("d2e", [(154, cy), (190, cy)])
    # EXEC back to FETCH over the top
    d.wire("e2f", [(213, cy + 10), (213, 98), (47, 98), (47, cy + 10)])
    d.text(130, 105, "not a load: retire, or take a trap")
    # loads go through MEM
    d.wire("e2m", [(213, cy - 10), (213, 34)])
    d.text(225, 47, "load", ha="center")
    d.wire("m2f", [(190, 24), (47, 24), (47, cy - 10)])
    d.text(118, 31, "write rd, retire")
    # interrupt check in FETCH
    d.wire("irq", [(24, cy + 5), (12, cy + 5), (12, cy - 5), (24, cy - 5)])
    d.text(22, 44, "interrupt:\ntrap entry", ha="center")
    return d.save(out("fig_fsm"))


# =============================================================================
# Five-stage pipeline
# =============================================================================
def fig_pipe_datapath():
    d = Diagram(W, 184)
    bw, bar, gap = 36.0, 4.0, 5.0
    x0 = 3.0
    stages = [("if", "PC,\nfetch"), ("id", "decode,\nregister\nfile"), ("ex", "ALU,\nbranch"),
              ("mem", "load/\nstore,\nCSR,\ntraps"), ("wb", "load\nalign")]
    names = ["IF", "ID", "EX", "MEM", "WB"]
    xs = []
    x = x0
    for k, (name, label) in enumerate(stages):
        xs.append(x)
        d.box(name, x, 68, bw, 44, label)
        d.text(x + bw / 2, 176, names[k], bold=True)
        if k < 4:
            bx = x + bw + gap
            d.bar("r%d" % k, bx, 58, bar, 66)
            d.wire("flow%d" % k, [(x + bw, 90), (bx, 90)], head=False)
            d.wire("flow%d" % k, [(bx + bar, 90), (bx + bar + gap, 90)])
            x = bx + bar + gap
    xif, xid, xex, xmem, xwb = xs
    # redirects over the top
    d.wire("ex_redirect", [(xex + 18, 112), (xex + 18, 134), (xif + 24, 134), (xif + 24, 112)])
    d.text((xif + 24 + xex + 18) / 2, 141, "branch or jump (EX)")
    d.wire("mem_redirect", [(xmem + 18, 112), (xmem + 18, 152), (xif + 12, 152), (xif + 12, 112)], style="--")
    d.text((xif + 12 + xmem + 18) / 2, 159, "trap, MRET, FENCE.I (MEM)")
    # forwarding and write-back underneath
    d.wire("fwd_mem", [(xmem + 12, 68), (xmem + 12, 50), (xex + 24, 50), (xex + 24, 68)])
    d.text((xex + 24 + xmem + 12) / 2, 41, "forward")
    d.wire("wb", [(xwb + 18, 68), (xwb + 18, 26), (xid + 18, 26), (xid + 18, 68)], style="--")
    d.wire("wb", [(xex + 8, 26), (xex + 8, 68)], style="--")
    d.text((xid + 18 + xwb + 18) / 2, 17, "write back, and forward to EX")
    return d.save(out("fig_pipe_datapath"))


# =============================================================================
# Verification flow
# =============================================================================
def fig_flow():
    d = Diagram(W, 236)
    d.box("params", 72, 212, 97, 18, "params.json", round_=True)
    d.wire("p2g", [(120.5, 212), (120.5, 198)])
    d.box("gen", 30, 172, 181, 26, "generated: Verilog and C headers,\nlinker scripts, constraints")
    d.wire("g2e", [(120.5, 172), (120.5, 158)])
    d.box("elf", 22, 120, 197, 38, "test program (ELF): directed, riscv-tests,\narch-test, random streams, C programs,\n"
          "on-board self-test programs")
    d.wire("elf", [(120.5, 120), (120.5, 104)])
    d.wire("elf", [(120.5, 112), (41, 112), (41, 104)])
    d.wire("elf", [(120.5, 112), (200, 112), (200, 104)])
    d.box("rtl", 3, 72, 76, 32, "RTL simulation\n(Verilator, Icarus)")
    d.box("iss", 83, 72, 75, 32, "golden model\n(Python ISS)")
    d.box("board", 162, 72, 76, 32, "Nexys A7 board\n(UART bootloader)")
    d.wire("rtl_out", [(41, 72), (41, 58)])
    d.wire("iss_tr", [(100, 72), (100, 58)])
    d.wire("iss_uart", [(141, 72), (141, 58)])
    d.wire("board_out", [(200, 72), (200, 58)])
    d.box("tcmp", 3, 32, 115, 26, "trace compare: every\nretired instruction")
    d.box("ucmp", 123, 32, 115, 26, "UART compare:\nevery byte printed")
    d.wire("t2r", [(60, 32), (60, 20)])
    d.wire("u2r", [(181, 32), (181, 20)])
    d.box("res", 30, 3, 181, 17, "results files: paper and README", round_=True)
    return d.save(out("fig_flow"))


# =============================================================================
# Multi-cycle datapath
# =============================================================================
def fig_mc_datapath():
    d = Diagram(W, 150)
    y0, h = 56, 36
    d.box("pc", 3, y0, 26, h, "PC")
    d.box("ibus", 37, y0, 34, h, "fetch\nport")
    d.box("ir", 79, y0, 22, h, "IR")
    d.box("rf", 109, y0, 40, h, "register\nfile")
    d.box("alu", 157, y0, 32, h, "ALU,\nbranch")
    d.box("lsu", 197, y0, 41, h, "load/\nstore")
    cy = y0 + h / 2
    d.wire("a1", [(29, cy), (37, cy)])
    d.wire("a2", [(71, cy), (79, cy)])
    d.wire("a3", [(101, cy), (109, cy)])
    d.wire("a4", [(149, cy), (157, cy)])
    d.wire("a5", [(189, cy), (197, cy)])
    top = y0 + h
    d.wire("pc_alu", [(22, top), (22, 106), (167, 106), (167, top)])
    d.text(94, 113, "pc to ALU (branch target, AUIPC)")
    d.wire("next_pc", [(181, top), (181, 126), (10, 126), (10, top)], style="--")
    d.text(94, 133, "next pc, trap or branch target")
    d.wire("alu_rf", [(173, y0), (173, 38), (135, 38), (135, y0)])
    d.text(154, 30, "ALU result")
    d.wire("lsu_rf", [(217, y0), (217, 14), (121, 14), (121, y0)], style="--")
    d.text(169, 6, "load data")
    return d.save(out("fig_mc_datapath"))


# =============================================================================
# Pipeline timing: load-use stall and taken branch
# =============================================================================
def fig_pipe_timing():
    fs = 7.5
    d = Diagram(W, 132, size=fs)
    cw, ch, g = 23.0, 13.0, 1.5
    ncol = 7
    x0 = W - ncol * (cw + g) - 1
    rows = [("lw x5, 0(x10)", ["IF", "ID", "EX", "MEM", "WB"], 0, {}),
            ("add x6, x5, x7", ["IF", "ID", "stall", "EX", "MEM", "WB"], 1, {2: "stall"}),
            ("beq x6, x0, L", ["IF", "stall", "ID", "EX", "MEM", "WB"], 2, {1: "stall"}),
            ("wrong path", ["IF", "ID", "flush"], 4, {2: "flush"}),
            ("wrong path", ["IF", "flush"], 5, {1: "flush"}),
            ("L: target", ["IF", "ID"], 6, {})]
    ytop = 108
    for c in range(ncol):
        d.text(x0 + c * (cw + g) + cw / 2, ytop + 15, "c%d" % (c + 1))
    for r, (label, cells, start, special) in enumerate(rows):
        y = ytop - r * (ch + 4) - ch
        d.text(2, y + ch / 2, label, ha="left")
        for k, s in enumerate(cells):
            c = start + k
            if c >= ncol:
                break
            style = "--" if special.get(k) else "-"
            d.box("r%dc%d" % (r, c), x0 + c * (cw + g), y, cw, ch, s if s not in ("stall", "flush") else s,
                  style=style, size=fs if s not in ("stall", "flush") else 6.5)
    return d.save(out("fig_pipe_timing"))


def main():
    made = [fig_soc(), fig_fsm(), fig_pipe_datapath(), fig_pipe_timing(), fig_flow(), fig_mc_datapath()]
    print("diagrams (rules checked): " + ", ".join(made))
    return made


if __name__ == "__main__":
    main()
