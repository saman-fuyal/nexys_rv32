/* =============================================================================
 * traps.S - directed test: every exception path of the core
 * -----------------------------------------------------------------------------
 * Purpose : Check mcause, mepc and mtval for each exception the core raises,
 *           and that the trapping instruction has no side effect.
 * Covers  : illegal encodings (all-zero, all-one, compressed, bad funct7,
 *           RV64 shift amount, reserved branch/load/store funct3, bad
 *           ECALL fields, unknown CSR, write to a read-only CSR), EBREAK,
 *           ECALL, misaligned loads/stores/jumps/branches, load/store access
 *           faults (unmapped, ROM write, IO byte access, IO hole) and an
 *           instruction access fault (jump into the IO region).
 * ========================================================================== */
#include "dt.h"

DT_BEGIN

/* ---- illegal instructions: mcause 2, mtval = instruction bits ---------- */
ill1:   .word 0x00000000
        EXPECT_TRAP(1, 2, ill1, 0x00000000)
ill2:   .word 0xffffffff
        EXPECT_TRAP(2, 2, ill2, 0xffffffff)
ill3:   .word 0x00010001            /* low bits 01: a compressed encoding */
        EXPECT_TRAP(3, 2, ill3, 0x00010001)
ill4:   .word 0x02208033            /* add with funct7 = 0000001 (M ext)  */
        EXPECT_TRAP(4, 2, ill4, 0x02208033)
ill5:   .word 0x02009093            /* slli x1, x1, 32 (shamt[5] set)     */
        EXPECT_TRAP(5, 2, ill5, 0x02009093)
ill6:   .word 0x00002063            /* branch funct3 = 010 (reserved)     */
        EXPECT_TRAP(6, 2, ill6, 0x00002063)
ill7:   .word 0x00003083            /* ld (RV64 only)                     */
        EXPECT_TRAP(7, 2, ill7, 0x00003083)
ill8:   .word 0x00003023            /* sd (RV64 only)                     */
        EXPECT_TRAP(8, 2, ill8, 0x00003023)
ill9:   .word 0x000000f3            /* ecall with rd = x1                 */
        EXPECT_TRAP(9, 2, ill9, 0x000000f3)
ill10:  .word 0x7c0020f3            /* csrrs x1, 0x7c0 (not implemented)  */
        EXPECT_TRAP(10, 2, ill10, 0x7c0020f3)
ill11:  .word 0xf1401073            /* csrw mhartid, x0 (read-only CSR)   */
        EXPECT_TRAP(11, 2, ill11, 0xf1401073)
ill12:  .word 0x0000100b            /* custom-0 opcode                    */
        EXPECT_TRAP(12, 2, ill12, 0x0000100b)
ill13:  .word 0x0000400f            /* MISC-MEM funct3 = 100              */
        EXPECT_TRAP(13, 2, ill13, 0x0000400f)
ill14:  .word 0x00004073            /* SYSTEM funct3 = 100                */
        EXPECT_TRAP(14, 2, ill14, 0x00004073)
ill15:  .word 0x42005093            /* srli with funct7 = 0100001         */
        EXPECT_TRAP(15, 2, ill15, 0x42005093)
ill16:  .word 0x00001067            /* jalr funct3 = 001                  */
        EXPECT_TRAP(16, 2, ill16, 0x00001067)

/* A trapping instruction must not write rd. */
        li      a0, 0x1234
ill17:  .word 0xc0002573            /* csrrs a0, cycle (Zicntr absent)    */
        EXPECT_TRAP(17, 2, ill17, 0xc0002573)
        CHECK(18, a0, 0x1234)

/* ---- EBREAK (mtval = pc) and ECALL (mtval = 0) -------------------------- */
brk:    ebreak
        EXPECT_TRAP_L(20, 3, brk, brk)
ecl:    ecall
        EXPECT_TRAP(21, 11, ecl, 0)

/* ---- misaligned data accesses: mcause 4/6, mtval = address -------------- */
        la      s0, buf
        li      a1, 0x5555
mlh:    lh      a1, 1(s0)
        EXPECT_TRAP_L(30, 4, mlh, buf + 1)
        CHECK(31, a1, 0x5555)
mlw:    lw      a1, 2(s0)
        EXPECT_TRAP_L(32, 4, mlw, buf + 2)
