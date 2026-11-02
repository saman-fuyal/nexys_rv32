/* =============================================================================
 * csr.S - directed test: CSR instruction semantics and WARL fields
 * -----------------------------------------------------------------------------
 * Purpose : Check each CSR instruction form and the writable/read-only bits
 *           of every implemented CSR.
 * Covers  : CSRRW/RS/RC and the immediate forms (old value returned, rs1=x0
 *           and uimm=0 do not write), mstatus/mie/mtvec/mepc masks, misa and
 *           mstatush and mip ignoring writes, read-only CSR read with
 *           CSRRS x0 (legal) and identification values, mcycle counting and
 *           write, minstret counting and the write-suppresses-increment rule.
 * ========================================================================== */
#include "dt.h"

        .option arch, +zicsr

DT_BEGIN
/* ---- read/modify/write forms on mscratch -------------------------------- */
        li      a0, 0x0f0f0f0f
        csrw    mscratch, a0
        li      a1, 0x000000ff
        csrrs   a2, mscratch, a1
        CHECK(1, a2, 0x0f0f0f0f)
        csrr    a2, mscratch
        CHECK(2, a2, 0x0f0f0fff)
        csrrc   a2, mscratch, a1
        CHECK(3, a2, 0x0f0f0fff)
        csrr    a2, mscratch
        CHECK(4, a2, 0x0f0f0f00)
        csrrwi  a2, mscratch, 0x15
        CHECK(5, a2, 0x0f0f0f00)
        csrrsi  a2, mscratch, 0x0a
        CHECK(6, a2, 0x15)
        csrrci  a2, mscratch, 0x01
        CHECK(7, a2, 0x1f)
        csrr    a2, mscratch
        CHECK(8, a2, 0x1e)
        csrrs   a2, mscratch, zero          /* no write */
        csrrsi  a3, mscratch, 0             /* no write */
        CHECK(9, a3, 0x1e)
        csrrw   zero, mscratch, a0          /* rd = x0: write only */
        csrr    a2, mscratch
        CHECK(10, a2, 0x0f0f0f0f)

/* ---- WARL masks ---------------------------------------------------------- */
        li      a0, -1
        csrw    mstatus, a0
        csrr    a1, mstatus
        CHECK(20, a1, 0x00001888)           /* MPP=11, MPIE, MIE */
        csrw    mstatus, zero
        csrr    a1, mstatus
        CHECK(21, a1, 0x00001800)           /* MPP stays M */
        csrw    mie, a0
        csrr    a1, mie
        CHECK(22, a1, 0x00000080)           /* only MTIE */
        csrw    mie, zero
        la      t0, dt_trap
        ori     a1, t0, 3
        csrw    mtvec, a1                   /* vectored mode not supported */
        csrr    a2, mtvec
        bne     a2, t0, dt_fail
        csrw    mepc, a0
        csrr    a1, mepc
        CHECK(23, a1, 0xfffffffc)
        csrr    a1, misa
        CHECK(24, a1, 0x40000100)
        csrw    misa, zero                  /* WARL: ignored, no trap */
        csrr    a1, misa
        CHECK(25, a1, 0x40000100)
        csrw    mstatush, a0
        csrr    a1, mstatush
        CHECK(26, a1, 0)
        csrw    mip, a0
        csrr    a1, mip
        CHECK(27, a1, 0)                    /* MTIP is 0 (mtimecmp all ones) */
        csrw    mcause, a0
        csrr    a1, mcause
        CHECK(28, a1, 0xffffffff)
        csrw    mtval, a0
        csrr    a1, mtval
        CHECK(29, a1, 0xffffffff)

/* ---- read-only identification registers --------------------------------- */
        csrr    a1, mvendorid
        CHECK(30, a1, 0)
        csrr    a1, marchid
        CHECK(31, a1, 0)
        csrr    a1, mimpid
        CHECK(32, a1, 0x00010000)
        csrr    a1, mhartid
        CHECK(33, a1, 0)
        csrr    a1, mconfigptr
        CHECK(34, a1, 0)
        csrrs   a1, mhartid, zero           /* read with rs1 = x0: legal */
        csrrsi  a1, mhartid, 0
        la      t3, dt_rec
        lw      t4, 12(t3)
        CHECK(35, t4, 0)                    /* no trap so far */

/* ---- counters ------------------------------------------------------------ */
        csrr    a0, mcycle
        nop
        nop
        csrr    a1, mcycle
        bgeu    a0, a1, dt_fail             /* mcycle advanced */
        csrr    a0, minstret
        nop
        nop
        csrr    a1, minstret
        sub     a2, a1, a0
        CHECK(40, a2, 3)                    /* two nops + first csrr retired */
        csrwi   minstret, 0
        csrr    a0, minstret
        CHECK(41, a0, 0)                    /* the write suppressed its own increment */
        li      a0, -1
        csrw    minstret, a0
        csrw    minstreth, a0
        nop
        csrr    a1, minstret
        CHECK(42, a1, 0)                    /* 64-bit wrap */
        csrr    a1, minstreth
        CHECK(43, a1, 0)
        csrw    mcycleh, zero
        li      a0, 1000
        csrw    mcycle, a0
        csrr    a1, mcycle
        li      a2, 1000
        bltu    a1, a2, dt_fail
        li      a2, 1100
        bgeu    a1, a2, dt_fail

        DT_PASS
DT_END
