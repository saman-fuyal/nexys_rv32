#!/usr/bin/env python3
# =============================================================================
# make_figures.py - draw every figure of the paper
# -----------------------------------------------------------------------------
# Purpose : All figures come from code, so they are redrawn (never shrunk)
#           when the design or the results change.
# Style   : one column of a two-column page (3.35 in wide), black on white,
#           lines told apart by style (solid / dashed / dotted), not colour.
# Inputs  : params.json (memory map), results/*.json (charts), VCD files from
#           the waveform runs (sim/build/wave/*.vcd, made by
#           tools/collect_results.py --waves).
# Output  : docs/figures/*.png (300 dpi) and *.svg
# Usage   : py tools/make_figures.py
# =============================================================================
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                        # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "docs", "figures")
sys.path.insert(0, os.path.join(ROOT, "model"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as params_mod  # noqa: E402

COL_W = 3.30   # one column of the A4 two-column write-up (84 mm)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 6.5, "axes.linewidth": 0.6,
                     "lines.linewidth": 0.7, "savefig.dpi": 300, "hatch.linewidth": 0.5})


def canvas(h, xmax=100, ymax=None):
    fig = plt.figure(figsize=(COL_W, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ymax = ymax or xmax * h / COL_W
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text="", lw=0.7, ls="-", fs=6.2, bold=False, round_=False, fill="white", hatch=None):
    if round_:
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", lw=lw, ls=ls,
                           ec="black", fc=fill, hatch=hatch)
    else:
        p = Rectangle((x, y), w, h, lw=lw, ls=ls, ec="black", fc=fill, hatch=hatch)
    ax.add_patch(p)
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                fontweight="bold" if bold else "normal", linespacing=1.15)


def arrow(ax, pts, ls="-", lw=0.7, head=True, text=None, tpos=None, fs=5.6, bg=True):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ls = {"--": (0, (2.6, 1.4)), ":": (0, (0.7, 1.0))}.get(ls, ls)
    ax.plot(xs[:-1] + [xs[-1]], ys[:-1] + [ys[-1]], color="black", ls=ls, lw=lw, solid_capstyle="butt")
    if head:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        d = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1e-9)
        k = min(1.0, 1.6 / d)                      # head only: keep the shaft's line style
        ax.annotate("", xy=pts[-1], xytext=(x2 - (x2 - x1) * k, y2 - (y2 - y1) * k),
                    arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", lw=lw, color="black",
                                    shrinkA=0, shrinkB=0))
    if text:
        tx, ty = tpos if tpos else ((xs[0] + xs[-1]) / 2, (ys[0] + ys[-1]) / 2)
        ax.text(tx, ty, text, fontsize=fs, ha="center", va="center",
                bbox=dict(fc="white", ec="none", pad=0.6) if bg else None)


def mux(ax, x, y, h, label="", w=2.6):
    ax.add_patch(plt.Polygon([(x, y), (x + w, y + h * 0.2), (x + w, y + h * 0.8), (x, y + h)], closed=True,
                             ec="black", fc="white", lw=0.7))
    if label:
        ax.text(x + w / 2, y + h / 2, label, fontsize=4.8, ha="center", va="center", rotation=90)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".png"))
    fig.savefig(os.path.join(OUT, name + ".svg"))
    plt.close(fig)
    return name




