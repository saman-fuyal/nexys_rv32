// =============================================================================
// rv_regfile.v - 32 x 32-bit integer register file, 2 read ports, 1 write port
// -----------------------------------------------------------------------------
// Purpose : Architectural registers x0..x31.
// Behavior: Asynchronous reads, synchronous write. x0 reads as zero because
//           the read mux forces it, so the storage for x0 is never trusted and
//           writes to x0 are dropped. Asynchronous reads let Vivado map the
//           array to distributed RAM (RAM32M primitives, about 24 LUTs) rather
//           than flip-flops; block RAM would add a cycle of read latency.
//           There is no reset: the ISA leaves x1..x31 undefined at reset and
//           both cores' software initialises what it uses.
//           A same-cycle read of the register being written returns the OLD
//           value; the pipelined core bypasses that case itself.
// =============================================================================
`default_nettype none

module rv_regfile (
    //== Ports
    input  wire        clk,
    input  wire        we,
    input  wire [4:0]  waddr,
    input  wire [31:0] wdata,
    input  wire [4:0]  raddr1,
    input  wire [4:0]  raddr2,
    output wire [31:0] rdata1,
    output wire [31:0] rdata2
);

    //== Localparams/Wires
    reg [31:0] rf_mem [0:31];

    //== Combinational Logic
    assign rdata1 = (raddr1 == 5'd0) ? 32'd0 : rf_mem[raddr1];
    assign rdata2 = (raddr2 == 5'd0) ? 32'd0 : rf_mem[raddr2];

    //== Sequential Logic
    always @(posedge clk) begin
        if (we && (waddr != 5'd0)) begin
            rf_mem[waddr] <= wdata;
        end
    end

endmodule

`default_nettype wire
