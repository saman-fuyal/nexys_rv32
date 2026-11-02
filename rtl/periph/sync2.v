// =============================================================================
// sync2.v - two-flop synchronizer for asynchronous inputs
// -----------------------------------------------------------------------------
// Purpose : Bring switch, button and UART RX levels into the clock domain.
// Behavior: Each bit passes through two flip-flops. The first may go
//           metastable; the second gives it a full clock period to settle.
//           ASYNC_REG tells Vivado to place the pair close together and not to
//           merge them into shift-register LUTs. RESET_VAL lets the UART line
//           start idle-high so reset does not look like a start bit.
// =============================================================================
`default_nettype none

module sync2 #(
    parameter integer   WIDTH     = 1,
    parameter [WIDTH-1:0] RESET_VAL = {WIDTH{1'b0}}
) (
    //== Ports
    input  wire             clk,
    input  wire             rst,
    input  wire [WIDTH-1:0] d,        // asynchronous input
    output wire [WIDTH-1:0] q         // synchronized output
);

    //== Localparams/Wires
    (* ASYNC_REG = "TRUE" *) reg [WIDTH-1:0] meta_q;
    (* ASYNC_REG = "TRUE" *) reg [WIDTH-1:0] sync_q;

    //== Combinational Logic
    assign q = sync_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            meta_q <= RESET_VAL;
            sync_q <= RESET_VAL;
        end else begin
            meta_q <= d;
            sync_q <= meta_q;
        end
    end

endmodule

`default_nettype wire
