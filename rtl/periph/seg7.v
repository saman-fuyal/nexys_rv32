// =============================================================================
// seg7.v - 8-digit multiplexed seven-segment display driver
// -----------------------------------------------------------------------------
// Purpose : Show a 32-bit value as 8 hex digits on the Nexys A7 display.
// Registers (word index):
//   0 VALUE    RW  digit n shows VALUE[4n+3:4n]; digit 7 is the leftmost
//   1 DIGIT_EN RW  bit n enables digit n (reset 8'hFF)
//   2 DP       RW  bit n lights the decimal point of digit n
// Behavior: One digit is driven at a time for DIV clocks (1 ms at the default
//           1 kHz), so a full refresh takes 8 ms, inside the 1-16 ms the
//           reference manual asks for. Anodes AN[7:0] and cathodes CA..CG, DP
//           are active low (common-anode displays driven through transistors).
//           All outputs are registered so the pins do not glitch.
// =============================================================================
`default_nettype none

module seg7 #(
    parameter integer DIV = 100000,
    parameter integer CW  = 20
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        req,
    input  wire        we,
    input  wire [2:0]  idx,
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire [7:0]  an_n,        // AN[7:0], active low
    output wire [6:0]  seg_n,       // {CG,CF,CE,CD,CC,CB,CA}, active low
    output wire        dp_n         // active low
);

    //== Localparams/Wires
    reg  [31:0]   value_q, value_d;
    reg  [7:0]    en_q,    en_d;
    reg  [7:0]    dp_q,    dp_d;
    reg  [31:0]   rdata_q, rdata_d;
    reg  [CW-1:0] cnt_q,   cnt_d;
    reg  [2:0]    digit_q, digit_d;
    reg  [7:0]    an_q,    an_d;
    reg  [6:0]    seg_q,   seg_d;
    reg           dpo_q,   dpo_d;
    reg  [3:0]    nibble;
    reg  [6:0]    segs;             // active-high {g,f,e,d,c,b,a}
    wire          wr = req & we;
    wire          rd = req & ~we;

    //== Combinational Logic
    // Register interface
    always @(*) begin
        value_d = value_q;
        en_d    = en_q;
        dp_d    = dp_q;
        rdata_d = 32'd0;
        if (wr) begin
            case (idx)
                3'd0:    value_d = wdata;
                3'd1:    en_d    = wdata[7:0];
                3'd2:    dp_d    = wdata[7:0];
                default: value_d = value_q;
            endcase
        end
        if (rd) begin
            case (idx)
                3'd0:    rdata_d = value_q;
                3'd1:    rdata_d = {24'd0, en_q};
                3'd2:    rdata_d = {24'd0, dp_q};
                default: rdata_d = 32'd0;
            endcase
        end
    end

    // Scan counter and digit select
    always @(*) begin
        cnt_d   = cnt_q + 1'b1;
        digit_d = digit_q;
        if (cnt_q == DIV[CW-1:0] - 1'b1) begin
            cnt_d   = {CW{1'b0}};
            digit_d = digit_q + 3'd1;
        end
    end

    // Hex font
    always @(*) begin
        nibble = value_q[3:0];
        segs   = 7'b0000000;
        case (digit_q)
            3'd0:    nibble = value_q[3:0];
            3'd1:    nibble = value_q[7:4];
            3'd2:    nibble = value_q[11:8];
            3'd3:    nibble = value_q[15:12];
            3'd4:    nibble = value_q[19:16];
            3'd5:    nibble = value_q[23:20];
            3'd6:    nibble = value_q[27:24];
            3'd7:    nibble = value_q[31:28];
            default: nibble = 4'h0;
        endcase
        case (nibble)
            4'h0:    segs = 7'b0111111;
            4'h1:    segs = 7'b0000110;
            4'h2:    segs = 7'b1011011;
            4'h3:    segs = 7'b1001111;
            4'h4:    segs = 7'b1100110;
            4'h5:    segs = 7'b1101101;
            4'h6:    segs = 7'b1111101;
            4'h7:    segs = 7'b0000111;
            4'h8:    segs = 7'b1111111;
            4'h9:    segs = 7'b1101111;
            4'hA:    segs = 7'b1110111;
            4'hB:    segs = 7'b1111100;
            4'hC:    segs = 7'b0111001;
            4'hD:    segs = 7'b1011110;
            4'hE:    segs = 7'b1111001;
            4'hF:    segs = 7'b1110001;
            default: segs = 7'b0000000;
        endcase
        an_d  = ~((8'd1 << digit_q) & en_q);
        seg_d = ~segs;
        dpo_d = ~dp_q[digit_q];
    end

    assign rdata = rdata_q;
    assign an_n  = an_q;
    assign seg_n = seg_q;
    assign dp_n  = dpo_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            value_q <= 32'd0;
            en_q    <= 8'hFF;
            dp_q    <= 8'h00;
            rdata_q <= 32'd0;
            cnt_q   <= {CW{1'b0}};
            digit_q <= 3'd0;
            an_q    <= 8'hFF;
            seg_q   <= 7'h7F;
            dpo_q   <= 1'b1;
        end else begin
            value_q <= value_d;
            en_q    <= en_d;
            dp_q    <= dp_d;
            rdata_q <= rdata_d;
            cnt_q   <= cnt_d;
            digit_q <= digit_d;
            an_q    <= an_d;
            seg_q   <= seg_d;
            dpo_q   <= dpo_d;
        end
    end

endmodule

`default_nettype wire
