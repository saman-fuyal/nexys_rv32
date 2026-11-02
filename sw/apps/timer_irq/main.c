/* =============================================================================
 * timer_irq/main.c - machine timer interrupt demo
 * -----------------------------------------------------------------------------
 * Purpose : Show interrupts working: the main loop waits in a WFI loop while the
 *           timer interrupt counts ticks.
 * Behavior: The handler fires every PERIOD_US (default 1 ms), re-arms
 *           mtimecmp relative to the previous deadline (no drift), counts the
 *           tick and toggles LED0 every 500 ticks (1 Hz blink at 1 ms). The
 *           main loop prints every 1000 ticks. With -DTICKS=n it stops after
 *           n ticks and checks the count; BTND also stops it.
 *           WFI is a legal NOP on this core (the spec allows it), so the
 *           loop spins instead of sleeping; the printed loop-pass count makes
 *           that visible. The interrupt preempts the loop either way.
 * ========================================================================== */
#include "rt.h"

#ifndef PERIOD_US
#define PERIOD_US 1000u
#endif

static volatile uint32_t ticks;
static uint64_t deadline;

void timer_irq_handler(void)
{
    deadline += PERIOD_US;
    timer_set_cmp(deadline);
    ticks++;
    if (ticks % 500u == 0u) {
        led_write(led_read() ^ 1u);
    }
}

int main(void)
{
    uint32_t shown = 0, loops = 0;
    printf("timer_irq: period %u us, BTND to stop\n", PERIOD_US);
    buttons_clear(0x1Fu);
    deadline = timer_now() + PERIOD_US;
    timer_set_cmp(deadline);
    CSR_SET(mie, MIE_MTIE);
    irq_enable();
    for (;;) {
        __asm__ volatile (".option push\n.option arch, +zicsr\nwfi\n.option pop");
        loops++;
        uint32_t t = ticks;
#ifdef TICKS
        if (t >= TICKS) {
            irq_disable();
            printf("ticks=%u (expected %u)\n", t, (uint32_t)TICKS);
            return (t == TICKS) ? 0 : 1;
        }
#endif
        if (t / 1000u != shown) {
            shown = t / 1000u;
            seg7_write(t);
            printf("ticks=%u\n", t);
        }
        if (buttons_events() & BTN_D) {
            irq_disable();
            printf("stopped at ticks=%u, loop passes=%u\n", t, loops);
            return 0;
        }
    }
}
