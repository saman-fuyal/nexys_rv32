/* =============================================================================
 * switches_leds/main.c - mirror the slide switches on the LEDs
 * -----------------------------------------------------------------------------
 * Purpose : Exercise GPIO input and output.
 * Behavior: LED[15:0] follow SW[15:0]; the switch value is also shown in hex
 *           on the 7-segment display and printed whenever it changes.
 *           Pressing BTND (down) ends the program with exit code 0.
 * ========================================================================== */
#include "rt.h"

int main(void)
{
    uint32_t last = 0xFFFFFFFFu;
    printf("switches_leds: flip SW0..SW15, press BTND to stop\n");
    buttons_clear(0x1Fu);
    for (;;) {
        uint32_t sw = switches_read();
        led_write(sw);
        if (sw != last) {
            seg7_write(sw);
            printf("SW=%04x\n", sw);
            last = sw;
        }
        if (buttons_events() & BTN_D) {
            printf("BTND pressed, bye\n");
            return 0;
        }
    }
}
