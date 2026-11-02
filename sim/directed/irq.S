/* =============================================================================
 * irq.S - directed test: machine timer interrupt
 * -----------------------------------------------------------------------------
 * Purpose : Check interrupt entry, masking and return.
 * Covers  : MTIP visible in mip; no interrupt while mstatus.MIE = 0 or
 *           mie.MTIE = 0 even with MTIP pending; an interrupt taken as soon
 *           as both are set; mcause = 0x80000007, mtval = 0, mepc = the next
 *           unexecuted instruction; MIE cleared and MPIE set inside the
 *           handler; MRET restoring MIE; WFI executing as a NOP; several
 *           interrupts in a loop with the handler re-arming mtimecmp.
 * ========================================================================== */
#include "dt.h"

#define MTIME_LO     0x40000300
#define MTIME_HI     0x40000304
#define MTIMECMP_LO  0x40000308
#define MTIMECMP_HI  0x4000030c

        .option arch, +zicsr

DT_BEGIN
        la      t0, irq_handler
        csrw    mtvec, t0
        li      s2, MTIMECMP_LO
        li      s3, MTIMECMP_HI
        li      s5, MTIME_LO

/* ---- MTIP pending, interrupts masked ------------------------------------ */
        sw      zero, 0(s3)
        sw      zero, 0(s2)                 /* mtimecmp = 0 <= mtime: pending */
        li      a0, 50
1:      addi    a0, a0, -1
        bnez    a0, 1b
        csrr    a1, mip
        CHECK(1, a1, 0x80)
        li      a0, 0x80
        csrs    mie, a0                     /* MTIE on, MIE still off */
        li      a0, 50
2:      addi    a0, a0, -1
        bnez    a0, 2b
        CHECK(2, s4, 0)                     /* handler has not run */

/* ---- enable: taken at once ---------------------------------------------- */
        csrsi   mstatus, 8
irq_next:
        nop
        CHECK(3, s4, 1)
        la      t0, irq_next
        bne     s6, t0, dt_fail             /* mepc = first unexecuted instruction */
        li      t0, 0x80000007
        bne     s7, t0, dt_fail
        CHECK(4, s8, 0)                     /* mtval */
        CHECK(5, s9, 0x1880)                /* in handler: MIE=0, MPIE=1, MPP=M */
        csrr    a1, mstatus
        CHECK(6, a1, 0x1888)                /* MRET restored MIE */

/* ---- periodic interrupts, handler re-arms ------------------------------- */
        li      s4, 0
        li      s10, 5                      /* re-arm 5 times, then disarm */
        lw      a0, 0(s5)
        addi    a0, a0, 3
        li      t0, -1
        sw      t0, 0(s3)
        sw      a0, 0(s2)
        sw      zero, 0(s3)
3:      wfi
        li      t0, 6
        bltu    s4, t0, 3b
        CHECK(7, s4, 6)
        csrr    a1, mip
        CHECK(8, a1, 0)                     /* disarmed */

        csrci   mstatus, 8
        DT_PASS

        .balign 4
irq_handler:
        csrr    s7, mcause
        csrr    s6, mepc
        csrr    s8, mtval
        csrr    s9, mstatus
        addi    s4, s4, 1
        li      t5, -1
        sw      t5, 0(s3)                   /* park mtimecmp high word */
        beqz    s10, 9f
        addi    s10, s10, -1
        lw      t5, 0(s5)
        addi    t5, t5, 3
        sw      t5, 0(s2)
        sw      zero, 0(s3)
9:      mret

DT_END
