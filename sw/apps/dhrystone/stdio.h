/* =============================================================================
 * dhrystone/stdio.h - freestanding stand-in for <stdio.h>
 * -----------------------------------------------------------------------------
 * Purpose : The unmodified Dhrystone sources include <stdio.h>; there is no C
 *           library, so this header forwards to the runtime (rt.h), which
 *           declares printf, strcpy, strcmp and memcpy.
 * Behavior: Declarations only.
 * ========================================================================== */
#include "rt.h"
