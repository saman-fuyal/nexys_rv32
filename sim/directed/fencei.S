/* =============================================================================
 * fencei.S - directed test: self-modifying code with FENCE.I (Zifencei)
 * -----------------------------------------------------------------------------
 * Purpose : The pipelined core may already hold stale instructions in IF/ID
 *           when a store rewrites code. FENCE.I must flush them.
 * Covers  : patch an instruction right after the FENCE.I (closest case) and
 *           one further away; run the patched code; FENCE as a NOP.
 * ========================================================================== */
#include "dt.h"

DT_BEGIN
        la      s0, patch1
        li      a0, 0x02a00593              /* addi a1, zero, 42 */
        sw      a0, 0(s0)
        fence.i
patch1: addi    a1, zero, 1                 /* replaced before it executes */
        CHECK(1, a1, 42)

        la      s0, patch2
        li      a0, 0x06300613              /* addi a2, zero, 99 */
        sw      a0, 0(s0)
        fence   rw, rw
        fence.i
        nop
        nop
patch2: addi    a2, zero, 2
        CHECK(2, a2, 99)

        DT_PASS
DT_END
