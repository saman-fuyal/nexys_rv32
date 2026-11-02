#!/usr/bin/env python3
# =============================================================================
# gen_all.py - regenerate every file derived from params.json
# -----------------------------------------------------------------------------
# Purpose : Keep one source of truth. Each output carries a DO NOT EDIT banner
#           and the hash of params.json it was made from, so a stale file is
#           detectable (run_sim.py checks the hash before every run).
# Outputs : rtl/gen/soc_params.vh          Verilog localparams
#           sw/include/soc_map.h           C register addresses and constants
#           sw/link/app.ld                 linker script for programs in RAM
#           sw/link/boot.ld                linker script for the boot ROM
#           sim/riscv_tests/link.ld        linker script for riscv-tests
#           sim/arch_test/link.ld          linker script for riscv-arch-test
#           fpga/constraints/clock_gen.xdc clock constraint
#           fpga/scripts/params_gen.tcl    part, default core, clock for Vivado
#           docs/generated/*.md            memory map, register and CSR tables
#           host/soc_params.json           copy used by the host tool
# Usage   : py tools/gen_all.py [--check]
#           --check exits 1 if any output differs from what would be written.
# =============================================================================
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "model"))
import params as params_mod  # noqa: E402

BOOT_STACK = 256          # bytes at the top of RAM reserved for the bootloader stack


def params_hash():
    with open(params_mod.PARAMS_JSON, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:16]


def banner(comment, what):
    h = params_hash()
    lines = [
        "=" * 70,
        "GENERATED FILE - DO NOT EDIT.",
        "Source : params.json (sha256/16 %s)" % h,
        "Tool   : tools/gen_all.py",
        "Content: %s" % what,
        "=" * 70,
    ]
    return "\n".join(comment + " " + l if l else comment for l in lines) + "\n"


# -----------------------------------------------------------------------------
# Verilog header
# -----------------------------------------------------------------------------
def gen_vh(P):
    o = [banner("//", "SoC localparams, included inside module bodies")]
    o.append("// Not every includer uses every constant: UNUSEDPARAM waived for this header.")
    o.append("// verilator lint_off UNUSEDPARAM")
    o.append("// Clocking and peripheral timing")
    o.append("localparam integer CPU_HZ          = %d;" % P.cpu_hz)
    o.append("localparam integer UART_DIV        = %d;  // cycles per bit, baud %d (error %+.3f%%)"
             % (P.uart_div, P.baud, 100 * P.uart_baud_err))
    o.append("localparam integer TIMER_DIV       = %d;  // cycles per mtime tick (%d Hz)" % (P.timer_div, P.tick_hz))
    o.append("localparam integer DEBOUNCE_CYCLES = %d;  // %d ms" % (P.debounce_cycles, P.debounce_ms))
    o.append("localparam integer SEG7_DIV        = %d;  // cycles per digit" % P.seg7_div)
    o.append("")
    o.append("// Memory map (strict decode: anything outside a region faults)")
    o.append("localparam [31:0] RESET_VECTOR = 32'h%08X;" % P.reset_vector)
    for n, tag in (("bootrom", "ROM"), ("ram", "RAM"), ("io", "IO")):
        r = P.regions[n]
        o.append("localparam [31:0] %s_BASE = 32'h%08X;" % (tag, r["base"]))
        o.append("localparam integer %s_AW  = %d;  // %d bytes" % (tag, r["aw"], r["size"]))
    o.append("")
    o.append("// IO decode: addr[11:8] selects the peripheral, addr[7:2] the register")
    for pname in ("uart", "gpio", "seg7", "timer", "sysctrl"):
        pd = P.periph[pname]
        o.append("localparam [3:0] PIDX_%-8s = 4'd%d;" % (pname.upper(), pd["index"]))
        o.append("localparam [5:0] NREGS_%-8s = 6'd%d;" % (pname.upper(), pd["nregs"]))
    o.append("")
    o.append("// Feature flags and identification")
    o.append("localparam FEAT_ZICSR     = 1'b%d;" % P.zicsr)
    o.append("localparam FEAT_TIMER_IRQ = 1'b%d;" % P.timer_irq)
    o.append("localparam FEAT_ZIFENCEI  = 1'b%d;" % P.zifencei)
    o.append("localparam [31:0] MISA_VALUE   = 32'h%08X;" % P.misa)
    o.append("localparam [31:0] MIMPID_VALUE = 32'h%08X;" % P.mimpid)
    o.append("localparam [31:0] BUILD_ID     = 32'h%08X;" % P.build_id)
    o.append("// Simulation-only: RAM address bits of the riscv-arch-test configuration")
    o.append("localparam integer COMPLIANCE_RAM_AW = %d;" % P.compliance_ram_aw)
    o.append("// verilator lint_on UNUSEDPARAM")
    return "\n".join(o) + "\n"


