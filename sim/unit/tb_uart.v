// =============================================================================
// tb_uart.v - unit test: uart (TX, RX, registers) with a loopback wire
// -----------------------------------------------------------------------------
// Purpose : 64 random bytes sent through TXDATA come back through RXDATA via
//           a TX->RX wire; STATUS bits (TX_BUSY, RX_VALID), overrun on a
//           missed byte and its write-1-to-clear, a framing error from a
//           bad stop bit, and a glitch shorter than half a bit ignored.
//           A small divisor (16 clocks per bit) keeps the test short.
// =============================================================================
`timescale 1ns / 1ps
module tb_uart;
    reg         clk = 0, rst = 1;
    reg         req = 0, we = 0;
    reg  [2:0]  idx = 0;
    reg  [7:0]  wdata = 0;
    wire [31:0] rdata;
    wire        tx;
    reg         force_rx = 0, rx_val = 1;
    wire        rx = force_rx ? rx_val : tx;
    integer     i, errors = 0, checks = 0, seed = 3;
    reg  [7:0]  b;
    reg  [31:0] r;
    uart #(.DIV(16)) dut (.clk(clk), .rst(rst), .req(req), .we(we), .idx(idx), .wdata(wdata),
                          .rdata(rdata), .rx_pin(rx), .tx_pin(tx));
    always #5 clk = ~clk;
    task wr(input [2:0] i_, input [7:0] d);
        begin @(negedge clk); req = 1; we = 1; idx = i_; wdata = d; @(negedge clk); req = 0; we = 0; end
    endtask
    task rdr(input [2:0] i_);
        begin @(negedge clk); req = 1; we = 0; idx = i_; @(negedge clk); req = 0; #1 r = rdata; end
    endtask
    task chk(input [255:0] what, input [31:0] got, input [31:0] exp);
        begin checks = checks + 1;
              if (got !== exp) begin errors = errors + 1; $display("uart FAIL %0s got %h exp %h", what, got, exp); end end
    endtask
    task sendbit(input v); begin rx_val = v; repeat (16) @(posedge clk); end endtask
    initial begin
        repeat (3) @(posedge clk); rst = 0;
        for (i = 0; i < 64; i = i + 1) begin
            b = $random(seed);
            wr(0, b);
            rdr(2); chk("tx busy after write", r[0], 1);
            r = 1;
            while (r[1] == 0) rdr(2);                 // wait RX_VALID
            rdr(1); chk("loopback byte", r[7:0], b);
            rdr(2); chk("rx valid cleared by read", r[1], 0);
        end
        // overrun: two bytes without reading
        wr(0, 8'h11); r = 0; while (r[0] == 0) rdr(2); while (r[0] == 1) rdr(2);
        wr(0, 8'h22); r = 0; while (r[0] == 0) rdr(2); while (r[0] == 1) rdr(2);
        repeat (40) @(posedge clk);
        rdr(2); chk("overrun set", r[2], 1);
        rdr(1); chk("newest byte kept", r[7:0], 8'h22);
        wr(2, 8'h04); rdr(2); chk("overrun cleared", r[2], 0);
        // framing error and glitch, driven directly on RX
        force_rx = 1; rx_val = 1; repeat (40) @(posedge clk);
        sendbit(0); sendbit(1); sendbit(0); sendbit(1); sendbit(0); sendbit(1); sendbit(0); sendbit(1);
        sendbit(0); sendbit(0);                       // stop bit 0
        rx_val = 1; repeat (40) @(posedge clk);
        rdr(2); chk("frame error", r[3], 1);
        wr(2, 8'h08); rdr(2); chk("frame error cleared", r[3], 0);
        rdr(1);
        rx_val = 0; repeat (5) @(posedge clk); rx_val = 1; repeat (400) @(posedge clk);
        rdr(2); chk("glitch ignored", r[1], 0);
        if (errors == 0) $display("UNIT uart PASS %0d checks", checks);
        else $display("UNIT uart FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
