/* =============================================================================
 * riscv_test.h (env_hil) - riscv-tests "p" environment for the on-board self-test
 * -----------------------------------------------------------------------------
 * Purpose : Run the unmodified rv32ui/rv32mi tests on the board through the
 *           UART bootloader and see their result without a debugger.
 * Behavior: Includes the upstream environment (upstream/env/p/riscv_test.h,
 *           BSD licence, unchanged) and replaces only RVTEST_CODE_BEGIN, whose
 *           write_tohost now (1) prints "RVTEST <code>" on the UART, code =
 *           TESTNUM as 8 hex digits (1 = pass, else 2*n+1 for failing test n),
 *           waiting until the last bit has left the UART, (2) writes TOHOST as
 *           before, so simulation stops there, and (3) jumps to address 0, the
 *           bootloader, instead of looping. Everything before write_tohost is
 *           byte-for-byte the upstream macro; model/hil.py env_matches_upstream()
 *           checks that in every regression, so an upstream update cannot
 *           drift silently.
 * Registers: write_tohost is reached with the test finished; t5, t6, a0 and
 *           a1 are free to use.
 * ========================================================================== */
#include "../upstream/env/p/riscv_test.h"

#define HIL_UART 0x40000000

/* t6 = character; waits while UART STATUS.TX_BUSY (bit 0), then writes TXDATA */
#define HIL_PUTC(c)                                                     \
        li t6, c;                                                       \
        li t5, HIL_UART;                                                \
  91:   lw a0, 8(t5);                                                   \
        andi a0, a0, 1;                                                 \
        bnez a0, 91b;                                                   \
        sw t6, 0(t5);

#define HIL_REPORT                                                      \
        HIL_PUTC(82) HIL_PUTC(86) HIL_PUTC(84) HIL_PUTC(69)             \
        HIL_PUTC(83) HIL_PUTC(84) HIL_PUTC(32)                          \
        mv a1, TESTNUM;                                                 \
        li t6, 8;                                                       \
  92:   srli a0, a1, 28;                                                \
        addi a0, a0, 48;                                                \
        li t5, 58;                                                      \
        blt a0, t5, 93f;                                                \
        addi a0, a0, 39;                                                \
  93:   li t5, HIL_UART;                                                \
  94:   lw ra, 8(t5);                                                   \
        andi ra, ra, 1;                                                 \
        bnez ra, 94b;                                                   \
        sw a0, 0(t5);                                                   \
        slli a1, a1, 4;                                                 \
        addi t6, t6, -1;                                                \
        bnez t6, 92b;                                                   \
        HIL_PUTC(10)                                                    \
        li t5, HIL_UART;                                                \
  95:   lw a0, 8(t5);                                                   \
        andi a0, a0, 1;                                                 \
        bnez a0, 95b;

#undef RVTEST_CODE_BEGIN
#define RVTEST_CODE_BEGIN                                               \
        .section .text.init;                                            \
        .align  6;                                                      \
        .weak stvec_handler;                                            \
        .weak mtvec_handler;                                            \
        .globl _start;                                                  \
_start:                                                                 \
        /* reset vector */                                              \
        j reset_vector;                                                 \
        .align 2;                                                       \
trap_vector:                                                            \
        /* test whether the test came from pass/fail */                 \
        csrr t5, mcause;                                                \
        li t6, CAUSE_USER_ECALL;                                        \
        beq t5, t6, write_tohost;                                       \
        li t6, CAUSE_SUPERVISOR_ECALL;                                  \
        beq t5, t6, write_tohost;                                       \
        li t6, CAUSE_MACHINE_ECALL;                                     \
        beq t5, t6, write_tohost;                                       \
        /* if an mtvec_handler is defined, jump to it */                \
        la t5, mtvec_handler;                                           \
        beqz t5, 1f;                                                    \
        jr t5;                                                          \
        /* was it an interrupt or an exception? */                      \
  1:    csrr t5, mcause;                                                \
        bgez t5, handle_exception;                                      \
        INTERRUPT_HANDLER;                                              \
handle_exception:                                                       \
        /* we don't know how to handle whatever the exception was */    \
  other_exception:                                                      \
        /* some unhandlable exception occurred */                       \
  1:    ori TESTNUM, TESTNUM, 1337;                                     \
  write_tohost:                                                         \
        HIL_REPORT;                                                     \
        sw TESTNUM, tohost, t5;                                         \
        sw zero, tohost + 4, t5;                                        \
        jalr x0, 0(x0);                                                 \
reset_vector:                                                           \
        INIT_XREG;                                                      \
        RISCV_MULTICORE_DISABLE;                                        \
        INIT_RNMI;                                                      \
        INIT_SATP;                                                      \
        INIT_PMP;                                                       \
        DELEGATE_NO_TRAPS;                                              \
        li TESTNUM, 0;                                                  \
        la t0, trap_vector;                                             \
        csrw mtvec, t0;                                                 \
        CHECK_XLEN;                                                     \
        /* if an stvec_handler is defined, delegate exceptions to it */ \
        la t0, stvec_handler;                                           \
        beqz t0, 1f;                                                    \
        csrw stvec, t0;                                                 \
        li t0, (1 << CAUSE_LOAD_PAGE_FAULT) |                           \
               (1 << CAUSE_STORE_PAGE_FAULT) |                          \
               (1 << CAUSE_FETCH_PAGE_FAULT) |                          \
               (1 << CAUSE_MISALIGNED_FETCH) |                          \
               (1 << CAUSE_USER_ECALL) |                                \
               (1 << CAUSE_BREAKPOINT);                                 \
        csrw medeleg, t0;                                               \
1:      csrwi mstatus, 0;                                               \
        init;                                                           \
        EXTRA_INIT;                                                     \
        EXTRA_INIT_TIMER;                                               \
        la t0, 1f;                                                      \
        csrw mepc, t0;                                                  \
        csrr a0, mhartid;                                               \
        mret;                                                           \
1:
