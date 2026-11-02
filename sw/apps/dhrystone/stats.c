/* =============================================================================
 * dhrystone/stats.c - exact cycle and instruction counts for Dhrystone
 * -----------------------------------------------------------------------------
 * Purpose : riscv-tests' harness calls setStats(1) just before and
 *           setStats(0) just after the timed loop.
 * Behavior: Prints "DHRY_STATS runs=<n> cycles=<c> instret=<i>" for the timed
 *           loop only. DMIPS/MHz = 10^6 * runs / (cycles * 1757).
 * ========================================================================== */
#include "rt.h"

static uint64_t c0, i0;

void setStats(int enable)
{
    if (enable) {
        c0 = rdcycle64();
        i0 = rdinstret64();
    } else {
        uint64_t c = rdcycle64() - c0;
        uint64_t i = rdinstret64() - i0;
        rt_printf("DHRY_STATS runs=%u cycles=%u instret=%u\n",
                  (uint32_t)NUMBER_OF_RUNS, (uint32_t)c, (uint32_t)i);
    }
}
