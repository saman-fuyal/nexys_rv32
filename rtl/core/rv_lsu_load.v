// =============================================================================
// rv_lsu_load.v - load data alignment and extension
// -----------------------------------------------------------------------------
// Purpose : Pick the addressed byte or halfword out of the 32-bit bus word and
//           sign- or zero-extend it (LB, LH, LW, LBU, LHU).
// Behavior: Combinational. Alignment was already checked when the request was
//           made, so a halfword is taken from lane 0 or lane 2 only.
// =============================================================================
`default_nettype none

module rv_lsu_load (
    //== Ports
    input  wire [31:0] raw,         // bus read data (whole word)
    input  wire [1:0]  addr_lo,
    input  wire [1:0]  size,
    input  wire        is_unsigned,
    output reg  [31:0] data
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    wire [7:0]  byte_sel = addr_lo[1] ? (addr_lo[0] ? raw[31:24] : raw[23:16])
                                      : (addr_lo[0] ? raw[15:8]  : raw[7:0]);
    wire [15:0] half_sel = addr_lo[1] ? raw[31:16] : raw[15:0];

    //== Combinational Logic
    always @(*) begin
        data = raw;
        case (size)
            SZ_B:    data = {{24{~is_unsigned & byte_sel[7]}}, byte_sel};
            SZ_H:    data = {{16{~is_unsigned & half_sel[15]}}, half_sel};
            default: data = raw;
        endcase
    end

    //== Sequential Logic
    // (none: purely combinational)

endmodule

`default_nettype wire
