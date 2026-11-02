/* =============================================================================
 * boot.c - UART bootloader in the boot ROM
 * -----------------------------------------------------------------------------
 * Purpose : Load programs into RAM over the USB-UART without rebuilding the
 *           bitstream, then start them.
 * Behavior: After reset it prints a banner, shows B007000<v> on the 7-segment
 *           display and serves commands from host/rvload.py. If SW15 is up at
 *           reset it skips the host and jumps to the RAM base, re-running the
 *           program still in block RAM (RAM keeps its contents through
 *           CPU_RESET).
 * Protocol: (all multi-byte fields little-endian; every reply starts with
 *           'K' = ok or 'E' + 1 error byte)
 *   'P'                         ping   -> 'K' "RVBL" ver ram_base ram_size limit
 *   'W' addr len                write  -> 'K' (range ok) or 'E' r
 *        data[len] crc32                -> 'K' crc32 or 'E' c
 *   'R' addr len                read   -> 'K' data[len] crc32   or 'E' r
 *   'G' addr                    go     -> 'K', then jumps to addr
 *   anything else                      -> 'E' '?'
 *   Writes must lie in [ram_base, limit): the top 256 bytes of RAM hold this
 *   program's stack. CRC-32 is the IEEE 802.3 polynomial (same as zlib).
 * Limits  : no .data or .bss (the ROM is read-only and RAM is the target),
 *           no multiply/divide (no libgcc). boot.ld enforces the first.
 * ========================================================================== */
#include <stdint.h>
#include "soc_map.h"

#define BOOT_VERSION 1u
#define LOAD_LIMIT   (SOC_RAM_BASE + SOC_RAM_SIZE - SOC_BOOT_STACK)

static void putc_(uint32_t c)
{
    while (SOC_REG(UART_STATUS) & UART_TX_BUSY) {
    }
    SOC_REG(UART_TXDATA) = c & 0xFFu;
}

static void puts_(const char *s)
{
    while (*s) {
        putc_((uint8_t)*s++);
    }
}

static void puthex(uint32_t v)
{
    for (int i = 28; i >= 0; i -= 4) {
        uint32_t d = (v >> i) & 0xFu;
        putc_(d < 10u ? '0' + d : 'a' + d - 10u);
    }
}

static uint32_t getc_(void)
{
    while (!(SOC_REG(UART_STATUS) & UART_RX_VALID)) {
    }
    return SOC_REG(UART_RXDATA) & 0xFFu;
}

static uint32_t get32(void)
{
    uint32_t v = getc_();
    v |= getc_() << 8;
    v |= getc_() << 16;
    v |= getc_() << 24;
    return v;
}

static void put32(uint32_t v)
{
    putc_(v);
    putc_(v >> 8);
    putc_(v >> 16);
    putc_(v >> 24);
}

static uint32_t crc32_byte(uint32_t crc, uint32_t b)
{
    crc ^= b;
    for (int k = 0; k < 8; k++) {
        crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return crc;
}

static int range_ok(uint32_t addr, uint32_t len)
{
    return addr >= SOC_RAM_BASE && addr <= LOAD_LIMIT && len <= LOAD_LIMIT - addr;
}

void boot_fatal(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    puts_("\r\nBOOT TRAP mcause=");
    puthex(mcause);
    puts_(" mepc=");
    puthex(mepc);
    puts_(" mtval=");
    puthex(mtval);
    puts_("\r\n");
    SOC_REG(SEG7_VALUE) = 0xEEEE0000u | (mcause & 0xFFu);
    for (;;) {
    }
}

static void jump(uint32_t addr)
{
    while (SOC_REG(UART_STATUS) & UART_TX_BUSY) {
    }
    SOC_REG(GPIO_LEDS) = 0;
    ((void (*)(void))addr)();
}

void boot_main(void)
{
    SOC_REG(SEG7_VALUE) = 0xB0070000u | BOOT_VERSION;
    SOC_REG(GPIO_LEDS) = 0x8000u;
    if (SOC_REG(GPIO_SWITCHES) & 0x8000u) {
        puts_("\r\nnexys_rv32 boot: SW15 up, running RAM image\r\n");
        jump(SOC_RAM_BASE);
    }
    puts_("\r\nnexys_rv32 boot v1, RAM ");
    puthex(SOC_RAM_BASE);
    puts_("+");
    puthex(SOC_RAM_SIZE);
    puts_(", waiting for rvload\r\n");

    uint32_t loaded = 0;
    for (;;) {
        uint32_t cmd = getc_();
        if (cmd == 'P') {
            putc_('K');
            puts_("RVBL");
            putc_(BOOT_VERSION);
            put32(SOC_RAM_BASE);
            put32(SOC_RAM_SIZE);
            put32(LOAD_LIMIT);
        } else if (cmd == 'W' || cmd == 'R') {
            uint32_t addr = get32();
            uint32_t len = get32();
            if (!range_ok(addr, len)) {
                putc_('E');
                putc_('r');
                continue;
            }
            putc_('K');
            uint8_t *p = (uint8_t *)addr;
            uint32_t crc = 0xFFFFFFFFu;
            if (cmd == 'W') {
                for (uint32_t i = 0; i < len; i++) {
                    uint32_t b = getc_();
                    p[i] = (uint8_t)b;
                    crc = crc32_byte(crc, b);
                }
                crc = ~crc;
                if (get32() != crc) {
                    putc_('E');
                    putc_('c');
                    continue;
                }
                putc_('K');
                put32(crc);
                loaded += len;
                SOC_REG(SEG7_VALUE) = loaded;
                SOC_REG(GPIO_LEDS) = 0x8000u | (loaded >> 10);
            } else {
                for (uint32_t i = 0; i < len; i++) {
                    putc_(p[i]);
                    crc = crc32_byte(crc, p[i]);
                }
                put32(~crc);
            }
        } else if (cmd == 'G') {
            uint32_t addr = get32();
            putc_('K');
            jump(addr);
        } else {
            putc_('E');
            putc_('?');
        }
    }
}
