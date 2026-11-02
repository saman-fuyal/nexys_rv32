/* =============================================================================
 * dhrystone/util.h - shim that replaces riscv-tests' benchmarks/common/util.h
 * -----------------------------------------------------------------------------
 * Purpose : Let the unmodified riscv-tests Dhrystone sources
 *           (sw/third_party/dhrystone) build on this runtime.
 * Behavior: read_csr() maps to CSR_READ; debug_printf to rt_printf.
 *           setStats(1) records mcycle/minstret at the start of the timed
 *           loop and setStats(0) prints the exact counts as a line
 *           "DHRY_STATS runs=<n> cycles=<c> instret=<i>", which
 *           tools/collect_results.py turns into DMIPS/MHz and CPI.
 * ========================================================================== */
#ifndef __UTIL_H
#define __UTIL_H

#include "rt.h"

#define read_csr(reg) CSR_READ(reg)
#define debug_printf rt_printf

void setStats(int enable);

#endif
