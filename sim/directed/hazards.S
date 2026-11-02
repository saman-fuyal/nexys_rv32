/* =============================================================================
 * hazards.S - directed test: data and control hazards in the pipeline
 * -----------------------------------------------------------------------------
 * Purpose : Exercise every forwarding path and the load-use interlock at each
 *           producer-consumer distance, plus branch/jump flushes.
 * Covers  : distance 1 (MEM->EX), 2 (WB->EX), 3 (WB write-through in ID) for
 *           ALU results; load-use for ALU, store data, store address, branch
 *           and jalr consumers; CSR read result used at once; both operands
 *           forwarded from different stages; youngest producer wins when two
 *           in-flight instructions write the same register; x0 never
 *           forwarded; branch and jump back-to-back; jal/jalr link register
 *           used at once.
 *           The multi-cycle core runs the same file (no hazards there), so a
 *           pass on both cores with matching ISS traces is the check.
 * ========================================================================== */
#include "dt.h"

DT_BEGIN
        la      s0, data

/* ---- ALU -> ALU at distances 1, 2, 3 ------------------------------------ */
        li      a0, 5
        addi    a1, a0, 1               /* dist 1 */
        CHECK(1, a1, 6)
        li      a0, 7
        nop
        addi    a1, a0, 1               /* dist 2 */
        CHECK(2, a1, 8)
        li      a0, 9
        nop
        nop
        addi    a1, a0, 1               /* dist 3: register file write-through */
        CHECK(3, a1, 10)

/* ---- both operands, from MEM and WB at the same time --------------------- */
        li      a2, 100
        li      a3, 23
        add     a4, a2, a3              /* a2 from WB, a3 from MEM */
        CHECK(4, a4, 123)
        li      a3, 23
        li      a2, 100
        sub     a4, a2, a3              /* a2 from MEM, a3 from WB */
        CHECK(5, a4, 77)

/* ---- youngest producer wins ---------------------------------------------- */
        li      a5, 1
        li      a5, 2
        li      a5, 3
        addi    a6, a5, 0
        CHECK(6, a6, 3)

/* ---- x0 is never forwarded ----------------------------------------------- */
        addi    zero, zero, 55
        add     a7, zero, zero
        CHECK(7, a7, 0)
        lw      zero, 0(s0)
        add     a7, zero, zero
        CHECK(8, a7, 0)

/* ---- load-use for each consumer type ------------------------------------- */
        lw      a0, 0(s0)               /* 0x00000010 */
        addi    a1, a0, 1               /* ALU */
        CHECK(10, a1, 0x11)
        lw      a0, 4(s0)               /* 0x00000004: offset */
        add     a1, s0, a0
        lw      a2, 0(a1)               /* load address from a load */
        CHECK(11, a2, 0x4)
        lw      a0, 8(s0)               /* 0xcafef00d */
        sw      a0, 12(s0)              /* store data from a load */
        lw      a1, 12(s0)
        CHECK(12, a1, 0xcafef00d)
        lw      a0, 0(s0)
        add     a1, s0, a0
        sw      a0, 0(a1)               /* store address from a load (via ALU) */
        lw      a2, 16(s0)
        CHECK(13, a2, 0x10)
        lw      a0, 0(s0)
        beq     a0, zero, dt_fail       /* branch on a load */
        li      a1, 0x10
        bne     a0, a1, dt_fail
        la      a0, jtab
        lw      a1, 0(a0)
        jalr    ra, 0(a1)               /* jalr target from a load */
        CHECK(14, a0, 0x99)
        lb      a0, 20(s0)              /* sign-extended byte used at once */
        addi    a0, a0, 0
        CHECK(15, a0, 0xffffff80)
        lhu     a0, 20(s0)
        addi    a0, a0, 0
        CHECK(16, a0, 0x0080)

/* ---- CSR read result used at once ---------------------------------------- */
        li      a0, 0x5a5a
        .option push
        .option arch, +zicsr
        csrw    mscratch, a0
        csrr    a1, mscratch
        .option pop
        addi    a2, a1, 1
        CHECK(20, a2, 0x5a5b)

/* ---- link registers used at once ----------------------------------------- */
        jal     ra, 1f
1:      la      a0, 1b
        bne     ra, a0, dt_fail
        la      a0, 2f
        jalr    a1, 0(a0)
2:      la      a2, 2b
        bne     a1, a2, dt_fail
        la      a0, 3f
        jalr    a0, 0(a0)               /* rd == rs1 */
3:      la      a2, 3b
        bne     a0, a2, dt_fail

/* ---- control flow back to back ------------------------------------------- */
        li      a0, 0
        beq     zero, zero, 4f
        addi    a0, a0, 1               /* flushed */
        addi    a0, a0, 1               /* flushed */
4:      j       5f
        addi    a0, a0, 1               /* flushed */
5:      bne     zero, zero, dt_fail     /* not taken */
        beq     zero, zero, 6f
        j       dt_fail
6:      CHECK(30, a0, 0)

/* ---- a loop with a load-use inside it ------------------------------------ */
        li      a0, 0
        li      a1, 8
        mv      a2, s0
7:      lw      a3, 24(a2)
        add     a0, a0, a3
        addi    a1, a1, -1
        bnez    a1, 7b
        CHECK(31, a0, 8)

        DT_PASS

fn99:   li      a0, 0x99
        ret

DT_END

        .data
        .balign 4
data:   .word 0x00000010, 0x00000004, 0xcafef00d, 0, 0
        .word 0x00000080
        .word 1, 1, 1, 1, 1, 1, 1, 1
jtab:   .word fn99
