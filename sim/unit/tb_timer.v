// =============================================================================
// tb_timer.v - unit test: machine timer
// -----------------------------------------------------------------------------
// Purpose : mtime ticks every DIV clocks, 64-bit carry, register writes,
//           mtimecmp reset value, MTIP assert/deassert one clock after the
//           compare changes.
// =============================================================================
`timescale 1ns / 1ps
module tb_timer;
    reg         clk = 0, rst = 1, req = 0, we = 0;
    reg  [2:0]  idx = 0;
    reg  [31:0] wdata = 0, r;
    wire [31:0] rdata;
    wire        mtip;
    integer     errors = 0, checks = 0;
    timer #(.DIV(10)) dut (.clk(clk), .rst(rst), .req(req), .we(we), .idx(idx), .wdata(wdata),
                           .rdata(rdata), .mtip(mtip));
    always #5 clk = ~clk;
    task wr(input [2:0] i_, input [31:0] d);
        begin @(negedge clk); req = 1; we = 1; idx = i_; wdata = d; @(negedge clk); req = 0; we = 0; end
    endtask
    task rdr(input [2:0] i_);
        begin @(negedge clk); req = 1; we = 0; idx = i_; @(negedge clk); req = 0; #1 r = rdata; end
    endtask
    task chk(input [255:0] what, input [31:0] got, input [31:0] exp);
        begin checks = checks + 1;
              if (got !== exp) begin errors = errors + 1; $display("timer FAIL %0s got %h exp %h", what, got, exp); end end
    endtask
    initial begin
        repeat (3) @(posedge clk); rst = 0;
        rdr(2); chk("mtimecmp lo reset", r, 32'hffffffff);
        rdr(3); chk("mtimecmp hi reset", r, 32'hffffffff);
        chk("no mtip at reset", mtip, 0);
        repeat (200) @(posedge clk);
        rdr(0); chk("mtime after ~205 clocks /10", (r >= 20 && r <= 21), 1);
        wr(0, 32'hfffffff0); wr(1, 32'h00000007);
        repeat (300) @(posedge clk);
        rdr(1); chk("carry into mtime hi", r, 32'h8);
        wr(3, 32'h0); wr(2, 32'h0);
        repeat (2) @(posedge clk);
        chk("mtip when mtime >= mtimecmp", mtip, 1);
        wr(3, 32'hffffffff);
        repeat (2) @(posedge clk);
        chk("mtip cleared", mtip, 0);
        if (errors == 0) $display("UNIT timer PASS %0d checks", checks);
        else $display("UNIT timer FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