# =============================================================================
# F3 memory map
# =============================================================================
def fig_memmap():
    P = params_mod.load()
    fig, ax = canvas(2.2, 100, 66)
    def ad(v):
        return "0x%04X_%04X" % (v >> 16, v & 0xFFFF)
    def sz(n):
        return "%d KB" % (n // 1024) if n < 1 << 20 else "%d MB" % (n >> 20)
    rom, ram, io = P.rom, P.ram, P.io
    offs = ", ".join("%s +%03X" % (k if k != "seg7" else "7-seg", v["offset"]) for k, v in P.periph.items())
    offs = offs.replace("uart", "UART").replace("gpio", "GPIO")
    parts = offs.split(", ")
    offs = ",\n".join(", ".join(parts[i:i + 2]) for i in range(0, len(parts), 2))
    rows = [("0xFFFF_FFFF", None, ""), (ad(ram["base"] + ram["size"]), "unmapped", ""),
            (ad(ram["base"]), "RAM " + sz(ram["size"]), "programs, data, stack\n(top 256 B: boot stack)"),
            (ad(io["base"] + io["size"]), "unmapped", ""),
            (ad(io["base"]), "IO " + sz(io["size"]), offs),
            (ad(rom["base"] + rom["size"]), "unmapped", ""),
            (ad(rom["base"]), "boot ROM " + sz(rom["size"]), "reset vector, UART bootloader")]
    y = 60
    hs = [0, 6, 12, 6, 12, 6, 9]
    for (addr, name, desc), h in zip(rows, hs):
        if name is None:
            ax.text(25, y, addr, fontsize=5.6, ha="right", va="center", family="DejaVu Sans Mono")
            continue
        y0 = y - h
        box(ax, 27, y0, 24, h, "" if name == "unmapped" else name, fs=5.8,
            hatch="////" if name == "unmapped" else None, fill="white", bold=True)
        ax.text(25, y0, addr, fontsize=5.6, ha="right", va="center", family="DejaVu Sans Mono")
        ax.text(53, y0 + h / 2, desc if name != "unmapped" else "unmapped: access fault", fontsize=5.2,
                va="center")
        y = y0
    ax.text(50, 64, "Strict decode: no aliasing; every hole raises an access fault.", fontsize=5.4, ha="center",
            style="italic")
    return save(fig, "fig_memmap")





# =============================================================================
# F7 pipeline timing (load-use stall and taken branch)
# =============================================================================
def fig_pipe_timing():
    fig, ax = canvas(2.0, 100, 60)
    rows = [("lw   x5, 0(x10)", ["IF", "ID", "EX", "MEM", "WB", "", "", "", ""]),
            ("add  x6, x5, x7", ["", "IF", "ID", "ID*", "EX", "MEM", "WB", "", ""]),
            ("beq  x6, x0, L", ["", "", "IF", "IF*", "ID", "EX", "MEM", "WB", ""]),
            ("(wrong path)", ["", "", "", "", "IF", "ID", "x", "", ""]),
            ("(wrong path)", ["", "", "", "", "", "IF", "x", "", ""]),
            ("L: target", ["", "", "", "", "", "", "IF", "ID", "EX"])]
    x0, cw, rh = 30, 7.6, 7.5
    for c in range(9):
        ax.text(x0 + c * cw + cw / 2, 55, "c%d" % (c + 1), fontsize=5.4, ha="center")
    for r, (name, cells) in enumerate(rows):
        y = 47 - r * rh
        ax.text(1, y + rh / 2, name, fontsize=5.6, va="center", family="DejaVu Sans Mono")
        for c, t in enumerate(cells):
            if not t:
                continue
            hatch = "////" if t.endswith("*") else ("xxxx" if t == "x" else None)
            box(ax, x0 + c * cw + 0.4, y + 0.6, cw - 0.8, rh - 1.2, t.rstrip("*") if t != "x" else "",
                fs=5.2, hatch=hatch)
    ax.text(x0 + 4.5 * cw, 47 - rh - 1.0, "x5 forwarded WB->EX", fontsize=4.8, ha="center", style="italic")
    ax.text(x0 + 3.5 * cw, 2.5, "//// stall (load-use, 1 cycle)    xxxx flushed (taken branch, 2 cycles)",
            fontsize=5.0, ha="center")
    return save(fig, "fig_pipe_timing")


# =============================================================================
# waveforms from VCD (hazard and UART)
# =============================================================================
def parse_vcd(path, wanted):
    ids, vals, t = {}, {}, 0
    scope = []
    with open(path) as fh:
        for line in fh:
            s = line.split()
            if not s:
                continue
            if s[0] == "$scope":
                scope.append(s[2])
            elif s[0] == "$upscope":
                scope.pop()
            elif s[0] == "$var":
                full = ".".join(scope + [s[4]])
                for w in wanted:
                    if full.endswith(w):
                        ids.setdefault(s[3], []).append(w)
                        vals.setdefault(w, [])
            elif s[0].startswith("#"):
                t = int(s[0][1:])
            elif s[0][0] in "01xz" and len(s) == 1:
                for w in ids.get(s[0][1:], []):
                    vals[w].append((t, s[0][0]))
            elif s[0][0] == "b" and len(s) == 2:
                for w in ids.get(s[1], []):
                    vals[w].append((t, s[0][1:]))
    return vals


def value_at(changes, t):
    """Value of a signal at time t from its (time, value) change list."""
    cur = None
    for tc, vc in changes:
        if tc > t:
            break
        cur = vc
    return cur


MNEM = {0x37: "lui", 0x17: "auipc", 0x6F: "jal", 0x67: "jalr", 0x0F: "fence", 0x73: "csr"}
BR = ["beq", "bne", "?", "?", "blt", "bge", "bltu", "bgeu"]
LD = ["lb", "lh", "lw", "?", "lbu", "lhu", "?", "?"]
ST = ["sb", "sh", "sw", "?", "?", "?", "?", "?"]
OPI = ["addi", "slli", "slti", "sltiu", "xori", "sr*i", "ori", "andi"]
OPR = ["add", "sll", "slt", "sltu", "xor", "srl", "or", "and"]


def mnemonic(word):
    """Mnemonic of an RV32I instruction word (for waveform labels only)."""
    op, f3, f7 = word & 0x7F, (word >> 12) & 7, word >> 25
    if word == 0x00000013:
        return "nop"
    if op == 0x63:
        return BR[f3]
    if op == 0x03:
        return LD[f3]
    if op == 0x23:
        return ST[f3]
    if op == 0x13:
        return ("srai" if f7 & 0x20 else "srli") if f3 == 5 else OPI[f3]
    if op == 0x33:
        return "sub" if (f3 == 0 and f7 & 0x20) else ("sra" if (f3 == 5 and f7 & 0x20) else OPR[f3])
    return MNEM.get(op, "?")


def draw_rows(ax, rows, n_slots, label_min=0.9, fs_bus=4.4):
    """rows: (label, kind, [value per slot]); kind 'clk', 'bit' or 'bus'."""
    n = len(rows)
    for i, (label, kind, vals) in enumerate(rows):
        y = n - i - 1
        ax.text(-0.02, y + 0.35, label, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=5.6, family="DejaVu Sans Mono")
        if kind == "clk":
            for k in range(n_slots):
                ax.plot([k, k, k + 0.5, k + 0.5, k + 1], [y, y + 0.7, y + 0.7, y, y], color="black", lw=0.6)
            continue
        # merge equal neighbours into segments
        segs, k0 = [], 0
        for k in range(1, n_slots + 1):
            if k == n_slots or vals[k] != vals[k0]:
                segs.append((k0, k, vals[k0]))
                k0 = k
        for a, b, val in segs:
            if kind == "bit":
                lvl = 0.7 if val == "1" else 0.0
                ax.plot([a, b], [y + lvl, y + lvl], color="black", lw=0.8)
                if b < n_slots:
                    ax.plot([b, b], [y, y + 0.7], color="black", lw=0.8)
            else:
                ax.plot([a, b], [y + 0.7, y + 0.7], color="black", lw=0.6)
                ax.plot([a, b], [y, y], color="black", lw=0.6)
                if b < n_slots:
                    ax.plot([b - 0.08, b + 0.08], [y, y + 0.7], color="black", lw=0.6)
                    ax.plot([b - 0.08, b + 0.08], [y + 0.7, y], color="black", lw=0.6)
                if val and b - a >= label_min:
                    ax.text((a + b) / 2, y + 0.35, val, ha="center", va="center", fontsize=fs_bus,
                            family="DejaVu Sans Mono")
    ax.set_xlim(0, n_slots)
    ax.set_ylim(-0.3, n + 0.1)
    ax.set_yticks([])
    for sp in ("left", "right", "top"):
        ax.spines[sp].set_visible(False)


def fig_waves():
    """Cycle-sampled waveforms: each signal is drawn with the value it holds at
    the end of each cycle (just before the next rising edge), so zero-width
    simulator glitches on combinational signals do not appear."""
    made = []
    wd = os.path.join(ROOT, "sim", "build", "wave")
    hz = os.path.join(wd, "hazards.vcd")
    if os.path.exists(hz):
        keys = ["tb_soc.clk", "u_core.d_insn", "u_core.stall", "u_core.ex_redirect", "u_core.fwd_a_mem",
                "u_core.fwd_b_mem", "u_core.fwd_a_wb", "u_core.fwd_b_wb", "tb_soc.rvfi_valid", "tb_soc.rvfi_pc", "u_core.d_valid_q"]
        v = parse_vcd(hz, keys)
        rises = [t for t, x in v["tb_soc.clk"] if x == "1"]

        def at(key, k):
            return value_at(v[key], rises[k + 1] - 1)
        ncyc = len(rises) - 1
        stall = [at("u_core.stall", k) == "1" for k in range(ncyc)]
        flush = [at("u_core.ex_redirect", k) == "1" for k in range(ncyc)]
        # first window of 17 cycles holding a load-use stall followed by a taken branch
        start = None
        for k in range(ncyc - 16):
            if stall[k] and any(flush[k + 1:k + 11]):
                start = max(0, k - 2)
                break
        if start is None:
            raise SystemExit("hazard waveform: no stall followed by a taken branch in the dump")
        W = 17

        def bit(key):
            return [at(key, start + k) for k in range(W)]

        def orbits(a, b):
            return ["1" if at(a, start + k) == "1" or at(b, start + k) == "1" else "0" for k in range(W)]

        def insn(k):
            x = at("u_core.d_insn", start + k)
            if at("u_core.d_valid_q", start + k) != "1" or not x or "x" in x:
                return ""
            return mnemonic(int(x, 2))

        def rpc(k):
            x = at("tb_soc.rvfi_pc", start + k)
            if at("tb_soc.rvfi_valid", start + k) != "1" or not x or "x" in x:
                return ""
            return "%02x" % (int(x, 2) & 0xFF)
        rows = [("clk", "clk", None),
                ("ID insn", "bus", [insn(k) for k in range(W)]),
                ("stall", "bit", bit("u_core.stall")),
                ("flush", "bit", bit("u_core.ex_redirect")),
                ("fwd MEM", "bit", orbits("u_core.fwd_a_mem", "u_core.fwd_b_mem")),
                ("fwd WB", "bit", orbits("u_core.fwd_a_wb", "u_core.fwd_b_wb")),
                ("retire", "bit", bit("tb_soc.rvfi_valid")),
                ("retire pc", "bus", [rpc(k) for k in range(W)])]
        fig = plt.figure(figsize=(COL_W, 1.95))
        ax = fig.add_axes([0.17, 0.15, 0.81, 0.83])
        draw_rows(ax, rows, W, label_min=0.9, fs_bus=3.9)
        ax.set_xticks([k + 0.5 for k in range(W)])
        ax.set_xticklabels([str(k + 1) for k in range(W)])
        ax.tick_params(axis="x", labelsize=4.8, length=1.5)
        ax.set_xlabel("clock cycle (pc shown as its low byte)", fontsize=5.4, labelpad=1.5)
        made.append(save(fig, "fig_wave_hazard"))
        # facts for the caption in the write-up (cycle numbers as drawn, 1-based)
        ev = dict(stall=[k + 1 for k in range(W) if rows[2][2][k] == "1"],
                  flush=[k + 1 for k in range(W) if rows[3][2][k] == "1"],
                  no_retire=[k + 1 for k in range(W) if rows[6][2][k] != "1"],
                  id=[insn(k) for k in range(W)])
        json.dump(ev, open(os.path.join(OUT, "fig_wave_hazard.json"), "w"), indent=1)
    ua = os.path.join(wd, "uart.vcd")
    if os.path.exists(ua):
        keys = ["tb_soc.uart_tx", "u_uart.tx_busy", "u_tx.nbits_q"]
        v = parse_vcd(ua, keys)
        P = params_mod.load()
        bit_t = P.uart_div * 10000          # ps per bit (the testbench clock period is 10 ns)
        falls = [t for t, x in v["tb_soc.uart_tx"] if x == "0"]
        if not falls:
            raise SystemExit("uart waveform: no start bit in the dump")
        f0 = falls[0]
        # quarter-bit slots, from half a bit before the start bit to the end of the stop bit
        Q = 4
        nslot = 10 * Q + 2
        t0 = f0 - 2 * bit_t // Q

        def samp(key, k):
            return value_at(v[key], t0 + k * bit_t // Q + bit_t // (2 * Q))
        pin = [samp("tb_soc.uart_tx", k) or "1" for k in range(nslot)]
        busy = [samp("u_uart.tx_busy", k) or "0" for k in range(nslot)]
        left = []
        for k in range(nslot):
            x = samp("u_tx.nbits_q", k)
            left.append(str(int(x, 2)) if x and "x" not in x else "0")
        data = 0
        for b in range(8):
            if value_at(v["tb_soc.uart_tx"], f0 + (b + 1) * bit_t + bit_t // 2) == "1":
                data |= 1 << b
        ch = chr(data) if 32 <= data < 127 else "?"
        rows = [("uart_tx pin", "bit", pin), ("TX_BUSY", "bit", busy), ("bits left", "bus", left)]
        fig = plt.figure(figsize=(COL_W, 1.15))
        ax = fig.add_axes([0.2, 0.25, 0.78, 0.62])
        draw_rows(ax, rows, nslot, label_min=Q * 0.9, fs_bus=4.6)
        names = ["start"] + ["d%d" % b for b in range(8)] + ["stop"]
        for b, nm in enumerate(names):
            x = 2 + b * Q + Q / 2.0
            ax.text(x, 3.05, nm, ha="center", va="bottom", fontsize=4.6)
        ax.set_xticks([2 + b * Q for b in range(11)])
        ax.set_xticklabels([str(b) for b in range(11)])
        ax.tick_params(axis="x", labelsize=4.8, length=1.5)
        ax.set_xlabel("bit times at %d baud: '%s' = 0x%02X, sent LSB first" % (P.baud, ch, data),
                      fontsize=5.4, labelpad=1.5)
        ax.set_ylim(-0.3, 3.5)
        made.append(save(fig, "fig_wave_uart"))
    return made


# =============================================================================
# results chart
# =============================================================================
OKABE_ITO = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442",
             "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000"}


def fig_cpi():
    """CPI of both cores on four workloads (RTL simulation, exact cycle counts). Okabe-Ito colours,
    with hatching so the bars also differ in black and white; legend above the plot area."""
    s = os.path.join(ROOT, "results", "summary.json")
    if not os.path.exists(s):
        return None
    d = json.load(open(s))
    b = d.get("bench_sim", {})
    work = [("riscv-tests\n(average)", lambda c: d["cpi_rvtests_avg"].get(c)),
            ("random streams\n(average)", lambda c: d["cpi_random_avg"].get(c)),
            ("Dhrystone", lambda c: b.get(c, {}).get("dhrystone_cpi")),
            ("CoreMark", lambda c: b.get(c, {}).get("coremark_cpi"))]
    from diagram import FONT
    plt.rcParams.update({"font.family": FONT, "font.size": 8})
    fig = plt.figure(figsize=(3.35, 1.95))
    ax = fig.add_axes([0.12, 0.22, 0.86, 0.62])
    wbar = 0.36
    style = (("mc", "multi-cycle", OKABE_ITO["orange"], "////"), ("pipe", "5-stage pipeline", OKABE_ITO["blue"], ""))
    top = 0
    for k, (core, label, col, hatch) in enumerate(style):
        vals = [f(core) or 0 for _, f in work]
        top = max(top, max(vals))
        xs = [i + (k - 0.5) * wbar for i in range(len(work))]
        ax.bar(xs, vals, wbar, color=col, edgecolor="black", lw=0.6, hatch=hatch, label=label)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.06, "%.2f" % v, ha="center", va="bottom", fontsize=7)
    ax.set_xticks(range(len(work)))
    ax.set_xticklabels([w for w, _ in work], fontsize=7.5)
    ax.set_ylabel("cycles per instruction", fontsize=8)
    ax.set_ylim(0, top * 1.22)
    ax.tick_params(axis="both", labelsize=7.5, width=0.6)
    for sp in ("right", "top"):
        ax.spines[sp].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=8,
              handlelength=1.6, columnspacing=1.5)
    fig.savefig(os.path.join(OUT, "fig_cpi.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "fig_cpi.svg"))
    plt.close(fig)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 6.5})
    return "fig_cpi"


def fig_slot(name, title, lines):
    from diagram import FONT
    fig, ax = canvas(1.6, 100, 48)
    box(ax, 2, 2, 96, 44, "", ls="--", lw=1.0)
    ax.text(50, 33, title, ha="center", va="center", fontsize=8, family=FONT)
    ax.text(50, 17, "\n".join(lines), ha="center", va="center", fontsize=7, family=FONT)
    return save(fig, name)


def main():
    import make_diagrams
    made = make_diagrams.main() + [fig_memmap()]
    made += fig_waves()
    b = fig_cpi()
    if b:
        made.append(b)
    made.append(fig_slot("slot_board_photo", "Photograph to be added on board day",
                         ["Nexys A7 running seg7_counter, terminal visible.",
                          "Save it as docs/slots/board_photo.jpg and run update_docs.bat."]))
    print("figures: " + ", ".join(made))


if __name__ == "__main__":
    main()
