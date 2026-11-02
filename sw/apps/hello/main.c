/* =============================================================================
 * hello/main.c - first program: print over the UART and identify the SoC
 * -----------------------------------------------------------------------------
 * Purpose : Prove the whole chain: GCC build, bootloader load, UART output.
 * Behavior: Prints a greeting, the core type, clock, misa and mimpid, then the
 *           cycles and instructions spent printing the greeting (so the CPI
 *           of a printf-heavy loop can be read off the terminal). Shows
 *           0x00C0FFEE on the 7-segment display and exits with code 0.
 * ========================================================================== */
#include "rt.h"

int main(void)
{
    uint64_t c0 = rdcycle64();
    uint64_t i0 = rdinstret64();
    printf("Hello from nexys_rv32!\n");
    uint64_t c1 = rdcycle64();
    uint64_t i1 = rdinstret64();

    uint32_t feat = SOC_REG(SYSCTRL_FEATURES);
    printf("core      : %s\n", (feat & 8u) ? "5-stage pipeline" : "multi-cycle");
    printf("clock     : %u Hz\n", SOC_REG(SYSCTRL_CLK_HZ));
    printf("misa      : %08x  mimpid: %08x\n", CSR_READ(misa), CSR_READ(mimpid));
    printf("features  : zicsr=%u timer_irq=%u zifencei=%u\n",
           feat & 1u, (feat >> 1) & 1u, (feat >> 2) & 1u);
    printf("greeting  : %u cycles, %u instructions\n",
           (uint32_t)(c1 - c0), (uint32_t)(i1 - i0));
    seg7_write(0x00C0FFEEu);
    led_write(0x0001u);
    return 0;
}
