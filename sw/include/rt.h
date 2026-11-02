/* =============================================================================
 * rt.h - nexys_rv32 bare-metal runtime API
 * -----------------------------------------------------------------------------
 * Purpose : The small library every program links: UART text I/O, a printf
 *           subset, the machine timer, LEDs/switches/buttons, the 7-segment
 *           display, CSR access and program exit.
 * Behavior: No C library is used. Programs build with -ffreestanding
 *           -nostdlib; integer multiply/divide come from libgcc (GCC) or
 *           sw/lib/rt_arith.c (clang cross-check build), both listed in the
 *           link map.
 * ========================================================================== */
#ifndef RT_H
#define RT_H

#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include "soc_map.h"

/* ---- UART ---------------------------------------------------------------- */
void     uart_putc(char c);
void     uart_puts(const char *s);
int      uart_getc(void);              /* blocks; returns 0..255            */
int      uart_try_getc(void);          /* returns -1 if nothing received     */
void     uart_flush(void);             /* wait until the last byte left      */

/* ---- printf subset: %c %s %d %i %u %x %X %p %%, flags '0' '-', width ---- */
int      rt_printf(const char *fmt, ...);
int      rt_vprintf(const char *fmt, va_list ap);
#define  printf rt_printf

/* ---- timer (mtime counts at SOC_TIMER_HZ, 1 MHz by default) -------------- */
uint64_t timer_now(void);
void     timer_set_cmp(uint64_t t);
void     delay_us(uint32_t us);
void     delay_ms(uint32_t ms);

/* ---- GPIO and display ---------------------------------------------------- */
static inline void     led_write(uint32_t v)    { SOC_REG(GPIO_LEDS) = v; }
static inline uint32_t led_read(void)           { return SOC_REG(GPIO_LEDS); }
static inline uint32_t switches_read(void)      { return SOC_REG(GPIO_SWITCHES); }
static inline uint32_t buttons_read(void)       { return SOC_REG(GPIO_BUTTONS); }
static inline uint32_t buttons_events(void)     { return SOC_REG(GPIO_BTN_EDGE); }
static inline void     buttons_clear(uint32_t m){ SOC_REG(GPIO_BTN_EDGE) = m; }
static inline void     seg7_write(uint32_t v)   { SOC_REG(SEG7_VALUE) = v; }
static inline void     seg7_digits(uint32_t m)  { SOC_REG(SEG7_DIGIT_EN) = m; }
static inline void     seg7_dp(uint32_t m)      { SOC_REG(SEG7_DP) = m; }

/* ---- CSRs ------------------------------------------------------------------
 * Since GCC 12 / binutils 2.38 the CSR instructions belong to the Zicsr
 * extension. Programs still build with -march=rv32i, so each access enables
 * zicsr locally with .option arch for that one instruction. */
#define CSR_READ(csr) ({ uint32_t v_;                                        \
    __asm__ volatile (".option push\n.option arch, +zicsr\n"                 \
                      "csrr %0, " #csr "\n.option pop" : "=r"(v_));         \
    v_; })
#define CSR_WRITE(csr, val) do { uint32_t v_ = (uint32_t)(val);             \
    __asm__ volatile (".option push\n.option arch, +zicsr\n"                 \
                      "csrw " #csr ", %0\n.option pop" :: "r"(v_) : "memory"); \
    } while (0)
#define CSR_SET(csr, val) do { uint32_t v_ = (uint32_t)(val);               \
    __asm__ volatile (".option push\n.option arch, +zicsr\n"                 \
                      "csrs " #csr ", %0\n.option pop" :: "r"(v_) : "memory"); \
    } while (0)
#define CSR_CLEAR(csr, val) do { uint32_t v_ = (uint32_t)(val);             \
    __asm__ volatile (".option push\n.option arch, +zicsr\n"                 \
                      "csrc " #csr ", %0\n.option pop" :: "r"(v_) : "memory"); \
    } while (0)

uint64_t rdcycle64(void);              /* mcycle, read hi/lo/hi safely       */
uint64_t rdinstret64(void);            /* minstret                           */

#define MSTATUS_MIE (1u << 3)
#define MIE_MTIE    (1u << 7)
#define MCAUSE_IRQ  (1u << 31)

static inline void irq_enable(void)  { CSR_SET(mstatus, MSTATUS_MIE); }
static inline void irq_disable(void) { CSR_CLEAR(mstatus, MSTATUS_MIE); }

/* ---- traps -----------------------------------------------------------------
 * crt0 points mtvec at rt_trap_entry, which saves the caller-saved registers
 * and calls rt_trap(). Interrupts call timer_irq_handler() (weak, override
 * it); exceptions call exception_handler() (weak, default prints the cause
 * and stops with a failure code). */
void     timer_irq_handler(void);
uint32_t exception_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval);

/* ---- exit ------------------------------------------------------------------
 * Waits for the UART, writes the result to sysctrl TOHOST (1 = success,
 * (code << 1) | 1 = failure) and stops. Returning from main() calls it. */
void     rt_exit(int code) __attribute__((noreturn));

/* ---- string/memory functions GCC may call implicitly ---------------------- */
void    *memcpy(void *d, const void *s, size_t n);
void    *memset(void *d, int c, size_t n);
void    *memmove(void *d, const void *s, size_t n);
int      memcmp(const void *a, const void *b, size_t n);
size_t   strlen(const char *s);
int      strcmp(const char *a, const char *b);
char    *strcpy(char *d, const char *s);

#endif
