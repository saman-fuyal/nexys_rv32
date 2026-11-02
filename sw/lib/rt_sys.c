/* =============================================================================
 * rt_sys.c - trap dispatch, program exit and memory/string functions
 * -----------------------------------------------------------------------------
 * Purpose : The C side of trap handling, rt_exit(), and the few C-library
 *           functions GCC may emit calls to even in freestanding code
 *           (memcpy, memset, memmove, memcmp) plus string helpers the
 *           benchmarks use.
 * Behavior: rt_trap() is called by crt0's rt_trap_entry with interrupts
 *           disabled by hardware. A machine-timer interrupt calls
 *           timer_irq_handler() and resumes at mepc. Any exception calls
 *           exception_handler(); the default prints the cause, shows it on
 *           the 7-segment display and exits with code 0x100 + mcause.
 *           Software must re-arm mtimecmp in timer_irq_handler(), otherwise
 *           the interrupt stays pending and fires again at once.
 * ========================================================================== */
#include "rt.h"

static const char *cause_name(uint32_t c)
{
    switch (c) {
    case 0:  return "instruction address misaligned";
    case 1:  return "instruction access fault";
    case 2:  return "illegal instruction";
    case 3:  return "breakpoint";
    case 4:  return "load address misaligned";
    case 5:  return "load access fault";
    case 6:  return "store address misaligned";
    case 7:  return "store access fault";
    case 11: return "ecall from M-mode";
    default: return "unknown";
    }
}

__attribute__((weak)) void timer_irq_handler(void)
{
    /* No handler installed: silence the timer so the core does not livelock. */
    timer_set_cmp(~0ull);
}

__attribute__((weak)) uint32_t exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    rt_printf("\n*** TRAP: %s (mcause=%u) mepc=%08x mtval=%08x\n",
              cause_name(mcause), mcause, mepc, mtval);
    seg7_write(0xEEEE0000u | (mcause & 0xFFu));
    rt_exit((int)(0x100u + mcause));
}

uint32_t rt_trap(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    if (mcause == (MCAUSE_IRQ | 7u)) {
        timer_irq_handler();
        return mepc;
    }
    return exception_handler(mcause, mepc, mtval);
}

void rt_exit(int code)
{
    uart_flush();
    SOC_REG(SYSCTRL_TOHOST) = (code == 0) ? 1u : (((uint32_t)code << 1) | 1u);
    for (;;) {
        __asm__ volatile ("" ::: "memory");
    }
}

void *memcpy(void *d, const void *s, size_t n)
{
    uint8_t *dp = (uint8_t *)d;
    const uint8_t *sp = (const uint8_t *)s;
    if ((((uintptr_t)dp | (uintptr_t)sp) & 3u) == 0) {
        while (n >= 4) {
            *(uint32_t *)dp = *(const uint32_t *)sp;
            dp += 4;
            sp += 4;
            n -= 4;
        }
    }
    while (n--) {
        *dp++ = *sp++;
    }
    return d;
}

void *memset(void *d, int c, size_t n)
{
    uint8_t *dp = (uint8_t *)d;
    while (n--) {
        *dp++ = (uint8_t)c;
    }
    return d;
}

void *memmove(void *d, const void *s, size_t n)
{
    uint8_t *dp = (uint8_t *)d;
    const uint8_t *sp = (const uint8_t *)s;
    if (dp < sp) {
        while (n--) {
            *dp++ = *sp++;
        }
    } else {
        while (n--) {
            dp[n] = sp[n];
        }
    }
    return d;
}

int memcmp(const void *a, const void *b, size_t n)
{
    const uint8_t *p = (const uint8_t *)a, *q = (const uint8_t *)b;
    for (; n; n--, p++, q++) {
        if (*p != *q) {
            return *p - *q;
        }
    }
    return 0;
}

size_t strlen(const char *s)
{
    size_t n = 0;
    while (s[n]) {
        n++;
    }
    return n;
}

/* A word holds a zero byte iff (w - 0x01010101) & ~w & 0x80808080 != 0.
 * strcmp/strcpy work a word at a time while both pointers are word-aligned,
 * the usual technique (PicoRV32's Dhrystone runtime does the same), so the
 * benchmark comparison is like for like. Aligned word reads never cross into
 * an unmapped region, because RAM is word-granular. */
#define HAS_ZERO(w) (((w) - 0x01010101u) & ~(w) & 0x80808080u)

int strcmp(const char *a, const char *b)
{
    if ((((uintptr_t)a | (uintptr_t)b) & 3u) == 0) {
        const uint32_t *wa = (const uint32_t *)a, *wb = (const uint32_t *)b;
        while (*wa == *wb && !HAS_ZERO(*wa)) {
            wa++;
            wb++;
        }
        a = (const char *)wa;
        b = (const char *)wb;
    }
    while (*a && *a == *b) {
        a++;
        b++;
    }
    return (unsigned char)*a - (unsigned char)*b;
}

char *strcpy(char *d, const char *s)
{
    char *r = d;
    if ((((uintptr_t)d | (uintptr_t)s) & 3u) == 0) {
        uint32_t *wd = (uint32_t *)d;
        const uint32_t *ws = (const uint32_t *)s;
        while (!HAS_ZERO(*ws)) {
            *wd++ = *ws++;
        }
        d = (char *)wd;
        s = (const char *)ws;
    }
    while ((*d++ = *s++)) {
    }
    return r;
}
