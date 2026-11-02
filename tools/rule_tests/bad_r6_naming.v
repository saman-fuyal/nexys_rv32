// =============================================================================
// bad_r6_naming.v - rule-checker self-test: a file that follows every rule
// -----------------------------------------------------------------------------
// Purpose : Reference for tools/check_rules.py --selftest (must FAIL).
// Behavior: 8-bit counter with enable, synchronous reset and a decoded flag.
// =============================================================================
`default_nettype none

module bad_r6_naming (
    //== Ports
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    input  wire [1:0] sel,
    output wire [7:0] count,
    output reg        flag
);

    //== Localparams/Wires
    reg [7:0] cnt_r, cnt_d;

    //== Combinational Logic
    always @(*) begin
        cnt_d = cnt_r;
        if (en) begin
            cnt_d = cnt_r + 8'd1;
        end
    end

    always @(*) begin
        flag = 1'b0;
        case (sel)
            2'd0:    flag = cnt_r[0];
            2'd1:    flag = cnt_r[1];
            default: flag = 1'b0;
        endcase
    end

    assign count = cnt_r;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            cnt_r <= 8'd0;
        end else begin
            cnt_r <= cnt_d;
        end
    end

endmodule

`default_nettype wire
