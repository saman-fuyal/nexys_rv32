// =============================================================================
// tb_lsu.v - unit test: rv_lsu_req and rv_lsu_load
// -----------------------------------------------------------------------------
// Purpose : Byte-lane strobes, lane-replicated store data, misalignment flag,
//           and load extraction/extension for every size and offset.
//           req  line: size(4) lo(4) data(32) mis(4) strb(4) wdata(32)
//           load line: size(4) lo(4) uns(4) raw(32) data(32)
// =============================================================================
`timescale 1ns / 1ps
module tb_lsu;
    reg  [79:0]  vreq  [0:9999];
    reg  [75:0]  vload [0:9999];
    reg  [1:0]   size, lo;
    reg  [31:0]  sd, raw;
    reg          uns;
    wire         mis;
    wire [3:0]   strb;
    wire [31:0]  wd, ld;
    integer      i, n, errors;
    reg [8*1024-1:0] f1, f2;
    rv_lsu_req  u_req (.addr_lo(lo), .size(size), .store_data(sd), .misaligned(mis), .wstrb(strb), .wdata(wd));
    rv_lsu_load u_ld  (.raw(raw), .addr_lo(lo), .size(size), .is_unsigned(uns), .data(ld));
    initial begin
        for (i = 0; i < 10000; i = i + 1) begin vreq[i] = 80'bx; vload[i] = 76'bx; end
        if (!$value$plusargs("vreq=%s", f1)) f1 = "lsu_req.hex";
        if (!$value$plusargs("vload=%s", f2)) f2 = "lsu_load.hex";
        $readmemh(f1, vreq);
        $readmemh(f2, vload);
        errors = 0; n = 0;
        for (i = 0; i < 10000 && vreq[i][0] !== 1'bx; i = i + 1) begin
            size = vreq[i][77:76]; lo = vreq[i][73:72]; sd = vreq[i][71:40];
            #1;
            n = n + 1;
            if (mis !== vreq[i][36] || (!mis && (strb !== vreq[i][35:32] || wd !== vreq[i][31:0]))) begin
                errors = errors + 1;
                if (errors < 10) $display("lsu_req mismatch size=%0d lo=%0d mis=%0d strb=%h wd=%h exp %h", size, lo, mis, strb, wd, vreq[i][36:0]);
            end
        end
        for (i = 0; i < 10000 && vload[i][0] !== 1'bx; i = i + 1) begin
            size = vload[i][73:72]; lo = vload[i][69:68]; uns = vload[i][64]; raw = vload[i][63:32];
            #1;
            n = n + 1;
            if (ld !== vload[i][31:0]) begin
                errors = errors + 1;
                if (errors < 10) $display("lsu_load mismatch size=%0d lo=%0d uns=%0d raw=%h got=%h exp=%h", size, lo, uns, raw, ld, vload[i][31:0]);
            end
        end
        if (errors == 0 && n > 0) $display("UNIT lsu PASS %0d vectors", n);
        else $display("UNIT lsu FAIL %0d of %0d vectors", errors, n);
        $finish;
    end
endmodule
