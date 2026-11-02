// ======================================================================
// GENERATED FILE - DO NOT EDIT.
// Source : params.json (sha256/16 0346f45c48f06b4d)
// Tool   : tools/gen_all.py
// Content: SoC localparams, included inside module bodies
// ======================================================================

// Not every includer uses every constant: UNUSEDPARAM waived for this header.
// verilator lint_off UNUSEDPARAM
// Clocking and peripheral timing
localparam integer CPU_HZ          = 50000000;
localparam integer UART_DIV        = 434;  // cycles per bit, baud 115200 (error +0.006%)
localparam integer TIMER_DIV       = 50;  // cycles per mtime tick (1000000 Hz)
localparam integer DEBOUNCE_CYCLES = 500000;  // 10 ms
localparam integer SEG7_DIV        = 50000;  // cycles per digit

// Memory map (strict decode: anything outside a region faults)
localparam [31:0] RESET_VECTOR = 32'h00000000;
localparam [31:0] ROM_BASE = 32'h00000000;
localparam integer ROM_AW  = 11;  // 2048 bytes
localparam [31:0] RAM_BASE = 32'h80000000;
localparam integer RAM_AW  = 16;  // 65536 bytes
localparam [31:0] IO_BASE = 32'h40000000;
localparam integer IO_AW  = 12;  // 4096 bytes

// IO decode: addr[11:8] selects the peripheral, addr[7:2] the register
localparam [3:0] PIDX_UART     = 4'd0;
localparam [5:0] NREGS_UART     = 6'd3;
localparam [3:0] PIDX_GPIO     = 4'd1;
localparam [5:0] NREGS_GPIO     = 6'd4;
localparam [3:0] PIDX_SEG7     = 4'd2;
localparam [5:0] NREGS_SEG7     = 6'd3;
localparam [3:0] PIDX_TIMER    = 4'd3;
localparam [5:0] NREGS_TIMER    = 6'd4;
localparam [3:0] PIDX_SYSCTRL  = 4'd4;
localparam [5:0] NREGS_SYSCTRL  = 6'd5;

// Feature flags and identification
localparam FEAT_ZICSR     = 1'b1;
localparam FEAT_TIMER_IRQ = 1'b1;
localparam FEAT_ZIFENCEI  = 1'b1;
localparam [31:0] MISA_VALUE   = 32'h40000100;
localparam [31:0] MIMPID_VALUE = 32'h00010000;
localparam [31:0] BUILD_ID     = 32'h00010000;
// Simulation-only: RAM address bits of the riscv-arch-test configuration
localparam integer COMPLIANCE_RAM_AW = 22;
// verilator lint_on UNUSEDPARAM
