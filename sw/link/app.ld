/* ======================================================================
 * GENERATED FILE - DO NOT EDIT.
 * Source : params.json (sha256/16 0346f45c48f06b4d)
 * Tool   : tools/gen_all.py
 * Content: linker script for programs loaded into RAM
 * ====================================================================== */

OUTPUT_ARCH("riscv")
ENTRY(_start)

STACK_SIZE = 4096;

MEMORY
{
  RAM (rwx) : ORIGIN = 0x80000000, LENGTH = 65536
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
  __load_limit = __stack_top - 256;
  ASSERT(__bss_end <= __stack_bottom, "program + stack do not fit in RAM")
  /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
