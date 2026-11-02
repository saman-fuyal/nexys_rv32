<!-- ======================================================================
 GENERATED FILE - DO NOT EDIT.
 Source : params.json (sha256/16 0346f45c48f06b4d)
 Tool   : tools/gen_all.py
 Content: memory map and register tables
 ====================================================================== -->

## Memory map

| Region | Base | Size | Execute | Write |
|---|---|---|---|---|
| bootrom | `0x00000000` | 2048 B | yes | no |
| io | `0x40000000` | 4096 B | no | yes |
| ram | `0x80000000` | 65536 B | yes | yes |

Any access outside these regions, and any non-word access to the IO region, raises an access-fault exception. The top 256 bytes of RAM hold the bootloader stack and cannot be loaded over UART.

## Peripheral registers

| Address | Name | Access | Description |
|---|---|---|---|
| `0x40000000` | UART_TXDATA | W | Write a byte to transmit (bits 7:0). Ignored while STATUS.TX_BUSY=1. |
| `0x40000004` | UART_RXDATA | R | Received byte (bits 7:0). Reading clears STATUS.RX_VALID. |
| `0x40000008` | UART_STATUS | RW | bit0 TX_BUSY, bit1 RX_VALID, bit2 RX_OVERRUN (write 1 to clear), bit3 RX_FRAME_ERR (write 1 to clear) |
| `0x40000100` | GPIO_LEDS | RW | LED[15:0]; 1 = on |
| `0x40000104` | GPIO_SWITCHES | R | SW[15:0] after a 2-flop synchronizer |
| `0x40000108` | GPIO_BUTTONS | R | Debounced buttons: bit0 BTNC, bit1 BTNU, bit2 BTNL, bit3 BTNR, bit4 BTND; 1 = pressed |
| `0x4000010C` | GPIO_BTN_EDGE | RW | Sticky press events, same bit order as BUTTONS; write 1 to clear |
| `0x40000200` | SEG7_VALUE | RW | 32-bit value shown as 8 hex digits; digit 7 (left) = bits 31:28 |
| `0x40000204` | SEG7_DIGIT_EN | RW | bit n enables digit n (reset 0xFF) |
| `0x40000208` | SEG7_DP | RW | bit n lights the decimal point of digit n |
| `0x40000300` | TIMER_MTIME_LO | RW | mtime[31:0], counts at timer.tick_hz |
| `0x40000304` | TIMER_MTIME_HI | RW | mtime[63:32] |
| `0x40000308` | TIMER_MTIMECMP_LO | RW | mtimecmp[31:0] (reset all ones) |
| `0x4000030C` | TIMER_MTIMECMP_HI | RW | mtimecmp[63:32] (reset all ones); MTIP = (mtime >= mtimecmp) |
| `0x40000400` | SYSCTRL_TOHOST | RW | Test result mailbox: 1 = pass, (n<<1)|1 = fail with code n. The simulation testbench stops on a write; in hardware it is a plain register. |
| `0x40000404` | SYSCTRL_TOHOST_HI | RW | Upper word of the riscv-tests tohost doubleword; scratch |
| `0x40000408` | SYSCTRL_CLK_HZ | R | CPU clock frequency in Hz |
| `0x4000040C` | SYSCTRL_FEATURES | R | bit0 zicsr, bit1 timer_irq, bit2 zifencei, bit3 core is pipelined |
| `0x40000410` | SYSCTRL_BUILD_ID | R | project.build_id |

## Control and status registers

| Number | Name | Access | Notes |
|---|---|---|---|
| `0x300` | mstatus | RW | MIE (bit 3), MPIE (bit 7); MPP (bits 12:11) reads 3 |
| `0x301` | misa | R* | 0x40000100 (RV32I). Writes ignored (WARL). |
| `0x304` | mie | RW | MTIE (bit 7) only |
| `0x305` | mtvec | RW | Direct mode only; bits 1:0 read 0 |
| `0x310` | mstatush | R* | Reads 0; writes ignored |
| `0x340` | mscratch | RW | Scratch |
| `0x341` | mepc | RW | bits 1:0 read 0 |
| `0x342` | mcause | RW | Interrupt bit 31, code bits 30:0 |
| `0x343` | mtval | RW | Faulting address or instruction |
| `0x344` | mip | R* | MTIP (bit 7) from the timer; writes ignored |
| `0xB00` | mcycle | RW | Cycle counter low |
| `0xB02` | minstret | RW | Retired-instruction counter low |
| `0xB80` | mcycleh | RW | Cycle counter high |
| `0xB82` | minstreth | RW | Retired-instruction counter high |
| `0xF11` | mvendorid | RO | 0 |
| `0xF12` | marchid | RO | 0 |
| `0xF13` | mimpid | RO | 0x00010000 |
| `0xF14` | mhartid | RO | 0 |
| `0xF15` | mconfigptr | RO | 0 |

Access codes: RW read/write; R read-only register in the IO map (writes ignored); W write-only; R* CSR whose writes are legal but ignored (WARL); RO CSR in the read-only CSR space (a write raises an illegal-instruction exception).

## Derived timing

| Quantity | Value |
|---|---|
| CPU clock | 50000000 Hz |
| UART divisor | 434 cycles/bit (baud 115200, error +0.006 %) |
| mtime tick | 1000000 Hz (every 50 cycles) |
| Button debounce | 10 ms (500000 cycles) |
| 7-segment scan | 1000 Hz per digit, 8.0 ms full refresh |
