/* =============================================================================
 * crt0.S - program startup and trap entry for programs in RAM
 * -----------------------------------------------------------------------------
 * Purpose : First code a program runs after the bootloader jumps to it.
 * Behavior: _start sets gp and sp, clears .bss, points mtvec at
 *           rt_trap_entry, calls main() and passes its return value to
 *           rt_exit(). .data needs no copy: the bootloader (or the testbench)
 *           loads the whole image into RAM where it runs.
 *           rt_trap_entry saves the 16 caller-saved registers, calls
 *           rt_trap(mcause, mepc, mtval), which returns the address to
 *           resume at, restores the registers and executes mret. Callee-saved
 *           registers are preserved by the C code itself.
 * ========================================================================== */
    .section .text.start, "ax"
    .globl _start
_start:
    .option push
    .option norelax
    la      gp, __global_pointer$
    .option pop
    la      sp, __stack_top

    la      t0, __bss_start
    la      t1, __bss_end
1:  bgeu    t0, t1, 2f
    sw      zero, 0(t0)
    addi    t0, t0, 4
    j       1b
2:
    .option push
    .option arch, +zicsr
    la      t0, rt_trap_entry
    csrw    mtvec, t0
    .option pop

    call    main
    call    rt_exit
3:  j       3b

    .text
    .balign 4
    .globl rt_trap_entry
rt_trap_entry:
    addi    sp, sp, -64
    sw      ra,  0(sp)
    sw      t0,  4(sp)
    sw      t1,  8(sp)
    sw      t2, 12(sp)
    sw      a0, 16(sp)
    sw      a1, 20(sp)
    sw      a2, 24(sp)
    sw      a3, 28(sp)
    sw      a4, 32(sp)
    sw      a5, 36(sp)
    sw      a6, 40(sp)
    sw      a7, 44(sp)
    sw      t3, 48(sp)
    sw      t4, 52(sp)
    sw      t5, 56(sp)
    sw      t6, 60(sp)
    .option push
    .option arch, +zicsr
    csrr    a0, mcause
    csrr    a1, mepc
    csrr    a2, mtval
    call    rt_trap
    csrw    mepc, a0
    .option pop
    lw      ra,  0(sp)
    lw      t0,  4(sp)
    lw      t1,  8(sp)
    lw      t2, 12(sp)
    lw      a0, 16(sp)
    lw      a1, 20(sp)
    lw      a2, 24(sp)
    lw      a3, 28(sp)
    lw      a4, 32(sp)
    lw      a5, 36(sp)
    lw      a6, 40(sp)
    lw      a7, 44(sp)
    lw      t3, 48(sp)
    lw      t4, 52(sp)
    lw      t5, 56(sp)
    lw      t6, 60(sp)
    addi    sp, sp, 64
    .option push
    .option arch, +zicsr
    mret
    .option pop
