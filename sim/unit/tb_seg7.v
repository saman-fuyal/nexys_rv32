// =============================================================================
// tb_seg7.v - unit test: 7-segment scan, font, digit enable and DP
// -----------------------------------------------------------------------------
// Purpose : Over two scan periods every digit is driven exactly when its
//           anode is low (one at a time), shows the hex font of its nibble,
//           blanks when disabled and lights DP when asked. Active-low pins.
// =============================================================================
`timescale 1ns / 1ps
module tb_seg7;
    reg         clk = 0, rst = 1, req = 0, we = 0;
    reg  [2:0]  idx = 0;
    reg  [31:0] wdata = 0;
    wire [31:0] rdata;
    wire [7:0]  an;
    wire [6:0]  seg;
    wire        dp;
    integer     errors = 0, checks = 0, d, k, lows;
    reg  [6:0]  font [0:15];
    reg  [7:0]  seen;
    reg         exp_dp;
    reg  [6:0]  exp_seg;
    seg7 #(.DIV(20)) dut (.clk(clk), .rst(rst), .req(req), .we(we), .idx(idx), .wdata(wdata),
                          .rdata(rdata), .an_n(an), .seg_n(seg), .dp_n(dp));
    always #5 clk = ~clk;
    task wr(input [2:0] i_, input [31:0] v);
        begin @(negedge clk); req = 1; we = 1; idx = i_; wdata = v; @(negedge clk); req = 0; we = 0; end
    endtask
    initial begin
        font[0]=7'h3F; font[1]=7'h06; font[2]=7'h5B; font[3]=7'h4F; font[4]=7'h66; font[5]=7'h6D;
        font[6]=7'h7D; font[7]=7'h07; font[8]=7'h7F; font[9]=7'h6F; font[10]=7'h77; font[11]=7'h7C;
        font[12]=7'h39; font[13]=7'h5E; font[14]=7'h79; font[15]=7'h71;
        repeat (3) @(posedge clk); rst = 0;
        wr(0, 32'h89abcdef); wr(1, 32'h000000f7); wr(2, 32'h00000021);
        seen = 0;
        for (k = 0; k < 2 * 8 * 20; k = k + 1) begin
            @(posedge clk); #1;
            lows = 0;
            for (d = 0; d < 8; d = d + 1) if (!an[d]) lows = lows + 1;
            checks = checks + 1;
            if (lows > 1) begin errors = errors + 1; $display("seg7 FAIL two anodes low %b", an); end
            for (d = 0; d < 8; d = d + 1) begin
                if (!an[d]) begin
                    seen[d] = 1;
                    checks = checks + 1;
                    exp_seg = font[(32'h89abcdef >> (4 * d)) & 15];
                    exp_dp  = (8'h21 >> d) & 1;
                    if (seg !== ~exp_seg || dp !== ~exp_dp) begin
                        errors = errors + 1;
                        if (errors < 10) $display("seg7 FAIL digit %0d seg=%b dp=%b", d, ~seg, ~dp);
                    end
                end
            end
        end
        checks = checks + 1;
        if (seen !== 8'hf7) begin errors = errors + 1; $display("seg7 FAIL digits seen %b expected f7", seen); end
        if (errors == 0) $display("UNIT seg7 PASS %0d checks", checks);
        else $display("UNIT seg7 FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
