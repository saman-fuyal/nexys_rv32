/*
Copyright 2018 Embedded Microprocessor Benchmark Consortium (EEMBC)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Original Author: Shay Gal-on

Modified for nexys_rv32: timing uses the machine timer (mtime, 1 MHz) for
CoreMark's own report and mcycle/minstret for exact per-iteration numbers.
*/
#include "coremark.h"
#include "core_portme.h"

#if VALIDATION_RUN
volatile ee_s32 seed1_volatile = 0x3415;
volatile ee_s32 seed2_volatile = 0x3415;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PERFORMANCE_RUN
volatile ee_s32 seed1_volatile = 0x0;
volatile ee_s32 seed2_volatile = 0x0;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PROFILE_RUN
volatile ee_s32 seed1_volatile = 0x8;
volatile ee_s32 seed2_volatile = 0x8;
volatile ee_s32 seed3_volatile = 0x8;
#endif
volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;

#define EE_TICKS_PER_SEC SOC_TIMER_HZ

static CORETIMETYPE start_time_val, stop_time_val;
static uint64_t     cyc0, cyc1, ins0, ins1;

void start_time(void)
{
    start_time_val = (CORETIMETYPE)timer_now();
    cyc0 = rdcycle64();
    ins0 = rdinstret64();
}

void stop_time(void)
{
    cyc1 = rdcycle64();
    ins1 = rdinstret64();
    stop_time_val = (CORETIMETYPE)timer_now();
}

CORE_TICKS get_time(void)
{
    return (CORE_TICKS)(stop_time_val - start_time_val);
}

secs_ret time_in_secs(CORE_TICKS ticks)
{
    return (secs_ret)(ticks / EE_TICKS_PER_SEC);
}

ee_u32 default_num_contexts = 1;

void portable_init(core_portable *p, int *argc, char *argv[])
{
    (void)argc;
    (void)argv;
    if (sizeof(ee_ptr_int) != sizeof(ee_u8 *)) {
        ee_printf("ERROR! Please define ee_ptr_int to a type that holds a pointer!\n");
    }
    if (sizeof(ee_u32) != 4) {
        ee_printf("ERROR! Please define ee_u32 to a 32b unsigned type!\n");
    }
    p->portable_id = 1;
}

void portable_fini(core_portable *p)
{
    p->portable_id = 0;
    ee_printf("CM_STATS iterations=%u cycles=%u instret=%u\n",
              (unsigned)ITERATIONS, (unsigned)(cyc1 - cyc0), (unsigned)(ins1 - ins0));
}

int ee_printf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = rt_vprintf(fmt, ap);
    va_end(ap);
    return n;
}
