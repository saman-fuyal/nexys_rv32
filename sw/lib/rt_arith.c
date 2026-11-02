/* =============================================================================
 * rt_arith.c - integer multiply/divide helpers for RV32I (clang build only)
 * -----------------------------------------------------------------------------
 * Purpose : RV32I has no multiply or divide instructions, so the compiler
 *           calls helper routines. GCC builds link libgcc for them (the
 *           standard choice and what benchmark results assume). The clang
 *           cross-check build has no RISC-V compiler-rt available here, so
 *           it links these portable versions with the same names and ABI.
 * Behavior: Shift-and-add multiply and restoring division. Division by zero
 *           returns all ones (quotient) and the dividend (remainder), the
 *           values the M extension defines, so results match a real divider.
 * ========================================================================== */
#include <stdint.h>

uint32_t __mulsi3(uint32_t a, uint32_t b)
{
    uint32_t r = 0;
    while (b) {
        if (b & 1u) {
            r += a;
        }
        a <<= 1;
        b >>= 1;
    }
    return r;
}

static uint32_t udivmod(uint32_t n, uint32_t d, uint32_t *rem)
{
    if (d == 0) {
        *rem = n;
        return 0xFFFFFFFFu;
    }
    uint32_t q = 0, r = 0;
    for (int i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1u);
        if (r >= d) {
            r -= d;
            q |= 1u << i;
        }
    }
    *rem = r;
    return q;
}

uint32_t __udivsi3(uint32_t n, uint32_t d) { uint32_t r; return udivmod(n, d, &r); }
uint32_t __umodsi3(uint32_t n, uint32_t d) { uint32_t r; udivmod(n, d, &r); return r; }

int32_t __divsi3(int32_t n, int32_t d)
{
    uint32_t r;
    if (d == 0) {
        return -1;
    }
    uint32_t q = udivmod(n < 0 ? 0u - (uint32_t)n : (uint32_t)n,
                         d < 0 ? 0u - (uint32_t)d : (uint32_t)d, &r);
    return ((n < 0) != (d < 0)) ? (int32_t)(0u - q) : (int32_t)q;
}

int32_t __modsi3(int32_t n, int32_t d)
{
    uint32_t r;
    if (d == 0) {
        return n;
    }
    udivmod(n < 0 ? 0u - (uint32_t)n : (uint32_t)n, d < 0 ? 0u - (uint32_t)d : (uint32_t)d, &r);
    return (n < 0) ? (int32_t)(0u - r) : (int32_t)r;
}
