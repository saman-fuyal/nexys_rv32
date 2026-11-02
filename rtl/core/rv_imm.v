// =============================================================================
// rv_imm.v - immediate generator
// -----------------------------------------------------------------------------
// Purpose : Build the sign-extended 32-bit immediate for each RV32I format
//           (I, S, B, U, J) and the zero-extended CSR uimm (Z).
// Behavior: Combinational. Bit positions follow the Unprivileged ISA figure
//           "Types of immediate produced by RISC-V instructions"; the sign is
//           always insn[31] so the sign-extension mux stays shallow.
// =============================================================================
`default_nettype none

module rv_imm (
    //== Ports
    input  wire [31:7] insn,        // opcode bits are not needed
    input  wire [2:0]  imm_type,
    output reg  [31:0] imm
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    wire [31:0] imm_i = {{21{insn[31]}}, insn[30:20]};
    wire [31:0] imm_s = {{21{insn[31]}}, insn[30:25], insn[11:7]};
    wire [31:0] imm_b = {{20{insn[31]}}, insn[7], insn[30:25], insn[11:8], 1'b0};
    wire [31:0] imm_u = {insn[31:12], 12'b0};
    wire [31:0] imm_j = {{12{insn[31]}}, insn[19:12], insn[20], insn[30:21], 1'b0};
    wire [31:0] imm_z = {27'b0, insn[19:15]};

    //== Combinational Logic
    always @(*) begin
        imm = imm_i;
        case (imm_type)
            IMM_I:   imm = imm_i;
            IMM_S:   imm = imm_s;
            IMM_B:   imm = imm_b;
            IMM_U:   imm = imm_u;
            IMM_J:   imm = imm_j;
            IMM_Z:   imm = imm_z;
            default: imm = imm_i;
        endcase
    end

    //== Sequential Logic
    // (none: purely combinational)

endmodule

`default_nettype wire
