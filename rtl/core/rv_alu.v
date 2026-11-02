// =============================================================================
// rv_alu.v - integer ALU and branch comparator
// -----------------------------------------------------------------------------
// Purpose : The ten RV32I arithmetic/logic operations plus the three compares
//           used by conditional branches.
// Behavior: Combinational. Shifts use b[4:0] only (RV32I semantics for both
//           register and immediate shifts). SUB is computed as a + ~b + 1 so
//           SLT/SLTU and the branch compare can reuse one 33-bit subtractor
//           instead of three separate comparators.
// =============================================================================
`default_nettype none

module rv_alu (
    //== Ports
    input  wire [31:0] a,
    input  wire [31:0] b,
    input  wire [3:0]  op,
    input  wire [2:0]  br_funct3,   // branch condition (BEQ..BGEU funct3)
    output reg  [31:0] y,
    output reg         br_taken
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    // 33-bit a - b: bit 32 is the borrow, i.e. a < b as unsigned numbers.
    wire [32:0] diff  = {1'b0, a} + {1'b0, ~b} + 33'd1;
    wire        ltu   = ~diff[32];
    wire        lt    = (a[31] ^ b[31]) ? a[31] : diff[31];
    wire        eq    = (a == b);
    wire [4:0]  shamt = b[4:0];
    wire [31:0] sra_y = $signed(a) >>> shamt;

    //== Combinational Logic
    always @(*) begin
        y = 32'd0;
        case (op)
            ALU_ADD:  y = a + b;
            ALU_SUB:  y = diff[31:0];
            ALU_SLL:  y = a << shamt;
            ALU_SLT:  y = {31'd0, lt};
            ALU_SLTU: y = {31'd0, ltu};
            ALU_XOR:  y = a ^ b;
            ALU_SRL:  y = a >> shamt;
            ALU_SRA:  y = sra_y;
            ALU_OR:   y = a | b;
            ALU_AND:  y = a & b;
            default:  y = a + b;
        endcase
    end

    always @(*) begin
        br_taken = 1'b0;
        case (br_funct3)
            3'b000:  br_taken = eq;     // BEQ
            3'b001:  br_taken = ~eq;    // BNE
            3'b100:  br_taken = lt;     // BLT
            3'b101:  br_taken = ~lt;    // BGE
            3'b110:  br_taken = ltu;    // BLTU
            3'b111:  br_taken = ~ltu;   // BGEU
            default: br_taken = 1'b0;   // reserved; the decoder flags these illegal
        endcase
    end

    //== Sequential Logic
    // (none: purely combinational)

endmodule

`default_nettype wire
