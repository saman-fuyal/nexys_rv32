/* =============================================================================
 * dt.h - framework for the directed assembly tests
 * -----------------------------------------------------------------------------
 * Purpose : Small, explicit test harness so each directed test controls the
 *           exact instruction sequence (hazard distances, trap encodings).
 * Behavior: DT_BEGIN sets mtvec to dt_trap, which stores mcause/mepc/mtval in
 *           dt_rec and returns to mepc+4, or to the address in dt_resume if
 *           that is non-zero (needed after fetch faults and misaligned
 *           jumps). The handler uses only t5/t6, which tests must not use.
 *           CHECK(n, reg, value) fails test n if reg != value.
 *           EXPECT_TRAP(n, cause, epc_label, tval) checks the last trap.
 *           DT_PASS writes 1 to TOHOST; a failure writes (n << 1) | 1.
 *           Every test is also compared against the golden ISS trace, so the
 *           self-checks guard against an ISS and RTL that are wrong together.
 * ========================================================================== */
#ifndef DT_H
#define DT_H

#define TOHOST_ADDR 0x40000400
#define TESTNUM     gp

#define DT_BEGIN                                    \
    .section .text.init, "ax";                      \
    .globl _start;                                  \
_start:                                             \
    la      t0, dt_trap;                            \
    .option push; .option arch, +zicsr;             \
    csrw    mtvec, t0;                              \
    .option pop;                                    \
    li      TESTNUM, 0;

#define DT_PASS                                     \
    li      t0, TOHOST_ADDR;                        \
    li      t1, 1;                                  \
    sw      t1, 0(t0);                              \
1:  j       1b;

#define CHECK(n, reg, val)                          \
    li      TESTNUM, n;                             \
    li      t4, val;                                \
    bne     reg, t4, dt_fail;

#define EXPECT_TRAP(n, cause, epc_label, tval)      \
    li      TESTNUM, n;                             \
    la      t3, dt_rec;                             \
    lw      t4, 0(t3);                              \
    li      t2, cause;                              \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 4(t3);                              \
    la      t2, epc_label;                          \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 8(t3);                              \
    li      t2, tval;                               \
    bne     t4, t2, dt_fail;                        \
    sw      zero, 0(t3);

/* Same, with an absolute mepc and mtval (fetch faults outside the program). */
#define EXPECT_TRAP_A(n, cause, epc, tval)          \
    li      TESTNUM, n;                             \
    la      t3, dt_rec;                             \
    lw      t4, 0(t3);                              \
    li      t2, cause;                              \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 4(t3);                              \
    li      t2, epc;                                \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 8(t3);                              \
    li      t2, tval;                               \
    bne     t4, t2, dt_fail;                        \
    sw      zero, 0(t3);

/* Same, but mtval is compared with an address label. */
#define EXPECT_TRAP_L(n, cause, epc_label, tval_label) \
    li      TESTNUM, n;                             \
    la      t3, dt_rec;                             \
    lw      t4, 0(t3);                              \
    li      t2, cause;                              \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 4(t3);                              \
    la      t2, epc_label;                          \
    bne     t4, t2, dt_fail;                        \
    lw      t4, 8(t3);                              \
    la      t2, tval_label;                         \
    bne     t4, t2, dt_fail;                        \
    sw      zero, 0(t3);

#define SET_RESUME(label)                           \
    la      t3, label;                              \
    la      t4, dt_resume;                          \
    sw      t3, 0(t4);

#define DT_END                                      \
dt_fail:                                            \
    slli    t0, TESTNUM, 1;                         \
    ori     t0, t0, 1;                              \
    li      t1, TOHOST_ADDR;                        \
    sw      t0, 0(t1);                              \
2:  j       2b;                                     \
    .balign 4;                                      \
dt_trap:                                            \
    .option push; .option arch, +zicsr;             \
    la      t6, dt_rec;                             \
    csrr    t5, mcause;                             \
    sw      t5, 0(t6);                              \
    csrr    t5, mepc;                               \
    sw      t5, 4(t6);                              \
    csrr    t5, mtval;                              \
    sw      t5, 8(t6);                              \
    lw      t5, 12(t6);                             \
    addi    t5, t5, 1;                              \
    sw      t5, 12(t6);                             \
    la      t6, dt_resume;                          \
    lw      t5, 0(t6);                              \
    beqz    t5, 3f;                                 \
    sw      zero, 0(t6);                            \
    csrw    mepc, t5;                               \
    mret;                                           \
3:  csrr    t5, mepc;                               \
    addi    t5, t5, 4;                              \
    csrw    mepc, t5;                               \
    mret;                                           \
    .option pop;                                    \
    .data;                                          \
    .balign 16;                                     \
dt_rec:    .word 0, 0, 0, 0;                        \
dt_resume: .word 0;                                 \
    .section .tohost, "aw", @nobits;                \
    .balign 8;                                      \
tohost: .dword 0;

#endif
