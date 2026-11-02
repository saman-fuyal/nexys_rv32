// =============================================================================
// debounce.v - counter-based debouncer for one synchronized button
// -----------------------------------------------------------------------------
// Purpose : Remove contact bounce from a push button.
// Behavior: The output follows the input only after the input has held the
//           new level for CYCLES consecutive clocks; any change of the input
//           restarts the count. Input must already be synchronized (sync2).
// =============================================================================
`default_nettype none

module debounce #(
    parameter integer CYCLES = 1000000,   // 10 ms at 100 MHz
    parameter integer CW     = 20         // counter width, 2**CW > CYCLES
) (
    //== Ports
    input  wire clk,
    input  wire rst,
    input  wire d,          // synchronized, bouncy
    output wire q           // stable level
);

    //== Localparams/Wires
    reg          state_q, state_d;
    reg [CW-1:0] cnt_q, cnt_d;

    //== Combinational Logic
    always @(*) begin
        state_d = state_q;
        cnt_d   = {CW{1'b0}};
        if (d != state_q) begin
            if (cnt_q == CYCLES[CW-1:0] - 1'b1) begin
                state_d = d;
            end else begin
                cnt_d = cnt_q + 1'b1;
            end
        end
    end

    assign q = state_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            state_q <= 1'b0;
            cnt_q   <= {CW{1'b0}};
        end else begin
            state_q <= state_d;
            cnt_q   <= cnt_d;
        end
    end

endmodule

`default_nettype wire
