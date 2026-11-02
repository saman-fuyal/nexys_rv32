// =============================================================================
// tb_decode.v - unit test: rv_decode legality against the golden ISS
// -----------------------------------------------------------------------------
// Purpose : For structured and random instruction words, the decoder's
//           'illegal' output must equal what the ISS raises (CSR address
//           checks excluded: rv_csr owns those). Also checks that an illegal
//           instruction asserts none of the side-effect controls.
//           Vector line: illegal(4) insn(32).
// =============================================================================
`timescale 1ns / 1ps
module tb_decode;
    reg  [35:0]  vec [0:19999];
    reg  [31:0]  insn;
    wire         ill, u1, u2, rdwe, isb, isj, isjr, isl, iss, isc, cwr, ec, eb, mr, fi;
    wire [3:0]   aop;
    wire [1:0]   asel, wbs, sz, cop;
    wire         bsel, uns;
    wire [2:0]   it;
    integer      i, n, errors, side;
    reg [8*1024-1:0] file;
    rv_decode #(.ZICSR(1), .ZIFENCEI(1)) dut (
        .insn(insn), .illegal(ill), .uses_rs1(u1), .uses_rs2(u2), .rd_we(rdwe), .alu_op(aop),
        .alu_a_sel(asel), .alu_b_sel(bsel), .imm_type(it), .wb_sel(wbs), .is_branch(isb),
        .is_jal(isj), .is_jalr(isjr), .is_load(isl), .is_store(iss), .mem_size(sz),
        .mem_unsigned(uns), .is_csr(isc), .csr_op(cop), .csr_wr_intent(cwr), .is_ecall(ec),
        .is_ebreak(eb), .is_mret(mr), .is_fencei(fi));
    initial begin
        for (i = 0; i < 20000; i = i + 1) vec[i] = 36'bx;
        if (!$value$plusargs("vec=%s", file)) file = "dec.hex";
        $readmemh(file, vec);
        errors = 0; n = 0; side = 0;
        for (i = 0; i < 20000 && vec[i][0] !== 1'bx; i = i + 1) begin
            insn = vec[i][31:0];
            #1;
            n = n + 1;
            if (ill !== vec[i][32]) begin
                errors = errors + 1;
                if (errors < 10) $display("decode mismatch insn=%h illegal=%0d expected=%0d", insn, ill, vec[i][32]);
            end
            if (ill && (rdwe | isb | isj | isjr | isl | iss | isc | cwr | ec | eb | mr | fi)) side = side + 1;
        end
        if (errors == 0 && side == 0 && n > 0) $display("UNIT decode PASS %0d vectors", n);
        else $display("UNIT decode FAIL %0d mismatches, %0d illegal-with-side-effect, %0d vectors", errors, side, n);
        $finish;
    end
endmodule
