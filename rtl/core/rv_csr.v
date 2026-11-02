// =============================================================================
// rv_csr.v - machine-mode CSR file, trap state and counters
// -----------------------------------------------------------------------------
// Purpose : Holds the Zicsr machine-mode registers listed in params.json and
//           performs the CSR side of trap entry (exception or interrupt) and
//           MRET.
// Behavior: csr_rdata / csr_illegal are combinational on csr_addr so the core
//           can decide in its commit stage whether a CSR instruction traps.
//           All state updates happen at the clock edge:
//             - CSR instruction (csr_en): RW/RS/RC on the addressed register
//             - trap_en : mepc, mcause, mtval written; MPIE <= MIE; MIE <= 0
//             - mret_en : MIE <= MPIE; MPIE <= 1 (MPP is hardwired to M)
//           mcycle counts every cycle and minstret every committed
//           instruction; a CSR write to either takes precedence over the
//           increment in that cycle (Privileged ISA, counter CSR semantics;
//           checked by riscv-tests rv32mi instret_overflow).
//           Unimplemented addresses and writes to the read-only space
//           (addr[11:10] = 11) report csr_illegal.
// =============================================================================
`default_nettype none

module rv_csr #(
    parameter        TIMER_IRQ = 1,
    parameter [31:0] MISA      = 32'h40000100,
    parameter [31:0] MIMPID    = 32'h00000000
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    // CSR instruction in the commit stage
    input  wire [11:0] csr_addr,
    input  wire [1:0]  csr_op,
    input  wire [31:0] csr_src,       // rs1 value or zero-extended uimm
    input  wire        csr_wr_intent,
    input  wire        csr_en,        // commit this CSR instruction now
    output reg  [31:0] csr_rdata,
    output reg         csr_illegal,
    // trap entry and return
    input  wire        trap_en,
    input  wire [31:0] trap_cause,
    input  wire [31:2] trap_epc,      // pc of the trapping/interrupted instruction
    input  wire [31:0] trap_tval,
    input  wire        mret_en,
    input  wire        instret_en,    // one instruction commits this cycle
    input  wire        irq_mtip,      // machine timer interrupt pending (level)
    output wire [31:0] mtvec,
    output wire [31:0] mepc,
    output wire        irq_pending
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    localparam [11:0] A_MSTATUS   = 12'h300;
    localparam [11:0] A_MISA      = 12'h301;
    localparam [11:0] A_MIE       = 12'h304;
    localparam [11:0] A_MTVEC     = 12'h305;
    localparam [11:0] A_MSTATUSH  = 12'h310;
    localparam [11:0] A_MSCRATCH  = 12'h340;
    localparam [11:0] A_MEPC      = 12'h341;
    localparam [11:0] A_MCAUSE    = 12'h342;
    localparam [11:0] A_MTVAL     = 12'h343;
    localparam [11:0] A_MIP       = 12'h344;
    localparam [11:0] A_MCYCLE    = 12'hB00;
    localparam [11:0] A_MINSTRET  = 12'hB02;
    localparam [11:0] A_MCYCLEH   = 12'hB80;
    localparam [11:0] A_MINSTRETH = 12'hB82;
    localparam [11:0] A_MVENDORID = 12'hF11;
    localparam [11:0] A_MARCHID   = 12'hF12;
    localparam [11:0] A_MIMPID    = 12'hF13;
    localparam [11:0] A_MHARTID   = 12'hF14;
    localparam [11:0] A_MCONFIGPTR= 12'hF15;

    reg        mie_q,   mie_d;        // mstatus.MIE
    reg        mpie_q,  mpie_d;       // mstatus.MPIE
    reg        mtie_q,  mtie_d;       // mie.MTIE
    reg [29:0] mtvec_q, mtvec_d;      // BASE[31:2], MODE = direct
    reg [31:0] mscratch_q, mscratch_d;
    reg [29:0] mepc_q,  mepc_d;
    reg [31:0] mcause_q, mcause_d;
    reg [31:0] mtval_q, mtval_d;
    reg [63:0] mcycle_q, mcycle_d;
    reg [63:0] minstret_q, minstret_d;

    reg        known;                 // csr_addr is implemented
    reg [31:0] wval;                  // value an RW/RS/RC would write
    wire       mtip     = irq_mtip & (TIMER_IRQ != 0);
    wire       read_only = (csr_addr[11:10] == 2'b11);
    wire       do_write  = csr_en & csr_wr_intent & ~csr_illegal;

    //== Combinational Logic
    // Read mux and legality
    always @(*) begin
        csr_rdata = 32'd0;
        known     = 1'b1;
        case (csr_addr)
            A_MSTATUS:   csr_rdata = {19'd0, 2'b11, 3'd0, mpie_q, 3'd0, mie_q, 3'd0};
            A_MISA:      csr_rdata = MISA;
            A_MIE:       csr_rdata = {24'd0, mtie_q, 7'd0};
            A_MTVEC:     csr_rdata = {mtvec_q, 2'b00};
            A_MSTATUSH:  csr_rdata = 32'd0;
            A_MSCRATCH:  csr_rdata = mscratch_q;
            A_MEPC:      csr_rdata = {mepc_q, 2'b00};
            A_MCAUSE:    csr_rdata = mcause_q;
            A_MTVAL:     csr_rdata = mtval_q;
            A_MIP:       csr_rdata = {24'd0, mtip, 7'd0};
            A_MCYCLE:    csr_rdata = mcycle_q[31:0];
            A_MINSTRET:  csr_rdata = minstret_q[31:0];
            A_MCYCLEH:   csr_rdata = mcycle_q[63:32];
            A_MINSTRETH: csr_rdata = minstret_q[63:32];
            A_MVENDORID: csr_rdata = 32'd0;
            A_MARCHID:   csr_rdata = 32'd0;
            A_MIMPID:    csr_rdata = MIMPID;
            A_MHARTID:   csr_rdata = 32'd0;
            A_MCONFIGPTR:csr_rdata = 32'd0;
            default: begin
                csr_rdata = 32'd0;
                known     = 1'b0;
            end
        endcase
        csr_illegal = ~known | (csr_wr_intent & read_only);
    end

    // Write value for CSRRW/CSRRS/CSRRC (and the immediate forms)
    always @(*) begin
        wval = csr_src;
        case (csr_op)
            CSR_RW:  wval = csr_src;
            CSR_RS:  wval = csr_rdata | csr_src;
            CSR_RC:  wval = csr_rdata & ~csr_src;
            default: wval = csr_src;
        endcase
    end

    // Next-state
    always @(*) begin
        mie_d      = mie_q;
        mpie_d     = mpie_q;
        mtie_d     = mtie_q;
        mtvec_d    = mtvec_q;
        mscratch_d = mscratch_q;
        mepc_d     = mepc_q;
        mcause_d   = mcause_q;
        mtval_d    = mtval_q;
        mcycle_d   = mcycle_q + 64'd1;
        minstret_d = instret_en ? (minstret_q + 64'd1) : minstret_q;

        if (trap_en) begin
            mepc_d   = trap_epc;
            mcause_d = trap_cause;
            mtval_d  = trap_tval;
            mpie_d   = mie_q;
            mie_d    = 1'b0;
        end else if (mret_en) begin
            mie_d    = mpie_q;
            mpie_d   = 1'b1;
        end else if (do_write) begin
            case (csr_addr)
                A_MSTATUS: begin
                    mie_d  = wval[3];
                    mpie_d = wval[7];
                end
                A_MIE:       mtie_d     = wval[7] & (TIMER_IRQ != 0);
                A_MTVEC:     mtvec_d    = wval[31:2];
                A_MSCRATCH:  mscratch_d = wval;
                A_MEPC:      mepc_d     = wval[31:2];
                A_MCAUSE:    mcause_d   = wval;
                A_MTVAL:     mtval_d    = wval;
                A_MCYCLE:    mcycle_d   = {mcycle_q[63:32], wval};
                A_MCYCLEH:   mcycle_d   = {wval, mcycle_q[31:0]};
                A_MINSTRET:  minstret_d = {minstret_q[63:32], wval};
                A_MINSTRETH: minstret_d = {wval, minstret_q[31:0]};
                default:     mtie_d     = mtie_q;   // WARL registers ignore writes
            endcase
        end
    end

    assign mtvec       = {mtvec_q, 2'b00};
    assign mepc        = {mepc_q, 2'b00};
    assign irq_pending = mie_q & mtie_q & mtip;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            mie_q      <= 1'b0;
            mpie_q     <= 1'b0;
            mtie_q     <= 1'b0;
            mtvec_q    <= 30'd0;
            mscratch_q <= 32'd0;
            mepc_q     <= 30'd0;
            mcause_q   <= 32'd0;
            mtval_q    <= 32'd0;
            mcycle_q   <= 64'd0;
            minstret_q <= 64'd0;
        end else begin
            mie_q      <= mie_d;
            mpie_q     <= mpie_d;
            mtie_q     <= mtie_d;
            mtvec_q    <= mtvec_d;
            mscratch_q <= mscratch_d;
            mepc_q     <= mepc_d;
            mcause_q   <= mcause_d;
            mtval_q    <= mtval_d;
            mcycle_q   <= mcycle_d;
            minstret_q <= minstret_d;
        end
    end

endmodule

`default_nettype wire