# -----------------------------------------------------------------------------
# C header
# -----------------------------------------------------------------------------
def gen_h(P):
    o = [banner("//", "C register addresses and SoC constants")]
    o.append("#ifndef SOC_MAP_H")
    o.append("#define SOC_MAP_H")
    o.append("")
    o.append("#define SOC_CPU_HZ        %du" % P.cpu_hz)
    o.append("#define SOC_UART_BAUD     %du" % P.baud)
    o.append("#define SOC_TIMER_HZ      %du" % P.tick_hz)
    o.append("#define SOC_ROM_BASE      0x%08Xu" % P.rom["base"])
    o.append("#define SOC_ROM_SIZE      %du" % P.rom["size"])
    o.append("#define SOC_RAM_BASE      0x%08Xu" % P.ram["base"])
    o.append("#define SOC_RAM_SIZE      %du" % P.ram["size"])
    o.append("#define SOC_IO_BASE       0x%08Xu" % P.io["base"])
    o.append("#define SOC_BOOT_STACK    %du" % BOOT_STACK)
    o.append("#define SOC_FEAT_ZICSR    %d" % P.zicsr)
    o.append("#define SOC_FEAT_TIMERIRQ %d" % P.timer_irq)
    o.append("#define SOC_FEAT_ZIFENCEI %d" % P.zifencei)
    o.append("")
    o.append("#define SOC_REG(addr) (*(volatile unsigned int *)(addr))")
    o.append("")
    for pname, pd in P.periph.items():
        o.append("/* %s @ 0x%08X */" % (pname, pd["base"]))
        for r in pd["regs"]:
            o.append("#define %-24s 0x%08Xu  /* %s %s */" % (
                "%s_%s" % (pname.upper(), r["name"]), r["addr"], r["acc"], r["desc"][:60]))
        o.append("")
    o.append("/* UART STATUS bits */")
    o.append("#define UART_TX_BUSY     (1u << 0)")
    o.append("#define UART_RX_VALID    (1u << 1)")
    o.append("#define UART_RX_OVERRUN  (1u << 2)")
    o.append("#define UART_RX_FRAMEERR (1u << 3)")
    o.append("/* Button bits */")
    o.append("#define BTN_C (1u << 0)")
    o.append("#define BTN_U (1u << 1)")
    o.append("#define BTN_L (1u << 2)")
    o.append("#define BTN_R (1u << 3)")
    o.append("#define BTN_D (1u << 4)")
    o.append("")
    o.append("/* CSR numbers */")
    for c in P.csrs:
        o.append("#define CSR_%-11s 0x%03X" % (c["name"].upper(), c["addr"]))
    o.append("")
    o.append("#endif")
    return "\n".join(o) + "\n"


