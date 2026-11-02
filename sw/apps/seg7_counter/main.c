/* =============================================================================
 * seg7_counter/main.c - decimal counter on the 7-segment display
 * -----------------------------------------------------------------------------
 * Purpose : Exercise the display, the timer and the buttons.
 * Behavior: Counts up every TICK_US microseconds (default 100 ms) and shows
 *           the count in decimal (BCD) on the 8 digits, leading zeros
 *           blanked. LED[15:0] show the binary count.
 *             BTNC  pause / resume
 *             BTNU  reset to 0
 *             BTNL  count down instead of up, BTNR count up
 *             BTND  print the count and exit
 *           Builds for simulation pass -DTICK_US=... and -DMAX_COUNT=... so
 *           the run is short and ends by itself.
 * ========================================================================== */
#include "rt.h"

#ifndef TICK_US
#define TICK_US 100000u
#endif

static uint32_t to_bcd(uint32_t v, uint32_t *digits)
{
    uint32_t bcd = 0, n = 0;
    do {
        bcd |= (v % 10u) << (4u * n);
        v /= 10u;
        n++;
    } while (v && n < 8u);
    *digits = n;
    return bcd;
}

int main(void)
{
    uint32_t count = 0, running = 1, up = 1, nd;
    uint64_t next = timer_now() + TICK_US;
    printf("seg7_counter: BTNC pause, BTNU reset, BTNL down, BTNR up, BTND stop\n");
    buttons_clear(0x1Fu);
    for (;;) {
        uint32_t ev = buttons_events();
        if (ev) {
            buttons_clear(ev);
            if (ev & BTN_C) running = !running;
            if (ev & BTN_U) count = 0;
            if (ev & BTN_L) up = 0;
            if (ev & BTN_R) up = 1;
            if (ev & BTN_D) {
                printf("count=%u\n", count);
                return 0;
            }
        }
        if (timer_now() >= next) {
            next += TICK_US;
            if (running) {
                count = up ? count + 1u : count - 1u;
            }
            seg7_write(to_bcd(count, &nd));
            seg7_digits((1u << nd) - 1u);
            led_write(count);
#ifdef MAX_COUNT
            if (count == MAX_COUNT) {
                printf("count=%u\n", count);
                return 0;
            }
#endif
        }
    }
}
