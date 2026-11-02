// =============================================================================
// tb_imm.v - unit test: rv_imm against immediates sliced from the ISA text
// -----------------------------------------------------------------------------
// Purpose : All six immediate formats on random instruction words.
//           Vector line: type(4) insn(32) imm(32).
// =============================================================================
`timescale 1ns / 1ps
module tb_imm;
    reg  [67:0]  vec [0:9999];
    reg  [31:0]  insn;
    reg  [2:0]   t;
    wire [31:0]  imm;
    integer      i, n, errors;
    reg [8*1024-1:0] file;
    rv_imm dut (.insn(insn[31:7]), .imm_type(t), .imm(imm));
    initial begin
        for (i = 0; i < 10000; i = i + 1) vec[i] = 68'bx;
        if (!$value$plusargs("vec=%s", file)) file = "imm.hex";
        $readmemh(file, vec);
        errors = 0; n = 0;
        for (i = 0; i < 10000 && vec[i][0] !== 1'bx; i = i + 1) begin
            t = vec[i][66:64]; insn = vec[i][63:32];
            #1;
            n = n + 1;
            if (imm !== vec[i][31:0]) begin
                errors = errors + 1;
                if (errors < 10) $display("imm mismatch type=%0d insn=%h got=%h exp=%h", t, insn, imm, vec[i][31:0]);
            end
        end
        if (errors == 0 && n > 0) $display("UNIT imm PASS %0d vectors", n);
        else $display("UNIT imm FAIL %0d of %0d vectors", errors, n);
        $finish;
    end
endmodule
