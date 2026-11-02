// =============================================================================
// tb_bus.v - unit test: soc_bus address decode and faults vs the ISS map
// -----------------------------------------------------------------------------
// Purpose : For boundary and random addresses, every size and direction:
//           dbus_fault must match the ISS memory map; a faulting request
//           enables no slave; fetch faults for anything outside ROM/RAM.
//           Vector line: size(4) we(4) dfault(4) ifault(4) addr(32).
// =============================================================================
`timescale 1ns / 1ps
module tb_bus;
    reg  [47:0]  vec [0:39999];
    reg          clk = 0, rst = 1;
    reg          ireq, dreq, we;
    reg  [31:0]  iaddr, daddr;
    reg  [1:0]   size;
    wire         ifault, dfault, rae, rae2, rbe, rbe2;
    wire [31:0]  ird, drd;
    wire [4:0]   preq;
    wire [2:0]   pidx;
    integer      i, n, errors;
    reg [8*1024-1:0] file;
    soc_bus dut (.clk(clk), .rst(rst), .ibus_req(ireq), .ibus_addr(iaddr), .ibus_fault(ifault),
                 .ibus_rdata(ird), .dbus_req(dreq), .dbus_we(we), .dbus_addr(daddr), .dbus_size(size),
                 .dbus_fault(dfault), .dbus_rdata(drd), .rom_a_en(rae), .ram_a_en(rae2),
                 .rom_b_en(rbe), .ram_b_en(rbe2), .rom_a_rdata(32'd0), .ram_a_rdata(32'd0),
                 .rom_b_rdata(32'd0), .ram_b_rdata(32'd0), .per_req(preq), .per_idx(pidx),
                 .per_rdata(32'd0));
    initial begin
        for (i = 0; i < 40000; i = i + 1) vec[i] = 48'bx;
        if (!$value$plusargs("vec=%s", file)) file = "bus.hex";
        $readmemh(file, vec);
        errors = 0; n = 0; ireq = 1; dreq = 1; rst = 0;
        for (i = 0; i < 40000 && vec[i][0] !== 1'bx; i = i + 1) begin
            size = vec[i][45:44]; we = vec[i][40]; daddr = vec[i][31:0]; iaddr = vec[i][31:0];
            #1;
            n = n + 1;
            if (dfault !== vec[i][36] || (dfault && (rbe | rbe2 | (|preq))) ||
                (size == 2'd2 && !we && ifault !== vec[i][32])) begin
                errors = errors + 1;
                if (errors < 10) $display("bus mismatch addr=%h size=%0d we=%0d dfault=%0d exp %0d ifault=%0d exp %0d",
                                          daddr, size, we, dfault, vec[i][36], ifault, vec[i][32]);
            end
        end
        if (errors == 0 && n > 0) $display("UNIT bus PASS %0d vectors", n);
        else $display("UNIT bus FAIL %0d of %0d vectors", errors, n);
        $finish;
    end
endmodule
