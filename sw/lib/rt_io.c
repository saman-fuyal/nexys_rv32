/* =============================================================================
 * rt_io.c - UART, timer and counter functions of the runtime
 * -----------------------------------------------------------------------------
 * Purpose : Polling UART I/O and machine-timer helpers (see rt.h).
 * Behavior: uart_putc waits while STATUS.TX_BUSY is set, then writes TXDATA.
 *           '\n' is sent as "\r\n" so terminals start a new line.
 *           64-bit counters are read high/low/high and retried if the high
 *           word changed, so a carry between the two reads cannot corrupt
 *           the value.
 * ========================================================================== */
#include "rt.h"

void uart_putc(char c)
{
    if (c == '\n') {
        uart_putc('\r');
    }
    while (SOC_REG(UART_STATUS) & UART_TX_BUSY) {
    }
    SOC_REG(UART_TXDATA) = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s) {
        uart_putc(*s++);
    }
}

int uart_try_getc(void)
{
    if (SOC_REG(UART_STATUS) & UART_RX_VALID) {
        return (int)(SOC_REG(UART_RXDATA) & 0xFFu);
    }
    return -1;
}

int uart_getc(void)
{
    int c;
    do {
        c = uart_try_getc();
    } while (c < 0);
    return c;
}

void uart_flush(void)
{
    while (SOC_REG(UART_STATUS) & UART_TX_BUSY) {
    }
}

uint64_t timer_now(void)
{
    uint32_t hi, lo, hi2;
    do {
        hi  = SOC_REG(TIMER_MTIME_HI);
        lo  = SOC_REG(TIMER_MTIME_LO);
        hi2 = SOC_REG(TIMER_MTIME_HI);
    } while (hi != hi2);
    return ((uint64_t)hi << 32) | lo;
}

void timer_set_cmp(uint64_t t)
{
    /* Privileged ISA recipe: park the high word so no spurious match can
     * happen between the two 32-bit writes. */
    SOC_REG(TIMER_MTIMECMP_HI) = 0xFFFFFFFFu;
    SOC_REG(TIMER_MTIMECMP_LO) = (uint32_t)t;
    SOC_REG(TIMER_MTIMECMP_HI) = (uint32_t)(t >> 32);
}

void delay_us(uint32_t us)
{
    uint64_t end = timer_now() + (uint64_t)us * (SOC_TIMER_HZ / 1000000u);
    while (timer_now() < end) {
    }
}

void delay_ms(uint32_t ms)
{
    while (ms--) {
        delay_us(1000u);
    }
}

uint64_t rdcycle64(void)
{
    uint32_t hi, lo, hi2;
    do {
        hi  = CSR_READ(mcycleh);
        lo  = CSR_READ(mcycle);
        hi2 = CSR_READ(mcycleh);
    } while (hi != hi2);
    return ((uint64_t)hi << 32) | lo;
}

uint64_t rdinstret64(void)
{
    uint32_t hi, lo, hi2;
    do {
        hi  = CSR_READ(minstreth);
        lo  = CSR_READ(minstret);
        hi2 = CSR_READ(minstreth);
    } while (hi != hi2);
    return ((uint64_t)hi << 32) | lo;
}
