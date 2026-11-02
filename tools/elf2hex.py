#!/usr/bin/env python3
# =============================================================================
# elf2hex.py - convert a RAM program (ELF) into a $readmemh file and a .bin
# -----------------------------------------------------------------------------
# Purpose : Produce the RAM image the simulation testbench preloads, and the
#           raw binary the host bootloader tool can send.
# Behavior: Only segments inside the RAM region are written (tohost and other
#           IO-region symbols are NOBITS and skipped). The hex file has one
#           32-bit little-endian word per line, word 0 = RAM base, with an
#           '@' address line before each contiguous block.
# Usage   : py tools/elf2hex.py prog.elf prog.hex [--bin prog.bin]
# =============================================================================
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
import elf as elf_mod        # noqa: E402
import params as params_mod  # noqa: E402


def ram_image(P, path):
    e = elf_mod.load(path)
    base, size = P.ram["base"], P.ram["size"]
    img = bytearray()
    for addr, data, memsz in e.segments:
        if P.io["base"] <= addr < P.io["base"] + P.io["size"]:
            continue
        if not (base <= addr and addr + memsz <= base + size):
            raise SystemExit("%s: segment 0x%08x+0x%x is outside RAM" % (path, addr, memsz))
        end = addr - base + memsz
        if len(img) < end:
            img.extend(bytes(end - len(img)))
        img[addr - base:addr - base + len(data)] = data
    while len(img) % 4:
        img.append(0)
    return e, img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf")
    ap.add_argument("hex")
    ap.add_argument("--bin")
    ap.add_argument("--ram-size", type=lambda s: int(s, 0), help="override RAM size (arch-test config)")
    a = ap.parse_args()
    P = params_mod.load(overrides={"memory.ram.size": a.ram_size} if a.ram_size else None)
    e, img = ram_image(P, a.elf)
    with open(a.hex, "w", newline="\n") as fh:
        fh.write("@00000000\n")
        for i in range(0, len(img), 4):
            fh.write("%08x\n" % int.from_bytes(img[i:i + 4], "little"))
    if a.bin:
        with open(a.bin, "wb") as fh:
            fh.write(img)
    print("%s: %d bytes, entry 0x%08x" % (os.path.basename(a.hex), len(img), e.entry))


if __name__ == "__main__":
    main()