# -----------------------------------------------------------------------------
# Linker scripts
# -----------------------------------------------------------------------------
def gen_app_ld(P):
    return banner("/*", "linker script for programs loaded into RAM").replace("\n/*", "\n *").rstrip() + " */\n" + """
OUTPUT_ARCH("riscv")
ENTRY(_start)

STACK_SIZE = %(stack)d;

MEMORY
{
  RAM (rwx) : ORIGIN = 0x%(ram).8X, LENGTH = %(ramsz)d
}

SECTIONS
{
  .text : {
    KEEP(*(.text.start))
    *(.text .text.*)
  } > RAM
  .rodata : ALIGN(4) {
    *(.rodata .rodata.*)
    *(.srodata .srodata.*)
  } > RAM
  .data : ALIGN(4) {
    __data_start = .;
    *(.data .data.*)
    . = ALIGN(4);
    __global_pointer$ = . + 0x800;
    *(.sdata .sdata.*)
    . = ALIGN(4);
    __data_end = .;
  } > RAM
  .bss (NOLOAD) : ALIGN(4) {
    __bss_start = .;
    *(.sbss .sbss.*)
    *(.bss .bss.*)
    *(COMMON)
    . = ALIGN(4);
    __bss_end = .;
  } > RAM
  __stack_top = ORIGIN(RAM) + LENGTH(RAM);
  __stack_bottom = __stack_top - STACK_SIZE;
  __load_limit = __stack_top - %(bootstack)d;
  ASSERT(__bss_end <= __stack_bottom, "program + stack do not fit in RAM")
  /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
""" % dict(stack=P.stack_size, ram=P.ram["base"], ramsz=P.ram["size"], bootstack=BOOT_STACK)


def gen_boot_ld(P):
    return banner("/*", "linker script for the boot ROM image").replace("\n/*", "\n *").rstrip() + " */\n" + """
OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
  ROM (rx)  : ORIGIN = 0x%(rom).8X, LENGTH = %(romsz)d
  BRAM (rw) : ORIGIN = 0x%(bram).8X, LENGTH = %(bootstack)d
}

SECTIONS
{
  .text : {
    KEEP(*(.text.start))
    *(.text .text.*)
  } > ROM
  .rodata : ALIGN(4) {
    *(.rodata .rodata.*)
    *(.srodata .srodata.*)
  } > ROM
  .data : { *(.data .data.* .sdata .sdata.*) } > BRAM
  .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.* COMMON) } > BRAM
  ASSERT(SIZEOF(.data) == 0, "boot ROM code must not use initialised data")
  ASSERT(SIZEOF(.bss) == 0, "boot ROM code must not use static variables")
  __stack_top = ORIGIN(BRAM) + LENGTH(BRAM);
  __rom_end = .;
  /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
""" % dict(rom=P.rom["base"], romsz=P.rom["size"],
           bram=P.ram["base"] + P.ram["size"] - BOOT_STACK, bootstack=BOOT_STACK)


def gen_test_ld(P, what, first_section, ram_size=None):
    tohost = P.reg("sysctrl", "TOHOST")
    ram_size = ram_size or P.ram["size"]
    return banner("/*", "linker script for " + what).replace("\n/*", "\n *").rstrip() + " */\n" + """
OUTPUT_ARCH("riscv")
ENTRY(_start)

SECTIONS
{
  . = 0x%(tohost).8X;
  .tohost (NOLOAD) : { *(.tohost) }
  . = 0x%(ram).8X;
  .text : { *(%(first)s) *(.text .text.*) }
  . = ALIGN(0x1000);
  .data : { *(.data .data.* .sdata .sdata.* .rodata .rodata.* .srodata .srodata.*) }
  .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
  _end = .;
  ASSERT(_end <= 0x%(ramend).8X, "test does not fit in RAM")
}
""" % dict(tohost=tohost, ram=P.ram["base"], first=first_section,
           ramend=P.ram["base"] + ram_size)


def gen_tcl(P):
    return banner("#", "Vivado build settings") + """
set NRV_PART     %s
set NRV_CORE     %s
set NRV_CORE_PIPE %d
set NRV_CPU_HZ   %d
set NRV_VERSION  %s
""" % (P.part, P.default_core, 1 if P.default_core == "pipe" else 0, P.cpu_hz, P.version)


def gen_clock_xdc(P):
    period = 1e9 / P.osc_hz
    return banner("#", "primary clock constraint") + """
create_clock -name sys_clk_pin -period %.3f -waveform {0.000 %.3f} [get_ports CLK100MHZ]
""" % (period, period / 2)


