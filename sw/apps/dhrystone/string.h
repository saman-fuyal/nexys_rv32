/* =============================================================================
 * dhrystone/string.h - freestanding stand-in for <string.h>
 * -----------------------------------------------------------------------------
 * Purpose : The unmodified Dhrystone sources include <string.h>; there is no C
 *           library, so this header forwards to the runtime (rt.h), which
 *           declares printf, strcpy, strcmp and memcpy.
 * Behavior: Declarations only.
 * ========================================================================== */
#include "rt.h"
