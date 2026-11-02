// =============================================================================
// tb_regfile.v - unit test: rv_regfile against a behavioural model
// -----------------------------------------------------------------------------
// Purpose : 20000 random cycles of write + two reads; x0 must read 0 and
//           ignore writes; a read of the register being written returns the
//           old value (the pipeline bypasses that case itself).
// =============================================================================
`timescale 1ns / 1ps
module tb_regfile;
    reg         clk = 0;
    reg         we;
    reg  [4:0]  wa, ra1, ra2;
    reg  [31:0] wd;
    wire [31:0] rd1, rd2;
    reg  [31:0] model [0:31];
    integer     i, errors, seed;
    rv_regfile dut (.clk(clk), .we(we), .waddr(wa), .wdata(wd), .raddr1(ra1), .raddr2(ra2),
                    .rdata1(rd1), .rdata2(rd2));
    always #5 clk = ~clk;
    initial begin
        seed = 7; errors = 0;
        for (i = 0; i < 32; i = i + 1) begin model[i] = 0; dut.rf_mem[i] = 0; end
        for (i = 0; i < 20000; i = i + 1) begin
            @(negedge clk);
            we = $random(seed); wa = $random(seed); wd = $random(seed);
            ra1 = $random(seed); ra2 = (i % 3 == 0) ? wa : $random(seed);
            #1;
            if (rd1 !== (ra1 == 0 ? 32'd0 : model[ra1]) || rd2 !== (ra2 == 0 ? 32'd0 : model[ra2])) begin
                errors = errors + 1;
                if (errors < 10) $display("regfile mismatch r%0d=%h r%0d=%h", ra1, rd1, ra2, rd2);
            end
            @(posedge clk);
            if (we && wa != 0) model[wa] = wd;
        end
        if (errors == 0) $display("UNIT regfile PASS 20000 cycles");
        else $display("UNIT regfile FAIL %0d errors", errors);
        $finish;
    end
endmodule
