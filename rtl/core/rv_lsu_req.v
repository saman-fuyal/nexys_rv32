// =============================================================================
// rv_lsu_req.v - load/store request formatting and alignment check
// -----------------------------------------------------------------------------
// Purpose : From a byte address and access size, produce the byte-lane write
//           strobes and lane-replicated write data the 32-bit bus expects, and
//           flag misaligned accesses.
// Behavior: Combinational. A halfword must be 2-byte aligned and a word 4-byte
//           aligned; anything else sets 'misaligned' and the core raises a
//           load/store address-misaligned exception (the ISA allows trapping
//           instead of handling misaligned accesses in hardware).
//           Store data is replicated across lanes (byte x4, half x2) so each
//           memory lane can take its byte without a shifter.
// =============================================================================
`default_nettype none

module rv_lsu_req (
    //== Ports
    input  wire [1:0]  addr_lo,     // address bits 1:0
    input  wire [1:0]  size,        // SZ_B / SZ_H / SZ_W
    input  wire [31:0] store_data,  // rs2
    output reg         misaligned,
    output reg  [3:0]  wstrb,
    output reg  [31:0] wdata
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    //== Combinational Logic
    always @(*) begin
        misaligned = 1'b0;
        wstrb      = 4'b0000;
        wdata      = store_data;
        case (size)
            SZ_B: begin
                wstrb = 4'b0001 << addr_lo;
                wdata = {4{store_data[7:0]}};
            end
            SZ_H: begin
                misaligned = addr_lo[0];
                wstrb      = addr_lo[1] ? 4'b1100 : 4'b0011;
                wdata      = {2{store_data[15:0]}};
            end
            SZ_W: begin
                misaligned = (addr_lo != 2'b00);
                wstrb      = 4'b1111;
                wdata      = store_data;
            end
            default: begin
                // size 3 cannot be decoded (illegal); keep the request inert
                misaligned = 1'b1;
                wstrb      = 4'b0000;
            end
        endcase
    end

    //== Sequential Logic
    // (none: purely combinational)

endmodule

`default_nettype wire
