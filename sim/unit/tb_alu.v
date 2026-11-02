// =============================================================================
// tb_alu.v - unit test: rv_alu against ISS-generated vectors
// -----------------------------------------------------------------------------
// Purpose : Every ALU operation and branch condition on random and edge
//           operands. Vector line: op(4) brf3(4) taken(4) a(32) b(32) y(32).
// Output  : "UNIT alu PASS <n> vectors" or the first mismatches.
// =============================================================================
`timescale 1ns / 1ps
module tb_alu;
    reg  [107:0] vec [0:9999];
    reg  [31:0]  a, b;
    reg  [3:0]   op;
    reg  [2:0]   bf3;
    wire [31:0]  y;
    wire         taken;
    integer      i, n, errors;
    reg [8*1024-1:0] file;
    rv_alu dut (.a(a), .b(b), .op(op), .br_funct3(bf3), .y(y), .br_taken(taken));
    initial begin
        for (i = 0; i < 10000; i = i + 1) vec[i] = 108'bx;
        if (!$value$plusargs("vec=%s", file)) file = "alu.hex";
        $readmemh(file, vec);
        errors = 0; n = 0;
        for (i = 0; i < 10000 && vec[i][0] !== 1'bx; i = i + 1) begin
            op = vec[i][107:104]; bf3 = vec[i][102:100];
            a = vec[i][95:64]; b = vec[i][63:32];
            #1;
            n = n + 1;
            if (y !== vec[i][31:0] || taken !== vec[i][96]) begin
                errors = errors + 1;
                if (errors < 10) $display("alu mismatch op=%h a=%h b=%h y=%h exp=%h br=%0d/%0d",
                                          op, a, b, y, vec[i][31:0], taken, vec[i][96]);
            end
        end
        if (errors == 0 && n > 0) $display("UNIT alu PASS %0d vectors", n);
        else $display("UNIT alu FAIL %0d of %0d vectors", errors, n);
        $finish;
    end
endmodule
