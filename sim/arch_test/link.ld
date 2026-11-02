/* ======================================================================
 * GENERATED FILE - DO NOT EDIT.
 * Source : params.json (sha256/16 0346f45c48f06b4d)
 * Tool   : tools/gen_all.py
 * Content: linker script for riscv-arch-test 2.7.4 (compliance RAM size)
 * ====================================================================== */

OUTPUT_ARCH("riscv")
ENTRY(_start)

SECTIONS
{
  . = 0x40000400;
  .tohost (NOLOAD) : { *(.tohost) }
  . = 0x80000000;
  .text : { *(.text.init) *(.text .text.*) }
  . = ALIGN(0x1000);
  .data : { *(.data .data.* .sdata .sdata.* .rodata .rodata.* .srodata .srodata.*) }
  .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
  _end = .;
  ASSERT(_end <= 0x80400000, "test does not fit in RAM")
}
