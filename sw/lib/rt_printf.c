/* =============================================================================
 * rt_printf.c - small printf for the UART
 * -----------------------------------------------------------------------------
 * Purpose : Formatted output without a C library.
 * Behavior: Supports %c %s %d %i %u %x %X %p %% with optional '-' (left
 *           align), '0' (zero pad) and a decimal width. Length modifiers 'l'
 *           and 'z' are accepted and ignored (all are 32 bits on RV32).
 *           Numbers are converted by repeated division, so on RV32I each
 *           digit costs a libgcc __udivsi3/__umodsi3 call.
 * ========================================================================== */
#include "rt.h"

static int put_padded(const char *s, int len, int width, int left, char pad)
{
    int n = 0;
    if (!left) {
        while (len + n < width) {
            uart_putc(pad);
            n++;
        }
    }
    for (int i = 0; i < len; i++) {
        uart_putc(s[i]);
    }
    n += len;
    while (n < width) {
        uart_putc(' ');
        n++;
    }
    return n;
}

static int put_num(uint32_t v, unsigned base, int neg, int upper, int width, int left, char pad)
{
    char buf[12];
    int i = sizeof(buf);
    const char *dig = upper ? "0123456789ABCDEF" : "0123456789abcdef";
    do {
        buf[--i] = dig[v % base];
        v /= base;
    } while (v);
    if (neg) {
        if (pad == '0' && width > 0) {
            uart_putc('-');
            return 1 + put_padded(&buf[i], (int)sizeof(buf) - i, width - 1, left, pad);
        }
        buf[--i] = '-';
    }
    return put_padded(&buf[i], (int)sizeof(buf) - i, width, left, pad);
}

int rt_vprintf(const char *fmt, va_list ap)
{
    int n = 0;
    for (; *fmt; fmt++) {
        if (*fmt != '%') {
            uart_putc(*fmt);
            n++;
            continue;
        }
        fmt++;
        int left = 0, width = 0;
        char pad = ' ';
        if (*fmt == '-') {
            left = 1;
            fmt++;
        }
        if (*fmt == '0') {
            pad = '0';
            fmt++;
        }
        while (*fmt >= '0' && *fmt <= '9') {
            width = width * 10 + (*fmt - '0');
            fmt++;
        }
        while (*fmt == 'l' || *fmt == 'z') {
            fmt++;
        }
        switch (*fmt) {
        case 'c': {
            char c = (char)va_arg(ap, int);
            n += put_padded(&c, 1, width, left, ' ');
            break;
        }
        case 's': {
            const char *s = va_arg(ap, const char *);
            if (!s) {
                s = "(null)";
            }
            n += put_padded(s, (int)strlen(s), width, left, ' ');
            break;
        }
        case 'd':
        case 'i': {
            int v = va_arg(ap, int);
            uint32_t u = (v < 0) ? (uint32_t)(-(v + 1)) + 1u : (uint32_t)v;
            n += put_num(u, 10, v < 0, 0, width, left, pad);
            break;
        }
        case 'u':
            n += put_num(va_arg(ap, uint32_t), 10, 0, 0, width, left, pad);
            break;
        case 'x':
        case 'X':
            n += put_num(va_arg(ap, uint32_t), 16, 0, *fmt == 'X', width, left, pad);
            break;
        case 'p':
            uart_puts("0x");
            n += 2 + put_num((uint32_t)(uintptr_t)va_arg(ap, void *), 16, 0, 0, 8, 0, '0');
            break;
        case '%':
            uart_putc('%');
            n++;
            break;
        case '\0':
            return n;
        default:
            uart_putc('%');
            uart_putc(*fmt);
            n += 2;
            break;
        }
    }
    return n;
}

int rt_printf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = rt_vprintf(fmt, ap);
    va_end(ap);
    return n;
}