# -----------------------------------------------------------------------------
# Documentation tables
# -----------------------------------------------------------------------------
def gen_docs(P):
    o = [banner("<!--", "memory map and register tables").replace("\n<!--", "\n").rstrip() + " -->\n"]
    o.append("## Memory map\n")
    o.append("| Region | Base | Size | Execute | Write |")
    o.append("|---|---|---|---|---|")
    for n in sorted(P.regions, key=lambda k: P.regions[k]["base"]):
        r = P.regions[n]
        o.append("| %s | `0x%08X` | %d B | %s | %s |" % (
            n, r["base"], r["size"], "yes" if r["exec"] else "no", "yes" if r["write"] else "no"))
    o.append("")
    o.append("Any access outside these regions, and any non-word access to the IO region, "
             "raises an access-fault exception. The top %d bytes of RAM hold the bootloader stack "
             "and cannot be loaded over UART.\n" % BOOT_STACK)
    o.append("## Peripheral registers\n")
    o.append("| Address | Name | Access | Description |")
    o.append("|---|---|---|---|")
    for pname, pd in P.periph.items():
        for r in pd["regs"]:
            o.append("| `0x%08X` | %s_%s | %s | %s |" % (r["addr"], pname.upper(), r["name"], r["acc"], r["desc"]))
    o.append("")
    o.append("## Control and status registers\n")
    o.append("| Number | Name | Access | Notes |")
    o.append("|---|---|---|---|")
    for c in P.csrs:
        o.append("| `0x%03X` | %s | %s | %s |" % (c["addr"], c["name"], c["acc"], c["desc"]))
    o.append("")
    o.append("Access codes: RW read/write; R read-only register in the IO map (writes ignored); "
             "W write-only; R* CSR whose writes are legal but ignored (WARL); RO CSR in the "
             "read-only CSR space (a write raises an illegal-instruction exception).\n")
    o.append("## Derived timing\n")
    o.append("| Quantity | Value |")
    o.append("|---|---|")
    o.append("| CPU clock | %d Hz |" % P.cpu_hz)
    o.append("| UART divisor | %d cycles/bit (baud %d, error %+.3f %%) |" % (P.uart_div, P.baud, 100 * P.uart_baud_err))
    o.append("| mtime tick | %d Hz (every %d cycles) |" % (P.tick_hz, P.timer_div))
    o.append("| Button debounce | %d ms (%d cycles) |" % (P.debounce_ms, P.debounce_cycles))
    o.append("| 7-segment scan | %d Hz per digit, %.1f ms full refresh |" % (P.seg7_digit_hz, 8000.0 / P.seg7_digit_hz))
    return "\n".join(o) + "\n"


def outputs(P):
    return {
        "rtl/gen/soc_params.vh": gen_vh(P),
        "sw/include/soc_map.h": gen_h(P),
        "sw/link/app.ld": gen_app_ld(P),
        "sw/link/boot.ld": gen_boot_ld(P),
        "sim/riscv_tests/link.ld": gen_test_ld(P, "riscv-tests (rv32ui/rv32mi, env p)", ".text.init"),
        "sim/arch_test/link.ld": gen_test_ld(P, "riscv-arch-test 2.7.4 (compliance RAM size)", ".text.init",
                                             P.compliance_ram_size),
        "fpga/constraints/clock_gen.xdc": gen_clock_xdc(P),
        "fpga/scripts/params_gen.tcl": gen_tcl(P),
        "docs/generated/memory_map.md": gen_docs(P),
        "host/soc_params.json": json.dumps(dict(
            _generated="DO NOT EDIT - tools/gen_all.py from params.json",
            ram_base=P.ram["base"], ram_size=P.ram["size"], boot_stack=BOOT_STACK,
            baud=P.baud, cpu_hz=P.cpu_hz, params_hash=params_hash()), indent=2) + "\n",
    }


def main():
    check = "--check" in sys.argv
    P = params_mod.load()
    stale = []
    for rel, text in outputs(P).items():
        path = os.path.join(ROOT, rel)
        old = None
        if os.path.exists(path):
            with open(path, newline="") as fh:
                old = fh.read()
        if old != text:
            stale.append(rel)
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", newline="\n") as fh:
                    fh.write(text)
    if check:
        if stale:
            print("STALE generated files: " + ", ".join(stale))
            print("Run: py tools/gen_all.py")
            sys.exit(1)
        print("generated files up to date (params %s)" % params_hash())
    else:
        print("gen_all: %d file(s) written, params %s" % (len(stale), params_hash()))


if __name__ == "__main__":
    main()
