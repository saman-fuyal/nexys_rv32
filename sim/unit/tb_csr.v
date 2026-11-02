// =============================================================================
// tb_csr.v - unit test: rv_csr directed sequence
// -----------------------------------------------------------------------------
// Purpose : CSR read/write/set/clear, WARL masks, read-only and unknown
//           addresses, trap entry, MRET, counters and the minstret write
//           rule, interrupt pending logic.
// =============================================================================
`timescale 1ns / 1ps
module tb_csr;
    reg         clk = 0, rst = 1;
    reg  [11:0] addr;
    reg  [1:0]  op;
    reg  [31:0] src;
    reg         wr, en, trap, mret, ret, mtip;
    reg  [31:0] cause, tval;
    reg  [31:2] epc;
    wire [31:0] rdata, mtvec, mepc;
    wire        ill, pend;
    integer     errors = 0, checks = 0;
    reg  [31:0] t0;
    rv_csr #(.TIMER_IRQ(1), .MISA(32'h40000100), .MIMPID(32'h00010000)) dut (
        .clk(clk), .rst(rst), .csr_addr(addr), .csr_op(op), .csr_src(src), .csr_wr_intent(wr),
        .csr_en(en), .csr_rdata(rdata), .csr_illegal(ill), .trap_en(trap), .trap_cause(cause),
        .trap_epc(epc), .trap_tval(tval), .mret_en(mret), .instret_en(ret), .irq_mtip(mtip),
        .mtvec(mtvec), .mepc(mepc), .irq_pending(pend));
    always #5 clk = ~clk;

    task chk(input [255:0] what, input [31:0] got, input [31:0] exp);
        begin
            checks = checks + 1;
            if (got !== exp) begin
                errors = errors + 1;
                $display("csr FAIL %0s: got %h expected %h", what, got, exp);
            end
        end
    endtask
    // one CSR instruction: returns the old value in t0
    task csr(input [11:0] a, input [1:0] o, input [31:0] s, input w);
        begin
            @(negedge clk);
            addr = a; op = o; src = s; wr = w; en = 1; ret = 1;
            #1 t0 = rdata;
            @(negedge clk);
            en = 0; ret = 0; wr = 0;
        end
    endtask
    task rd(input [11:0] a);
        begin
            @(negedge clk);
            addr = a; wr = 0; en = 0;
            #1 t0 = rdata;
        end
    endtask

    initial begin
        en = 0; wr = 0; trap = 0; mret = 0; ret = 0; mtip = 0; op = 1; src = 0; addr = 0;
        cause = 0; tval = 0; epc = 0;
        repeat (3) @(posedge clk);
        rst = 0;
        csr(12'h340, 2'd1, 32'hdeadbeef, 1); csr(12'h340, 2'd2, 32'h0000000f, 1);
        chk("mscratch rw old", t0, 32'hdeadbeef);
        rd(12'h340); chk("mscratch rs", t0, 32'hdeadbeef | 32'hf);
        csr(12'h340, 2'd3, 32'hffff0000, 1); rd(12'h340); chk("mscratch rc", t0, 32'h0000beef);
        csr(12'h300, 2'd1, 32'hffffffff, 1); rd(12'h300); chk("mstatus mask", t0, 32'h00001888);
        csr(12'h304, 2'd1, 32'hffffffff, 1); rd(12'h304); chk("mie mask", t0, 32'h00000080);
        csr(12'h305, 2'd1, 32'h80000103, 1); chk("mtvec port", mtvec, 32'h80000100);
        csr(12'h341, 2'd1, 32'h80000207, 1); chk("mepc port", mepc, 32'h80000204);
        rd(12'h301); chk("misa", t0, 32'h40000100);
        rd(12'hf13); chk("mimpid", t0, 32'h00010000);
        // legality
        @(negedge clk); addr = 12'h7c0; wr = 0; #1 chk("unknown csr illegal", ill, 1);
        addr = 12'hf14; wr = 0; #1 chk("mhartid read legal", ill, 0);
        addr = 12'hf14; wr = 1; #1 chk("mhartid write illegal", ill, 1);
        addr = 12'h301; wr = 1; #1 chk("misa write legal (WARL)", ill, 0);
        wr = 0;
        // interrupt pending: needs MIE, MTIE and MTIP
        mtip = 1; #1 chk("pending with MIE,MTIE,MTIP", pend, 1);
        // trap entry
        @(negedge clk); trap = 1; cause = 32'h80000007; epc = 30'h20000040; tval = 0;
        @(negedge clk); trap = 0;
        rd(12'h342); chk("mcause", t0, 32'h80000007);
        rd(12'h341); chk("mepc after trap", t0, 32'h80000100);
        rd(12'h300); chk("mstatus after trap", t0, 32'h00001880);
        chk("no pending inside handler", pend, 0);
        @(negedge clk); mret = 1; @(negedge clk); mret = 0;
        rd(12'h300); chk("mstatus after mret", t0, 32'h00001888);
        mtip = 0;
        // counters
        rd(12'hb00); t0 = t0; begin : cyc
            reg [31:0] c0; c0 = t0; repeat (10) @(negedge clk); rd(12'hb00);
            chk("mcycle advanced 11", t0 - c0, 32'd11);
        end
        csr(12'hb02, 2'd1, 32'h00000005, 1); rd(12'hb02); chk("minstret write wins", t0, 32'd5);
        csr(12'h340, 2'd2, 32'd0, 0); rd(12'hb02); chk("minstret counts", t0, 32'd6);
        csr(12'hb82, 2'd1, 32'h00000001, 1); rd(12'hb82); chk("minstreth write", t0, 32'd1);
        rd(12'hb02); chk("minstret not incremented by minstreth write", t0, 32'd6);
        if (errors == 0) $display("UNIT csr PASS %0d checks", checks);
        else $display("UNIT csr FAIL %0d of %0d checks", errors, checks);
        $finish;
    end
endmodule
