#!/usr/bin/env python3
# =============================================================================
# elf.py - minimal ELF32 little-endian RISC-V loader (no dependencies)
# -----------------------------------------------------------------------------
# Purpose : Read the loadable segments and the symbol table of a program so the
#           ISS, the hex generator and the host bootloader tool all see the
#           same bytes.
# Behavior: load(path) -> Elf with .entry, .segments [(paddr, bytes, memsz)],
#           .symbols {name: value}. Raises ValueError for anything that is not
#           a 32-bit little-endian RISC-V executable.
# =============================================================================
import struct

EM_RISCV = 243
PT_LOAD = 1
SHT_SYMTAB = 2


class Elf(object):
    def __init__(self, entry, segments, symbols):
        self.entry = entry
        self.segments = segments
        self.symbols = symbols

    def image(self):
        """Return (base, bytearray) covering all PT_LOAD segments, gaps zeroed."""
        lo = min(s[0] for s in self.segments)
        hi = max(s[0] + max(len(s[1]), s[2]) for s in self.segments)
        buf = bytearray(hi - lo)
        for addr, data, _ in self.segments:
            buf[addr - lo:addr - lo + len(data)] = data
        return lo, buf


def load(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:4] != b"\x7fELF":
        raise ValueError("%s: not an ELF file" % path)
    if d[4] != 1 or d[5] != 1:
        raise ValueError("%s: need ELF32 little-endian" % path)
    (e_type, e_machine, _ver, e_entry, e_phoff, e_shoff, _flags, _ehsz,
     e_phentsize, e_phnum, e_shentsize, e_shnum, _shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", d, 16)
    if e_machine != EM_RISCV:
        raise ValueError("%s: not a RISC-V ELF (machine %d)" % (path, e_machine))
    segs = []
    for i in range(e_phnum):
        p_type, p_offset, _vaddr, p_paddr, p_filesz, p_memsz, _fl, _al = struct.unpack_from(
            "<IIIIIIII", d, e_phoff + i * e_phentsize)
        if p_type == PT_LOAD and p_memsz:
            segs.append((p_paddr, d[p_offset:p_offset + p_filesz], p_memsz))
    syms = {}
    shdrs = [struct.unpack_from("<IIIIIIIIII", d, e_shoff + i * e_shentsize) for i in range(e_shnum)]
    for sh in shdrs:
        if sh[1] == SHT_SYMTAB:
            strtab = shdrs[sh[6]]
            for off in range(sh[4], sh[4] + sh[5], 16):
                st_name, st_value, _sz, _info, _oth, _shndx = struct.unpack_from("<IIIBBH", d, off)
                if st_name:
                    s0 = strtab[4] + st_name
                    name = d[s0:d.index(b"\0", s0)].decode("ascii", "replace")
                    syms[name] = st_value
    return Elf(e_entry, segs, syms)
