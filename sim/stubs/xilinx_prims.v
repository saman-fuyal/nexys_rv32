// =============================================================================
// xilinx_prims.v - lint-only stand-ins for the two Xilinx primitives that
// fpga_top.v uses when params.json selects a clock other than 100 MHz
// -----------------------------------------------------------------------------
// Purpose : Verilator lint needs a declaration for every module. These match
//           the ports and parameters fpga_top.v connects; they are never
//           synthesised (Vivado uses its own primitives).
// =============================================================================
`default_nettype none
/* verilator lint_off DECLFILENAME */
/* verilator lint_off UNUSEDPARAM */
/* verilator lint_off UNUSEDSIGNAL */
module BUFG (input wire I, output wire O);
    assign O = I;
endmodule

module MMCME2_BASE #(
    parameter real    CLKIN1_PERIOD    = 10.0,
    parameter integer DIVCLK_DIVIDE    = 1,
    parameter real    CLKFBOUT_MULT_F  = 10.0,
    parameter real    CLKOUT0_DIVIDE_F = 20.0
) (
    input  wire CLKIN1,
    input  wire CLKFBIN,
    input  wire RST,
    input  wire PWRDWN,
    output wire CLKOUT0,
    output wire CLKFBOUT,
    output wire LOCKED
);
    assign CLKOUT0  = CLKIN1;
    assign CLKFBOUT = CLKIN1;
    assign LOCKED   = ~(RST | PWRDWN);
endmodule
/* verilator lint_on UNUSEDSIGNAL */
/* verilator lint_on UNUSEDPARAM */
`default_nettype wire
