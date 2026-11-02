/* =============================================================================
 * boot_start.S - boot ROM entry (reset vector) and boot-time trap handler
 * -----------------------------------------------------------------------------
 * Purpose : First instructions after reset.
 * Behavior: Sets the stack to the top of RAM (the 256-byte area the host tool
 *           never loads over), points mtvec at boot_trap and calls
 *           boot_main(), which never returns. A trap while the bootloader runs
 *           calls boot_fatal(mcause, mepc, mtval) which reports it and stops.
 *           No gp: the boot code has no small-data section.
 * ========================================================================== */
    .section .text.start, "ax"
    .globl _start
_start:
    la      sp, __stack_top
    .option push
    .option arch, +zicsr
    la      t0, boot_trap
    csrw    mtvec, t0
    .option pop
    call    boot_main
1:  j       1b

    .balign 4
boot_trap:
    .option push
    .option arch, +zicsr
    csrr    a0, mcause
    csrr    a1, mepc
    csrr    a2, mtval
    .option pop
    la      sp, __stack_top
    call    boot_fatal
2:  j       2b
