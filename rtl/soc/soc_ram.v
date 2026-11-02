// =============================================================================
// soc_ram.v - main RAM, true dual-port block RAM with byte writes
// -----------------------------------------------------------------------------
// Purpose : Program and data memory shared by instruction fetch (port A, read
//           only) and loads/stores (port B, read/write).
// Behavior: Both ports read synchronously: data for a request in cycle t is on
//           rdata in cycle t+1. When a port is not enabled its output register
//           holds, which the pipelined core relies on while it stalls. Port B
//           is read-first (a store returns the old word, which the core
//           ignores). The coding follows the Vivado UG901 byte-write true
//           dual-port template so it maps to RAMB36E1 primitives; 64 KB uses
//           16 of the 75 block RAMs of the XC7A50T.
//           There is no initialisation: the bootloader fills RAM over UART,
//           and simulation testbenches preload it with $readmemh on the
//           hierarchical name u_ram.ram_mem (testbench code, not RTL).
// =============================================================================
`default_nettype none

module soc_ram #(
    parameter integer AW = 14              // word address bits (2**AW words)
) (
    //== Ports
    input  wire          clk,
    // port A: instruction fetch
    input  wire          a_en,
    input  wire [AW-1:0] a_addr,
    output wire [31:0]   a_rdata,
    // port B: data
    input  wire          b_en,
    input  wire [3:0]    b_we,
    input  wire [AW-1:0] b_addr,
    input  wire [31:0]   b_wdata,
    output wire [31:0]   b_rdata
);

    //== Localparams/Wires
    reg [31:0] ram_mem [0:(1 << AW) - 1];
    reg [31:0] a_rdata_q;
    reg [31:0] b_rdata_q;

    //== Combinational Logic
    assign a_rdata = a_rdata_q;
    assign b_rdata = b_rdata_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (a_en) begin
            a_rdata_q <= ram_mem[a_addr];
        end
    end

    always @(posedge clk) begin
        if (b_en) begin
            b_rdata_q <= ram_mem[b_addr];
            if (b_we[0]) begin
                ram_mem[b_addr][7:0] <= b_wdata[7:0];
            end
            if (b_we[1]) begin
                ram_mem[b_addr][15:8] <= b_wdata[15:8];
            end
            if (b_we[2]) begin
                ram_mem[b_addr][23:16] <= b_wdata[23:16];
            end
            if (b_we[3]) begin
                ram_mem[b_addr][31:24] <= b_wdata[31:24];
            end
        end
    end

endmodule

`default_nettype wire
