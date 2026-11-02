#!/usr/bin/env python3
# =============================================================================
# gen_bootrom.py - turn the bootloader image into a case-statement ROM
# -----------------------------------------------------------------------------
# Purpose : Put the boot ROM contents into plain synthesizable Verilog, so no
#           initial block or $readmemh is needed in any RTL module (project
#           rule 1 / decision on memory contents: "case ROM + UART bootloader").
# Behavior: Reads sw/build/boot/boot.elf (or --elf), checks every loadable
#           byte lies inside the ROM region, and writes rtl/gen/bootrom.v with
#           a function holding one case item per non-zero word. Words that are
#           zero fall to the default branch. Two registered read ports are
#           generated: A for instruction fetch, B for data loads (.rodata).
#           With --empty a ROM whose every word is 0 is written (used before
#           the toolchain exists; tests then start in RAM).
# Usage   : py tools/gen_bootrom.py [--elf PATH] [--empty]
# =============================================================================
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "model"))
import elf as elf_mod      # noqa: E402
import params as params_mod  # noqa: E402

OUT = os.path.join(ROOT, "rtl", "gen", "bootrom.v")


def build_words(P, path):
    e = elf_mod.load(path)
    nwords = P.rom["size"] // 4
    words = [0] * nwords
    for addr, data, memsz in e.segments:
        if memsz == 0:
            continue
        if not (P.rom["base"] <= addr and addr + memsz <= P.rom["base"] + P.rom["size"]):
            raise SystemExit("boot image segment 0x%08x+%d is outside the ROM" % (addr, memsz))
        for i, b in enumerate(data):
            o = addr - P.rom["base"] + i
            words[o // 4] |= b << (8 * (o % 4))
    used = max([i + 1 for i, w in enumerate(words) if w] or [0])
    return words, used, hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def emit(P, words, used, src, digest):
    aw = P.rom["aw"] - 2
    lines = []
    for i, w in enumerate(words):
        if w:
            lines.append("            %d'd%d: rom_word = 32'h%08X;" % (aw, i, w))
    body = "\n".join(lines) if lines else "            // (empty image)"
    return """// =============================================================================
// GENERATED FILE - DO NOT EDIT.
// Source : %(src)s (sha256/16 %(digest)s)
// Tool   : tools/gen_bootrom.py
// -----------------------------------------------------------------------------
// bootrom.v - boot ROM, %(nw)d words, %(used)d used by the image
// Purpose : Holds the UART bootloader. Contents are a case statement, so no
//           initial block or $readmemh is needed.
// Behavior: Two independent read ports, each registered with an enable; when
//           a port is not enabled its output holds (same contract as soc_ram).
//           rom_style = "block" asks Vivado to map the ROM to block RAM.
// =============================================================================
`default_nettype none

module bootrom (
    //== Ports
    input  wire          clk,
    input  wire          a_en,
    input  wire [%(awm1)d:0]   a_addr,
    output wire [31:0]   a_rdata,
    input  wire          b_en,
    input  wire [%(awm1)d:0]   b_addr,
    output wire [31:0]   b_rdata
);

    //== Localparams/Wires
    (* rom_style = "block" *) reg [31:0] a_rdata_q;
    (* rom_style = "block" *) reg [31:0] b_rdata_q;
    reg  [31:0] a_word;
    reg  [31:0] b_word;

    function [31:0] rom_word;
        input [%(awm1)d:0] addr;
        begin
            case (addr)
%(body)s
            default: rom_word = 32'h00000000;
            endcase
        end
    endfunction

    //== Combinational Logic
    always @(*) begin
        a_word = rom_word(a_addr);
        b_word = rom_word(b_addr);
    end

    assign a_rdata = a_rdata_q;
    assign b_rdata = b_rdata_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (a_en) begin
            a_rdata_q <= a_word;
        end
        if (b_en) begin
            b_rdata_q <= b_word;
        end
    end

endmodule

`default_nettype wire
""" % dict(src=src, digest=digest, nw=len(words), used=used, awm1=aw - 1, body=body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", default=os.path.join(ROOT, "sw", "build", "boot", "boot.elf"))
    ap.add_argument("--empty", action="store_true")
    a = ap.parse_args()
    P = params_mod.load()
    if a.empty:
        words, used, digest, src = [0] * (P.rom["size"] // 4), 0, "-", "(empty image)"
    else:
        words, used, digest = build_words(P, a.elf)
        src = os.path.relpath(a.elf, ROOT).replace("\\", "/")
    text = emit(P, words, used, src, digest)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="\n") as fh:
        fh.write(text)
    print("bootrom.v: %d of %d words used (%d bytes)" % (used, len(words), used * 4))


if __name__ == "__main__":
    main()
