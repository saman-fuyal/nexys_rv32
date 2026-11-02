/* =============================================================================
 * model_test.h - riscv-arch-test 2.7.4 target macros for nexys_rv32
 * -----------------------------------------------------------------------------
 * Purpose : The DUT-specific part of the architectural test suite: how a test
 *           boots, halts and marks its signature region.
 * Behavior: Tests start at the RAM base with nothing to copy. RVMODEL_HALT
 *           writes 1 to sysctrl TOHOST; the testbench stops and dumps the
 *           words from begin_signature to end_signature, which
 *           sim/run_sim.py compares with the Sail-generated
 *           *.reference_output shipped in the suite. No console output and
 *           no software/external interrupts are modelled, so those macros are
 *           empty (the I, privilege and Zifencei suites do not use them).
 * ========================================================================== */
#ifndef _COMPLIANCE_MODEL_H
#define _COMPLIANCE_MODEL_H

#define RVMODEL_DATA_SECTION                                            \
        .pushsection .tohost, "aw", @nobits;                            \
        .align 8; .global tohost; tohost: .dword 0;                     \
        .align 8; .global fromhost; fromhost: .dword 0;                 \
        .popsection;

#define RVMODEL_BOOT

#define RVMODEL_HALT                                                    \
        .option push; .option norelax;                                  \
        li      t0, 0x40000400;                                         \
        li      t1, 1;                                                  \
        sw      t1, 0(t0);                                              \
        .option pop;                                                    \
  halt_loop: j halt_loop;

#define RVMODEL_DATA_BEGIN                                              \
        RVMODEL_DATA_SECTION                                            \
        .align 4; .global begin_signature; begin_signature:

#define RVMODEL_DATA_END                                                \
        .align 4; .global end_signature; end_signature:

#define RVMODEL_IO_INIT
#define RVMODEL_IO_WRITE_STR(_R, _STR)
#define RVMODEL_IO_CHECK()
#define RVMODEL_IO_ASSERT_GPR_EQ(_S, _R, _I)
#define RVMODEL_IO_ASSERT_SFPR_EQ(_F, _R, _I)
#define RVMODEL_IO_ASSERT_DFPR_EQ(_D, _R, _I)

#define RVMODEL_SET_MSW_INT
#define RVMODEL_CLEAR_MSW_INT
#define RVMODEL_CLEAR_MTIMER_INT
#define RVMODEL_CLEAR_MEXT_INT

#endif
