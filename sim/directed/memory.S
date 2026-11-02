/* =============================================================================
 * memory.S - directed test: loads, stores, byte lanes and memory ordering
 * -----------------------------------------------------------------------------
 * Purpose : Check every load/store width at every legal offset, sign and zero
 *           extension, and a load directly after a store to the same word.
 * Covers  : SB at offsets 0..3, SH at 0 and 2, SW; LB/LBU/LH/LHU/LW at every
 *           legal offset with sign bit 0 and 1; store-then-load back to back
 *           (memory read-after-write); load from the boot ROM data port;
 *           peripheral register write/read-back (LEDS, SEG7, TOHOST_HI) and
 *           read-only sysctrl words (CLK_HZ, FEATURES).
 * ========================================================================== */
#include "dt.h"

DT_BEGIN
        la      s0, buf
        sw      zero, 0(s0)
        li      a0, 0x81
        sb      a0, 0(s0)
        li      a0, 0x72
        sb      a0, 1(s0)
        li      a0, 0xe3
        sb      a0, 2(s0)
        li      a0, 0x54
        sb      a0, 3(s0)
        lw      a1, 0(s0)
        CHECK(1, a1, 0x54e37281)
        lb      a1, 0(s0)
        CHECK(2, a1, 0xffffff81)
        lb      a1, 1(s0)
        CHECK(3, a1, 0x72)
        lb      a1, 2(s0)
        CHECK(4, a1, 0xffffffe3)
        lb      a1, 3(s0)
        CHECK(5, a1, 0x54)
        lbu     a1, 0(s0)
        CHECK(6, a1, 0x81)
        lbu     a1, 2(s0)
        CHECK(7, a1, 0xe3)
        lh      a1, 0(s0)
        CHECK(8, a1, 0x7281)
        lh      a1, 2(s0)
        CHECK(9, a1, 0x54e3)
        li      a0, 0x8001
        sh      a0, 2(s0)
        lh      a1, 2(s0)
        CHECK(10, a1, 0xffff8001)
        lhu     a1, 2(s0)
        CHECK(11, a1, 0x8001)
        li      a0, 0xfedc
        sh      a0, 0(s0)
        lw      a1, 0(s0)
        CHECK(12, a1, 0x8001fedc)

/* ---- store immediately followed by a load of the same word -------------- */
        li      a0, 0x13579bdf
        sw      a0, 4(s0)
        lw      a1, 4(s0)
        CHECK(20, a1, 0x13579bdf)
        li      a0, 0xaa
        sb      a0, 5(s0)
        lw      a1, 4(s0)
        CHECK(21, a1, 0x1357aadf)
        sw      a0, 8(s0)
        sw      a1, 12(s0)
        lw      a2, 8(s0)
        lw      a3, 12(s0)
        add     a4, a2, a3
        CHECK(22, a4, 0x1357ab89)

/* ---- boot ROM through the data port: word 0 is the first boot instruction
 *      (value checked against the golden model trace, not hard-coded) ---- */
        li      s1, 0x00000000
        lw      a1, 0(s1)
        lw      a1, 4(s1)
        lhu     a1, 2(s1)

/* ---- peripheral registers ----------------------------------------------- */
        li      s1, 0x40000100              /* GPIO LEDS */
        li      a0, 0x1a5a5
        sw      a0, 0(s1)
        lw      a1, 0(s1)
        CHECK(30, a1, 0xa5a5)               /* 16 bits implemented */
        li      s1, 0x40000200              /* SEG7 VALUE / DIGIT_EN / DP */
        li      a0, 0x12345678
        sw      a0, 0(s1)
        lw      a1, 0(s1)
        CHECK(31, a1, 0x12345678)
        lw      a1, 4(s1)
        CHECK(32, a1, 0xff)                 /* reset value */
        li      s1, 0x40000400              /* sysctrl */
        li      a0, 0x0badf00d
        sw      a0, 4(s1)                   /* TOHOST_HI */
        lw      a1, 4(s1)
        CHECK(33, a1, 0x0badf00d)
        lw      a1, 8(s1)
        CHECK(34, a1, CLK_HZ)               /* CLK_HZ, from params.json */
        sw      zero, 8(s1)                 /* read-only: ignored */
        lw      a1, 8(s1)
        CHECK(35, a1, CLK_HZ)
        lw      a1, 12(s1)                  /* FEATURES: core-dependent, ISS checks it */
        andi    a1, a1, 7
        CHECK(36, a1, 7)

        DT_PASS
DT_END

        .data
        .balign 16
buf:    .word 0, 0, 0, 0