mlhu:   lhu     a1, 3(s0)
        EXPECT_TRAP_L(33, 4, mlhu, buf + 3)
msh:    sh      a1, 1(s0)
        EXPECT_TRAP_L(34, 6, msh, buf + 1)
msw:    sw      a1, 3(s0)
        EXPECT_TRAP_L(35, 6, msw, buf + 3)
        lw      a2, 0(s0)
        CHECK(36, a2, 0x11223344)       /* the faulting stores changed nothing */

/* ---- misaligned jump/branch targets: mcause 0, mtval = target ----------- */
        li      ra, 0x777
        SET_RESUME(mj_back)
mjal:   jal     ra, mtarget + 2
mj_back:
        EXPECT_TRAP_L(40, 0, mjal, mtarget + 2)
        CHECK(41, ra, 0x777)            /* rd not written */
        la      a3, mtarget
        addi    a3, a3, 2
        SET_RESUME(mjr_back)
mjalr:  jalr    ra, 0(a3)
mjr_back:
        EXPECT_TRAP_L(42, 0, mjalr, mtarget + 2)
        CHECK(43, ra, 0x777)
        la      a3, mtarget
        addi    a3, a3, 3               /* bit 0 is cleared, bit 1 stays: still misaligned */
        SET_RESUME(mjr3_back)
mjalr3: jalr    zero, 0(a3)
mjr3_back:
        EXPECT_TRAP_L(44, 0, mjalr3, mtarget + 2)
        SET_RESUME(mbr_back)
mbeq:   beq     zero, zero, mtarget + 2
mbr_back:
        EXPECT_TRAP_L(45, 0, mbeq, mtarget + 2)
        /* not-taken branch to a misaligned target: no exception */
        bne     zero, zero, mtarget + 2
        la      t3, dt_rec
        lw      t4, 0(t3)
        CHECK(46, t4, 0)

/* ---- access faults: mcause 5 (load) / 7 (store), mtval = address -------- */
        li      s1, 0x20000000          /* unmapped */
fl1:    lw      a1, 0(s1)
        EXPECT_TRAP(50, 5, fl1, 0x20000000)
fs1:    sw      a1, 0(s1)
        EXPECT_TRAP(51, 7, fs1, 0x20000000)
        li      s1, 0x00000000          /* boot ROM: readable, not writable */
fs2:    sw      a1, 0(s1)
        EXPECT_TRAP(52, 7, fs2, 0x00000000)
        li      s1, 0x00000800          /* just past the 2 KB ROM */
fl3:    lw      a1, 0(s1)
        EXPECT_TRAP(53, 5, fl3, 0x00000800)
        li      s1, 0x40000008          /* UART STATUS: byte access not allowed */
fl4:    lb      a1, 0(s1)
        EXPECT_TRAP(54, 5, fl4, 0x40000008)
fs4:    sh      a1, 0(s1)
        EXPECT_TRAP(55, 7, fs4, 0x40000008)
        li      s1, 0x40000f00          /* IO hole (no peripheral) */
fl5:    lw      a1, 0(s1)
        EXPECT_TRAP(56, 5, fl5, 0x40000f00)
        li      s1, 0x4000010c + 4      /* past the last GPIO register */
fl6:    lw      a1, 0(s1)
        EXPECT_TRAP(57, 5, fl6, 0x40000110)
        li      s1, 0x80010000          /* just past the 64 KB RAM */
fs7:    sw      a1, 0(s1)
        EXPECT_TRAP(58, 7, fs7, 0x80010000)

/* ---- instruction access fault: fetch from IO, mepc = mtval = target ----- */
        SET_RESUME(ifault_back)
        li      s1, 0x40000000
        jalr    ra, 0(s1)
ifault_back:
        EXPECT_TRAP_A(60, 1, 0x40000000, 0x40000000)
        SET_RESUME(ifault2_back)
        li      s1, 0x10000000          /* unmapped */
        jr      s1
ifault2_back:
        EXPECT_TRAP_A(61, 1, 0x10000000, 0x10000000)

/* ---- trap count: every case above trapped exactly once ------------------ */
        la      t3, dt_rec
        lw      t4, 12(t3)
        CHECK(70, t4, 39)

        DT_PASS

        .balign 4
mtarget:
        nop
        nop
        j       dt_fail

DT_END

        .data
        .balign 4
buf:    .word 0x11223344, 0x55667788
