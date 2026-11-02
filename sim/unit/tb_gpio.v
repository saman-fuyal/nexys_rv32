// =============================================================================
// tb_gpio.v - unit test: LEDs, switch synchronizer, button debounce, edges
// -----------------------------------------------------------------------------
// Purpose : LED write/read-back (16 bits), switches visible after the
//           synchronizer, a bouncing button press that must produce exactly
//           one debounced press and one sticky edge bit, and edge clearing.
// =============================================================================
`timescale 1ns / 1ps
module tb_gpio;
    reg         clk = 0, rst = 1, req = 0, we = 0;
    reg  [2:0]  idx = 0;
    reg  [15:0] wdata = 0, sw = 0;
    reg  [4:0]  btn = 0;
    reg  [31:0] r;
    wire [31:0] rdata;
    wire [15:0] led;
    integer     errors = 0, checks = 0, i, edges = 0;
    reg         prev = 0;
    gpio #(.DEBOUNCE(20)) dut (.clk(clk), .rst(rst), .req(req), .we(we), .idx(idx), .wdata(wdata),
                               .rdata(rdata), .sw_pin(sw), .btn_pin(btn), .led(led));
    always #5 clk = ~clk;
    always @(posedge clk) begin
        if (dut.btn_db[3] && !prev) edges = edges + 1;
        prev <= dut.btn_db[3];
    end
    task wr(input [2:0] i_, input [15:0] v);
        begin @(negedge clk); req = 1; we = 1; idx = i_; wdata = v; @(negedge clk); req = 0; we = 0; end
    endtask
    task rdr(input [2:0] i_);
        begin @(negedge clk); req = 1; we = 0; idx = i_; @(negedge clk); req = 0; #1 r = rdata; end
    endtask
    task chk(input [255:0] what, input [31:0] got, input [31:0] exp);
        begin checks = checks + 1;
              if (got !== exp) begin errors = errors + 1; $display("gpio FAIL %0s got %h exp %h", what, got, exp); end end
    endtask
    initial begin
        repeat (3) @(posedge clk); rst = 0;
        wr(0, 16'hbeef); chk("led pins", led, 16'hbeef); rdr(0); chk("led readback", r, 32'hbeef);
        sw = 16'h1234; repeat (3) @(posedge clk); rdr(1); chk("switches", r, 32'h1234);
        for (i = 0; i < 12; i = i + 1) begin btn[3] = ~btn[3]; repeat (3) @(posedge clk); end
        btn[3] = 1; repeat (60) @(posedge clk);
        rdr(2); chk("button pressed", r, 32'h08);
        for (i = 0; i < 8; i = i + 1) begin btn[3] = ~btn[3]; repeat (2) @(posedge clk); end
        btn[3] = 0; repeat (60) @(posedge clk);
        rdr(2); chk("button released", r, 32'h00);
        chk("exactly one debounced press", edges, 1);
        rdr(3); chk("edge sticky", r, 32'h08);
        wr(3, 16'h0008); rdr(3); chk("edge cleared", r, 32'h00);
        if (errors == 0) $display("UNIT gpio PASS %0d checks", checks);
        else $display("UNIT gpio FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
