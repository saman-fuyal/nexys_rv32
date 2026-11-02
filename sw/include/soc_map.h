// ======================================================================
// GENERATED FILE - DO NOT EDIT.
// Source : params.json (sha256/16 0346f45c48f06b4d)
// Tool   : tools/gen_all.py
// Content: C register addresses and SoC constants
// ======================================================================

#ifndef SOC_MAP_H
#define SOC_MAP_H

#define SOC_CPU_HZ        50000000u
#define SOC_UART_BAUD     115200u
#define SOC_TIMER_HZ      1000000u
#define SOC_ROM_BASE      0x00000000u
#define SOC_ROM_SIZE      2048u
#define SOC_RAM_BASE      0x80000000u
#define SOC_RAM_SIZE      65536u
#define SOC_IO_BASE       0x40000000u
#define SOC_BOOT_STACK    256u
#define SOC_FEAT_ZICSR    1
#define SOC_FEAT_TIMERIRQ 1
#define SOC_FEAT_ZIFENCEI 1

#define SOC_REG(addr) (*(volatile unsigned int *)(addr))

/* uart @ 0x40000000 */
#define UART_TXDATA              0x40000000u  /* W Write a byte to transmit (bits 7:0). Ignored while STATUS.TX */
#define UART_RXDATA              0x40000004u  /* R Received byte (bits 7:0). Reading clears STATUS.RX_VALID. */
#define UART_STATUS              0x40000008u  /* RW bit0 TX_BUSY, bit1 RX_VALID, bit2 RX_OVERRUN (write 1 to cle */

/* gpio @ 0x40000100 */
#define GPIO_LEDS                0x40000100u  /* RW LED[15:0]; 1 = on */
#define GPIO_SWITCHES            0x40000104u  /* R SW[15:0] after a 2-flop synchronizer */
#define GPIO_BUTTONS             0x40000108u  /* R Debounced buttons: bit0 BTNC, bit1 BTNU, bit2 BTNL, bit3 BTN */
#define GPIO_BTN_EDGE            0x4000010Cu  /* RW Sticky press events, same bit order as BUTTONS; write 1 to c */

/* seg7 @ 0x40000200 */
#define SEG7_VALUE               0x40000200u  /* RW 32-bit value shown as 8 hex digits; digit 7 (left) = bits 31 */
#define SEG7_DIGIT_EN            0x40000204u  /* RW bit n enables digit n (reset 0xFF) */
#define SEG7_DP                  0x40000208u  /* RW bit n lights the decimal point of digit n */

/* timer @ 0x40000300 */
#define TIMER_MTIME_LO           0x40000300u  /* RW mtime[31:0], counts at timer.tick_hz */
#define TIMER_MTIME_HI           0x40000304u  /* RW mtime[63:32] */
#define TIMER_MTIMECMP_LO        0x40000308u  /* RW mtimecmp[31:0] (reset all ones) */
#define TIMER_MTIMECMP_HI        0x4000030Cu  /* RW mtimecmp[63:32] (reset all ones); MTIP = (mtime >= mtimecmp) */

/* sysctrl @ 0x40000400 */
#define SYSCTRL_TOHOST           0x40000400u  /* RW Test result mailbox: 1 = pass, (n<<1)|1 = fail with code n.  */
#define SYSCTRL_TOHOST_HI        0x40000404u  /* RW Upper word of the riscv-tests tohost doubleword; scratch */
#define SYSCTRL_CLK_HZ           0x40000408u  /* R CPU clock frequency in Hz */
#define SYSCTRL_FEATURES         0x4000040Cu  /* R bit0 zicsr, bit1 timer_irq, bit2 zifencei, bit3 core is pipe */
#define SYSCTRL_BUILD_ID         0x40000410u  /* R project.build_id */

/* UART STATUS bits */
#define UART_TX_BUSY     (1u << 0)
#define UART_RX_VALID    (1u << 1)
#define UART_RX_OVERRUN  (1u << 2)
#define UART_RX_FRAMEERR (1u << 3)
/* Button bits */
#define BTN_C (1u << 0)
#define BTN_U (1u << 1)
#define BTN_L (1u << 2)
#define BTN_R (1u << 3)
#define BTN_D (1u << 4)

/* CSR numbers */
#define CSR_MSTATUS     0x300
#define CSR_MISA        0x301
#define CSR_MIE         0x304
#define CSR_MTVEC       0x305
#define CSR_MSTATUSH    0x310
#define CSR_MSCRATCH    0x340
#define CSR_MEPC        0x341
#define CSR_MCAUSE      0x342
#define CSR_MTVAL       0x343
#define CSR_MIP         0x344
#define CSR_MCYCLE      0xB00
#define CSR_MINSTRET    0xB02
#define CSR_MCYCLEH     0xB80
#define CSR_MINSTRETH   0xB82
#define CSR_MVENDORID   0xF11
#define CSR_MARCHID     0xF12
#define CSR_MIMPID      0xF13
#define CSR_MHARTID     0xF14
#define CSR_MCONFIGPTR  0xF15

#endif
