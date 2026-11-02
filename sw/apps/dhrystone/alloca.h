/* =============================================================================
 * dhrystone/alloca.h - alloca for the freestanding Dhrystone build
 * -----------------------------------------------------------------------------
 * Purpose : dhrystone_main.c includes <alloca.h>; there is no C library, so
 *           this maps alloca to the compiler builtin.
 * Behavior: Stack allocation, freed when main() returns.
 * ========================================================================== */
#ifndef ALLOCA_SHIM_H
#define ALLOCA_SHIM_H
#define alloca(n) __builtin_alloca(n)
#endif
