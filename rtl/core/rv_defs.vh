// =============================================================================
// rv_defs.vh - RV32I encoding constants shared by both cores
// -----------------------------------------------------------------------------
// Purpose : Name the opcode, ALU and exception codes once so the decoder, the
//           ALU and both cores agree. Values come from the RISC-V Unprivileged
//           ISA (RV32I opcode map) and the Privileged ISA (mcause table).
// Usage   : `include inside a module body; it only declares localparams.
// Lint  : not every includer uses every constant, so UNUSEDPARAM is waived
//         for this header only.
// =============================================================================
// verilator lint_off UNUSEDPARAM

// Major opcodes, instruction bits [6:0]
localparam [6:0] OPC_LOAD     = 7'b0000011;
localparam [6:0] OPC_MISC_MEM = 7'b0001111;
localparam [6:0] OPC_OP_IMM   = 7'b0010011;
localparam [6:0] OPC_AUIPC    = 7'b0010111;
localparam [6:0] OPC_STORE    = 7'b0100011;
localparam [6:0] OPC_OP       = 7'b0110011;
localparam [6:0] OPC_LUI      = 7'b0110111;
localparam [6:0] OPC_BRANCH   = 7'b1100011;
localparam [6:0] OPC_JALR     = 7'b1100111;
localparam [6:0] OPC_JAL      = 7'b1101111;
localparam [6:0] OPC_SYSTEM   = 7'b1110011;

// ALU operation = {alternate bit, funct3}; matches the R-type encoding so the
// decoder can pass {insn[30], funct3} straight through for OP instructions.
localparam [3:0] ALU_ADD  = 4'b0000;
localparam [3:0] ALU_SUB  = 4'b1000;
localparam [3:0] ALU_SLL  = 4'b0001;
localparam [3:0] ALU_SLT  = 4'b0010;
localparam [3:0] ALU_SLTU = 4'b0011;
localparam [3:0] ALU_XOR  = 4'b0100;
localparam [3:0] ALU_SRL  = 4'b0101;
localparam [3:0] ALU_SRA  = 4'b1101;
localparam [3:0] ALU_OR   = 4'b0110;
localparam [3:0] ALU_AND  = 4'b0111;

// ALU operand selects
localparam [1:0] ASEL_RS1  = 2'd0;
localparam [1:0] ASEL_PC   = 2'd1;
localparam [1:0] ASEL_ZERO = 2'd2;
localparam       BSEL_RS2  = 1'b0;
localparam       BSEL_IMM  = 1'b1;

// Immediate formats
localparam [2:0] IMM_I = 3'd0;
localparam [2:0] IMM_S = 3'd1;
localparam [2:0] IMM_B = 3'd2;
localparam [2:0] IMM_U = 3'd3;
localparam [2:0] IMM_J = 3'd4;
localparam [2:0] IMM_Z = 3'd5;   // CSR zero-extended 5-bit uimm (rs1 field)

// Result select for rd
localparam [1:0] WB_ALU = 2'd0;
localparam [1:0] WB_PC4 = 2'd1;
localparam [1:0] WB_MEM = 2'd2;
localparam [1:0] WB_CSR = 2'd3;

// Memory access size (funct3[1:0])
localparam [1:0] SZ_B = 2'd0;
localparam [1:0] SZ_H = 2'd1;
localparam [1:0] SZ_W = 2'd2;

// CSR operation (funct3[1:0])
localparam [1:0] CSR_RW = 2'd1;
localparam [1:0] CSR_RS = 2'd2;
localparam [1:0] CSR_RC = 2'd3;

// mcause exception codes
localparam [30:0] EXC_INSN_MISALIGNED  = 31'd0;
localparam [30:0] EXC_INSN_FAULT       = 31'd1;
localparam [30:0] EXC_ILLEGAL          = 31'd2;
localparam [30:0] EXC_BREAKPOINT       = 31'd3;
localparam [30:0] EXC_LOAD_MISALIGNED  = 31'd4;
localparam [30:0] EXC_LOAD_FAULT       = 31'd5;
localparam [30:0] EXC_STORE_MISALIGNED = 31'd6;
localparam [30:0] EXC_STORE_FAULT      = 31'd7;
localparam [30:0] EXC_ECALL_M          = 31'd11;
localparam [30:0] IRQ_MTIMER           = 31'd7;

// verilator lint_on UNUSEDPARAM
