// =============================================================================
// rv_decode.v - RV32I + Zicsr + Zifencei instruction decoder
// -----------------------------------------------------------------------------
// Purpose : Turn one 32-bit instruction into control signals for either core.
// Behavior: Purely combinational. Every encoding that is not a supported
//           instruction sets 'illegal' (the core then raises mcause 2 with
//           mtval = instruction). Checks cover the full encoding, not only the
//           opcode: funct3/funct7 of every format, shift-amount bit 5, the
//           exact ECALL/EBREAK/MRET/WFI words, and insn[1:0] = 11 (no C).
//           CSR address legality is checked later by rv_csr, which knows the
//           implemented CSR set.
// =============================================================================
`default_nettype none

module rv_decode #(
    parameter ZICSR    = 1,
    parameter ZIFENCEI = 1
) (
    //== Ports
    input  wire [31:0] insn,
    output reg         illegal,
    output reg         uses_rs1,
    output reg         uses_rs2,
    output reg         rd_we,         // writes rd (before x0 masking)
    output reg  [3:0]  alu_op,
    output reg  [1:0]  alu_a_sel,
    output reg         alu_b_sel,
    output reg  [2:0]  imm_type,
    output reg  [1:0]  wb_sel,
    output reg         is_branch,
    output reg         is_jal,
    output reg         is_jalr,
    output reg         is_load,
    output reg         is_store,
    output reg  [1:0]  mem_size,
    output reg         mem_unsigned,
    output reg         is_csr,
    output reg  [1:0]  csr_op,
    output reg         csr_wr_intent, // CSRRW/I always; CSRRS/C only if rs1/uimm != 0
    output reg         is_ecall,
    output reg         is_ebreak,
    output reg         is_mret,
    output reg         is_fencei
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    wire [6:0] opcode = insn[6:0];
    wire [2:0] funct3 = insn[14:12];
    wire [6:0] funct7 = insn[31:25];
    wire [4:0] rs1    = insn[19:15];

    //== Combinational Logic
    always @(*) begin
        // Defaults describe a harmless no-op; each case only overrides fields.
        illegal       = 1'b0;
        uses_rs1      = 1'b0;
        uses_rs2      = 1'b0;
        rd_we         = 1'b0;
        alu_op        = ALU_ADD;
        alu_a_sel     = ASEL_RS1;
        alu_b_sel     = BSEL_IMM;
        imm_type      = IMM_I;
        wb_sel        = WB_ALU;
        is_branch     = 1'b0;
        is_jal        = 1'b0;
        is_jalr       = 1'b0;
        is_load       = 1'b0;
        is_store      = 1'b0;
        mem_size      = funct3[1:0];
        mem_unsigned  = funct3[2];
        is_csr        = 1'b0;
        csr_op        = funct3[1:0];
        csr_wr_intent = 1'b0;
        is_ecall      = 1'b0;
        is_ebreak     = 1'b0;
        is_mret       = 1'b0;
        is_fencei     = 1'b0;

        case (opcode)
            OPC_LUI: begin
                rd_we     = 1'b1;
                alu_a_sel = ASEL_ZERO;
                imm_type  = IMM_U;
            end
            OPC_AUIPC: begin
                rd_we     = 1'b1;
                alu_a_sel = ASEL_PC;
                imm_type  = IMM_U;
            end
            OPC_JAL: begin
                rd_we    = 1'b1;
                is_jal   = 1'b1;
                imm_type = IMM_J;
                wb_sel   = WB_PC4;
            end
            OPC_JALR: begin
                uses_rs1 = 1'b1;
                rd_we    = 1'b1;
                is_jalr  = 1'b1;
                wb_sel   = WB_PC4;
                illegal  = (funct3 != 3'b000);
            end
            OPC_BRANCH: begin
                uses_rs1  = 1'b1;
                uses_rs2  = 1'b1;
                is_branch = 1'b1;
                imm_type  = IMM_B;
                alu_b_sel = BSEL_RS2;     // the comparator works on rs1 - rs2
                // funct3 010 and 011 are reserved
                illegal   = (funct3[2:1] == 2'b01);
            end
            OPC_LOAD: begin
                uses_rs1 = 1'b1;
                rd_we    = 1'b1;
                is_load  = 1'b1;
                wb_sel   = WB_MEM;
                // valid: LB LH LW LBU LHU (000 001 010 100 101)
                illegal  = (funct3 == 3'b011) || (funct3[2:1] == 2'b11);
            end
            OPC_STORE: begin
                uses_rs1 = 1'b1;
                uses_rs2 = 1'b1;
                is_store = 1'b1;
                imm_type = IMM_S;
                // valid: SB SH SW (000 001 010)
                illegal  = funct3[2] || (funct3[1:0] == 2'b11);
            end
            OPC_OP_IMM: begin
                uses_rs1 = 1'b1;
                rd_we    = 1'b1;
                alu_op   = {1'b0, funct3};
                if (funct3 == 3'b001) begin
                    // SLLI: funct7 must be zero (bit 25 = shamt[5] is illegal on RV32)
                    illegal = (funct7 != 7'b0000000);
                end else if (funct3 == 3'b101) begin
                    // SRLI / SRAI
                    alu_op  = {insn[30], funct3};
                    illegal = (funct7 != 7'b0000000) && (funct7 != 7'b0100000);
                end
            end
            OPC_OP: begin
                uses_rs1  = 1'b1;
                uses_rs2  = 1'b1;
                rd_we     = 1'b1;
                alu_b_sel = BSEL_RS2;
                alu_op    = {insn[30], funct3};
                if (funct7 == 7'b0100000) begin
                    illegal = (funct3 != 3'b000) && (funct3 != 3'b101);   // SUB, SRA only
                end else begin
                    illegal = (funct7 != 7'b0000000);
                end
            end
            OPC_MISC_MEM: begin
                // FENCE ignores fm/pred/succ/rs1/rd (in-order, no caches).
                if (funct3 == 3'b001) begin
                    is_fencei = (ZIFENCEI != 0);
                    illegal   = (ZIFENCEI == 0);
                end else begin
                    illegal   = (funct3 != 3'b000);
                end
            end
            OPC_SYSTEM: begin
                if (funct3 == 3'b000) begin
                    case (insn)
                        32'h00000073: is_ecall  = 1'b1;
                        32'h00100073: is_ebreak = 1'b1;
                        32'h30200073: begin
                            is_mret = (ZICSR != 0);
                            illegal = (ZICSR == 0);
                        end
                        32'h10500073: illegal = (ZICSR == 0);   // WFI executes as a NOP
                        default:      illegal = 1'b1;
                    endcase
                end else if (funct3 == 3'b100) begin
                    illegal = 1'b1;
                end else begin
                    is_csr        = (ZICSR != 0);
                    illegal       = (ZICSR == 0);
                    rd_we         = 1'b1;
                    wb_sel        = WB_CSR;
                    uses_rs1      = ~funct3[2];
                    imm_type      = IMM_Z;
                    csr_wr_intent = (funct3[1:0] == CSR_RW) || (rs1 != 5'd0);
                end
            end
            default: illegal = 1'b1;
        endcase

        // Only 32-bit encodings exist without the C extension.
        if (insn[1:0] != 2'b11) begin
            illegal = 1'b1;
        end

        // An illegal instruction must have no side effect at all.
        if (illegal) begin
            rd_we         = 1'b0;
            is_branch     = 1'b0;
            is_jal        = 1'b0;
            is_jalr       = 1'b0;
            is_load       = 1'b0;
            is_store      = 1'b0;
            is_csr        = 1'b0;
            csr_wr_intent = 1'b0;
            is_ecall      = 1'b0;
            is_ebreak     = 1'b0;
            is_mret       = 1'b0;
            is_fencei     = 1'b0;
        end
    end

    //== Sequential Logic
    // (none: purely combinational)

endmodule

`default_nettype wire
