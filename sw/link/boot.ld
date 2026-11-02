/* ======================================================================
 * GENERATED FILE - DO NOT EDIT.
 * Source : params.json (sha256/16 0346f45c48f06b4d)
 * Tool   : tools/gen_all.py
 * Content: linker script for the boot ROM image
 * ====================================================================== */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY
{
  ROM (rx)  : ORIGIN = 0x00000000, LENGTH = 2048
  BRAM (rw) : ORIGIN = 0x8000FF00, LENGTH = 256
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
