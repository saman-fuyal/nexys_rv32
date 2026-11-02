// =============================================================================
// rv_core_pipe.v - 5-stage pipelined RV32I + Zicsr core
// -----------------------------------------------------------------------------
// Purpose : The performance core. Stages IF, ID, EX, MEM, WB.
// Behavior:
//   IF  : pc_q drives the instruction bus. Memories have one cycle of read
//         latency, so the word fetched in IF is decoded in ID one cycle later.
//         While ID stalls, ibus_req is low and the memory holds its output, so
//         the stalled instruction stays on ibus_rdata.
//   ID  : decode, register read (with WB write-through), immediate, load-use
//         hazard check. Illegal/ECALL/EBREAK/fetch-fault are recorded here and
//         travel down the pipe as an exception tag.
//   EX  : forwarding muxes (from MEM and WB), ALU, branch compare and target,
//         jump/branch target and load/store alignment checks. A taken branch
//         or jump redirects fetch from here (2-cycle penalty, static
//         not-taken prediction).
//   MEM : commit point. Exceptions and interrupts are taken here, so state
//         changes are precise: the data bus request, CSR read/write, MRET and
//         FENCE.I all happen only for an instruction that commits in MEM.
//         A trap, MRET or FENCE.I redirects fetch and flushes IF/ID/EX.
//   WB  : load data alignment, register write, retirement report.
//   Loads and CSR reads produce their result late (in WB), so an instruction
//   in ID that needs it stalls one cycle; everything else is forwarded.
// Retire: rvfi_* outputs report every retired instruction (WB) and every
//         trap (MEM) for the testbench trace; they do not affect execution and
//         are left unconnected in the FPGA build.
// =============================================================================
`default_nettype none

module rv_core_pipe #(
    parameter [31:0] RESET_VECTOR = 32'h00000000,
    parameter        ZICSR        = 1,
    parameter        ZIFENCEI     = 1,
    parameter        TIMER_IRQ    = 1,
    parameter [31:0] MISA         = 32'h40000100,
    parameter [31:0] MIMPID       = 32'h00000000
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    // instruction bus (read data one cycle after a request; held when no request)
    output wire        ibus_req,
    output wire [31:0] ibus_addr,
    input  wire [31:0] ibus_rdata,
    input  wire        ibus_fault,     // combinational on ibus_addr
    // data bus (read data one cycle after a request)
    output wire        dbus_req,
    output wire        dbus_we,
    output wire [31:0] dbus_addr,
    output wire [1:0]  dbus_size,
    output wire [3:0]  dbus_wstrb,
    output wire [31:0] dbus_wdata,
    input  wire [31:0] dbus_rdata,
    input  wire        dbus_fault,     // combinational on dbus_addr/size/we
    // interrupt
    input  wire        irq_mtip,
    // retirement report
    output wire        rvfi_valid,
    output wire [31:0] rvfi_pc,
    output wire [31:0] rvfi_insn,
    output wire [4:0]  rvfi_rd,
    output wire [31:0] rvfi_rd_wdata,
    output wire [1:0]  rvfi_mem,       // 0 none, 1 load, 2 store
    output wire [31:0] rvfi_mem_addr,
    output wire [3:0]  rvfi_mem_wstrb,
    output wire [31:0] rvfi_mem_wdata,
    output wire        rvfi_trap,
    output wire [31:0] rvfi_trap_cause,
    output wire [31:0] rvfi_trap_epc,
    output wire [31:0] rvfi_trap_tval,
    // performance events (one bit per event, one cycle wide)
    output wire [5:0]  perf_ev         // {trap, irq, fwd_wb, fwd_mem, flush, stall}
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    // ---- IF -----------------------------------------------------------------
    reg  [31:0] pc_q, pc_d;

    // ---- ID -----------------------------------------------------------------
    reg         d_valid_q, d_valid_d;
    reg  [31:0] d_pc_q, d_pc_d;
    reg         d_fault_q, d_fault_d;
    wire [31:0] d_insn = ibus_rdata;
    wire [4:0]  d_rs1  = d_insn[19:15];
    wire [4:0]  d_rs2  = d_insn[24:20];
    wire [4:0]  d_rd   = d_insn[11:7];

    wire        dec_illegal, dec_uses_rs1, dec_uses_rs2, dec_rd_we;
    wire [3:0]  dec_alu_op;
    wire [1:0]  dec_asel;
    wire        dec_bsel;
    wire [2:0]  dec_imm_type;
    wire [1:0]  dec_wb_sel;
    wire        dec_branch, dec_jal, dec_jalr, dec_load, dec_store;
    wire [1:0]  dec_size;
    wire        dec_unsigned, dec_csr;
    wire [1:0]  dec_csr_op;
    wire        dec_csr_wr, dec_ecall, dec_ebreak, dec_mret, dec_fencei;
    wire [31:0] d_imm;
    wire [31:0] rf_rdata1, rf_rdata2;
    reg  [31:0] d_rs1_val, d_rs2_val;
    reg         d_exc;
    reg  [3:0]  d_cause;
    reg  [31:0] d_tval;
    reg         stall;

    // ---- EX -----------------------------------------------------------------
    reg         e_valid_q, e_valid_d;
    reg  [31:0] e_pc_q, e_insn_q;
    reg  [4:0]  e_rs1_q, e_rs2_q, e_rd_q;
    reg  [31:0] e_rs1_val_q, e_rs2_val_q, e_imm_q;
    reg         e_rd_we_q, e_rd_we_d;
    reg  [3:0]  e_alu_op_q;
    reg  [1:0]  e_asel_q;
    reg         e_bsel_q;
    reg  [1:0]  e_wb_sel_q;
    reg         e_branch_q, e_jal_q, e_jalr_q, e_load_q, e_store_q;
    reg  [1:0]  e_size_q;
    reg         e_unsigned_q, e_csr_q;
    reg  [1:0]  e_csr_op_q;
    reg         e_csr_wr_q, e_mret_q, e_fencei_q;
    reg         e_exc_q;
    reg  [3:0]  e_cause_q;
    reg  [31:0] e_tval_q;

    reg         fwd_a_mem, fwd_a_wb, fwd_b_mem, fwd_b_wb;
    reg  [31:0] op_a, op_b, alu_a, alu_b;
    wire [31:0] alu_y;
    wire        br_taken;
    wire        lsu_misaligned;
    wire [3:0]  lsu_wstrb;
    wire [31:0] lsu_wdata;
    reg         ex_taken;
    reg  [31:0] ex_target;
    reg         ex_exc;
    reg  [3:0]  ex_cause;
    reg  [31:0] ex_tval;
    reg         ex_redirect;
    reg  [31:0] ex_result;

    // ---- MEM ----------------------------------------------------------------
    reg         m_valid_q, m_valid_d;
    reg  [31:0] m_pc_q, m_insn_q;
    reg  [4:0]  m_rd_q;
    reg         m_rd_we_q, m_rd_we_d;
    reg  [31:0] m_result_q, m_addr_q, m_wdata_q, m_csr_src_q, m_csr_src_d;
    reg         m_load_q, m_store_q, m_unsigned_q, m_csr_q;
    reg  [1:0]  m_size_q, m_csr_op_q;
    reg  [3:0]  m_wstrb_q;
    reg         m_csr_wr_q, m_mret_q, m_fencei_q;
    reg         m_exc_q;
    reg  [3:0]  m_cause_q;
    reg  [31:0] m_tval_q;

    wire [31:0] csr_rdata, csr_mtvec, csr_mepc;
    wire        csr_illegal, irq_pending;
    reg         irq_take, mem_fault, csr_trap, trap, commit;
    reg  [31:0] trap_cause, trap_tval;
    reg         mem_redirect;
    reg  [31:0] mem_target;

    // ---- WB -----------------------------------------------------------------
    reg         w_valid_q;
    reg  [31:0] w_pc_q, w_insn_q, w_data_q, w_addr_q, w_wdata_q;
    reg  [31:0] w_data_d, w_wdata_d;
    reg  [3:0]  w_wstrb_d;
    reg  [4:0]  w_rd_q;
    reg         w_rd_we_q, w_load_q, w_store_q, w_unsigned_q;
    reg  [1:0]  w_size_q;
    reg  [3:0]  w_wstrb_q;
    wire [31:0] w_load_data;
    wire [31:0] w_rd_data;
    wire        w_we;

    //== Combinational Logic

    // ---- ID: decode, register read, hazard --------------------------------
    rv_decode #(.ZICSR(ZICSR), .ZIFENCEI(ZIFENCEI)) u_dec (
        .insn(d_insn), .illegal(dec_illegal), .uses_rs1(dec_uses_rs1),
        .uses_rs2(dec_uses_rs2), .rd_we(dec_rd_we), .alu_op(dec_alu_op),
        .alu_a_sel(dec_asel), .alu_b_sel(dec_bsel), .imm_type(dec_imm_type),
        .wb_sel(dec_wb_sel), .is_branch(dec_branch), .is_jal(dec_jal),
        .is_jalr(dec_jalr), .is_load(dec_load), .is_store(dec_store),
        .mem_size(dec_size), .mem_unsigned(dec_unsigned), .is_csr(dec_csr),
        .csr_op(dec_csr_op), .csr_wr_intent(dec_csr_wr), .is_ecall(dec_ecall),
        .is_ebreak(dec_ebreak), .is_mret(dec_mret), .is_fencei(dec_fencei));

    rv_imm u_imm (.insn(d_insn[31:7]), .imm_type(dec_imm_type), .imm(d_imm));

    rv_regfile u_rf (
        .clk(clk), .we(w_we), .waddr(w_rd_q), .wdata(w_rd_data),
        .raddr1(d_rs1), .raddr2(d_rs2), .rdata1(rf_rdata1), .rdata2(rf_rdata2));

    always @(*) begin
        // WB writes at the end of this cycle; pass the new value through now.
        d_rs1_val = (w_we && (w_rd_q == d_rs1)) ? w_rd_data : rf_rdata1;
        d_rs2_val = (w_we && (w_rd_q == d_rs2)) ? w_rd_data : rf_rdata2;

        // Exception priority inside one instruction: fetch fault first, then
        // illegal, then ECALL/EBREAK (they are mutually exclusive encodings).
        d_exc   = d_fault_q | dec_illegal | dec_ecall | dec_ebreak;
        d_cause = EXC_ILLEGAL[3:0];
        d_tval  = d_insn;
        if (d_fault_q) begin
            d_cause = EXC_INSN_FAULT[3:0];
            d_tval  = d_pc_q;
        end else if (dec_illegal) begin
            d_cause = EXC_ILLEGAL[3:0];
            d_tval  = d_insn;
        end else if (dec_ebreak) begin
            d_cause = EXC_BREAKPOINT[3:0];
            d_tval  = d_pc_q;
        end else if (dec_ecall) begin
            d_cause = EXC_ECALL_M[3:0];
            d_tval  = 32'd0;
        end

        // Load-use (and CSR-read-use): the EX instruction's result only exists
        // in WB, two stages later, so the consumer waits one cycle in ID.
        stall = d_valid_q && e_valid_q && (e_load_q || e_csr_q) && e_rd_we_q &&
                ((dec_uses_rs1 && (e_rd_q == d_rs1)) || (dec_uses_rs2 && (e_rd_q == d_rs2)));
    end

    // ---- EX: forwarding, ALU, branch, alignment ---------------------------
    always @(*) begin
        fwd_a_mem = m_valid_q && m_rd_we_q && (m_rd_q == e_rs1_q);
        fwd_b_mem = m_valid_q && m_rd_we_q && (m_rd_q == e_rs2_q);
        fwd_a_wb  = w_we && (w_rd_q == e_rs1_q);
        fwd_b_wb  = w_we && (w_rd_q == e_rs2_q);
        op_a = fwd_a_mem ? m_result_q : (fwd_a_wb ? w_rd_data : e_rs1_val_q);
        op_b = fwd_b_mem ? m_result_q : (fwd_b_wb ? w_rd_data : e_rs2_val_q);

        alu_a = op_a;
        case (e_asel_q)
            ASEL_RS1:  alu_a = op_a;
            ASEL_PC:   alu_a = e_pc_q;
            ASEL_ZERO: alu_a = 32'd0;
            default:   alu_a = op_a;
        endcase
        alu_b = (e_bsel_q == BSEL_IMM) ? e_imm_q : op_b;
    end

    rv_alu u_alu (.a(alu_a), .b(alu_b), .op(e_alu_op_q), .br_funct3(e_insn_q[14:12]),
                  .y(alu_y), .br_taken(br_taken));

    rv_lsu_req u_lsu_req (.addr_lo(alu_y[1:0]), .size(e_size_q), .store_data(op_b),
                          .misaligned(lsu_misaligned), .wstrb(lsu_wstrb), .wdata(lsu_wdata));

    always @(*) begin
        ex_taken  = e_jal_q || e_jalr_q || (e_branch_q && br_taken);
        ex_target = e_jalr_q ? {alu_y[31:1], 1'b0} : (e_pc_q + e_imm_q);

        ex_exc   = e_exc_q;
        ex_cause = e_cause_q;
        ex_tval  = e_tval_q;
        if (!e_exc_q) begin
            if (ex_taken && ex_target[1]) begin
                ex_exc   = 1'b1;
                ex_cause = EXC_INSN_MISALIGNED[3:0];
                ex_tval  = ex_target;
            end else if ((e_load_q || e_store_q) && lsu_misaligned) begin
                ex_exc   = 1'b1;
                ex_cause = e_store_q ? EXC_STORE_MISALIGNED[3:0] : EXC_LOAD_MISALIGNED[3:0];
                ex_tval  = alu_y;
            end
        end
        ex_redirect = e_valid_q && ex_taken && !ex_exc;
        ex_result   = (e_wb_sel_q == WB_PC4) ? (e_pc_q + 32'd4) : alu_y;
    end

    // ---- MEM: commit, traps, data bus, CSRs -------------------------------
    rv_csr #(.TIMER_IRQ(TIMER_IRQ), .MISA(MISA), .MIMPID(MIMPID)) u_csr (
        .clk(clk), .rst(rst),
        .csr_addr(m_insn_q[31:20]), .csr_op(m_csr_op_q), .csr_src(m_csr_src_q),
        .csr_wr_intent(m_csr_wr_q), .csr_en(commit && m_csr_q),
        .csr_rdata(csr_rdata), .csr_illegal(csr_illegal),
        .trap_en(trap), .trap_cause(trap_cause), .trap_epc(m_pc_q[31:2]),
        .trap_tval(trap_tval), .mret_en(commit && m_mret_q), .instret_en(commit),
        .irq_mtip(irq_mtip), .mtvec(csr_mtvec), .mepc(csr_mepc),
        .irq_pending(irq_pending));

    always @(*) begin
        irq_take  = m_valid_q && irq_pending;
        mem_fault = m_valid_q && !m_exc_q && (m_load_q || m_store_q) && dbus_fault;
        csr_trap  = m_valid_q && !m_exc_q && m_csr_q && csr_illegal;
        trap      = irq_take || (m_valid_q && m_exc_q) || mem_fault || csr_trap;
        commit    = m_valid_q && !trap;

        trap_cause = {28'd0, EXC_ILLEGAL[3:0]};
        trap_tval  = m_insn_q;
        if (irq_take) begin
            trap_cause = {1'b1, IRQ_MTIMER};
            trap_tval  = 32'd0;
        end else if (m_exc_q) begin
            trap_cause = {28'd0, m_cause_q};
            trap_tval  = m_tval_q;
        end else if (mem_fault) begin
            trap_cause = {28'd0, (m_store_q ? EXC_STORE_FAULT[3:0] : EXC_LOAD_FAULT[3:0])};
            trap_tval  = m_addr_q;
        end

        mem_redirect = trap || (commit && (m_mret_q || m_fencei_q));
        mem_target   = m_pc_q + 32'd4;
        if (trap) begin
            mem_target = csr_mtvec;
        end else if (m_mret_q) begin
            mem_target = csr_mepc;
        end
    end

    assign dbus_req   = m_valid_q && (m_load_q || m_store_q) && !m_exc_q && !irq_take;
    assign dbus_we    = m_store_q;
    assign dbus_addr  = m_addr_q;
    assign dbus_size  = m_size_q;
    assign dbus_wstrb = m_store_q ? m_wstrb_q : 4'b0000;
    assign dbus_wdata = m_wdata_q;

    // ---- WB ---------------------------------------------------------------
    rv_lsu_load u_lsu_load (.raw(dbus_rdata), .addr_lo(w_addr_q[1:0]), .size(w_size_q),
                            .is_unsigned(w_unsigned_q), .data(w_load_data));

    assign w_rd_data = w_load_q ? w_load_data : w_data_q;
    assign w_we      = w_valid_q && w_rd_we_q;

    // ---- IF: next pc --------------------------------------------------------
    always @(*) begin
        pc_d      = pc_q + 32'd4;
        d_valid_d = 1'b1;
        d_pc_d    = pc_q;
        d_fault_d = ibus_fault;
        if (mem_redirect) begin
            pc_d      = mem_target;
            d_valid_d = 1'b0;
        end else if (ex_redirect) begin
            pc_d      = ex_target;
            d_valid_d = 1'b0;
        end else if (stall) begin
            pc_d      = pc_q;
            d_valid_d = d_valid_q;
            d_pc_d    = d_pc_q;
            d_fault_d = d_fault_q;
        end

        // Pipeline valid bits: younger stages are squashed by any redirect.
        e_valid_d = d_valid_q && !stall && !ex_redirect && !mem_redirect;
        m_valid_d = e_valid_q && !mem_redirect;
    end

    // Next values of the datapath registers that need any logic.
    always @(*) begin
        e_rd_we_d   = dec_rd_we && (d_rd != 5'd0);
        m_rd_we_d   = e_rd_we_q && !ex_exc;
        m_csr_src_d = e_insn_q[14] ? e_imm_q : op_a;     // CSRxxI uses the uimm
        w_data_d    = m_csr_q ? csr_rdata : m_result_q;
        w_wdata_d   = m_wdata_q & {{8{m_wstrb_q[3]}}, {8{m_wstrb_q[2]}},
                                   {8{m_wstrb_q[1]}}, {8{m_wstrb_q[0]}}};
        w_wstrb_d   = m_store_q ? m_wstrb_q : 4'b0000;
    end

    assign ibus_req  = !stall;
    assign ibus_addr = pc_q;

    // ---- retirement report -------------------------------------------------
    assign rvfi_valid      = w_valid_q;
    assign rvfi_pc         = w_pc_q;
    assign rvfi_insn       = w_insn_q;
    assign rvfi_rd         = w_we ? w_rd_q : 5'd0;
    assign rvfi_rd_wdata   = w_we ? w_rd_data : 32'd0;
    assign rvfi_mem        = w_load_q ? 2'd1 : (w_store_q ? 2'd2 : 2'd0);
    assign rvfi_mem_addr   = w_addr_q;
    assign rvfi_mem_wstrb  = w_wstrb_q;
    assign rvfi_mem_wdata  = w_wdata_q;
    assign rvfi_trap       = trap;
    assign rvfi_trap_cause = trap_cause;
    assign rvfi_trap_epc   = m_pc_q;
    assign rvfi_trap_tval  = trap_tval;
    assign perf_ev = {trap, irq_take,
                      e_valid_q && (fwd_a_wb || fwd_b_wb) && !(fwd_a_mem || fwd_b_mem),
                      e_valid_q && (fwd_a_mem || fwd_b_mem),
                      ex_redirect, stall};

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            pc_q      <= RESET_VECTOR;
            d_valid_q <= 1'b0;
            e_valid_q <= 1'b0;
            m_valid_q <= 1'b0;
            w_valid_q <= 1'b0;
        end else begin
            pc_q      <= pc_d;
            d_valid_q <= d_valid_d;
            e_valid_q <= e_valid_d;
            m_valid_q <= m_valid_d;
            w_valid_q <= commit;
        end
    end

    // Datapath registers need no reset: the valid bits above qualify them.
    always @(posedge clk) begin
        d_pc_q    <= d_pc_d;
        d_fault_q <= d_fault_d;

        // ID -> EX
        e_pc_q       <= d_pc_q;
        e_insn_q     <= d_insn;
        e_rs1_q      <= d_rs1;
        e_rs2_q      <= d_rs2;
        e_rd_q       <= d_rd;
        e_rs1_val_q  <= d_rs1_val;
        e_rs2_val_q  <= d_rs2_val;
        e_imm_q      <= d_imm;
        e_rd_we_q    <= e_rd_we_d;
        e_alu_op_q   <= dec_alu_op;
        e_asel_q     <= dec_asel;
        e_bsel_q     <= dec_bsel;
        e_wb_sel_q   <= dec_wb_sel;
        e_branch_q   <= dec_branch;
        e_jal_q      <= dec_jal;
        e_jalr_q     <= dec_jalr;
        e_load_q     <= dec_load;
        e_store_q    <= dec_store;
        e_size_q     <= dec_size;
        e_unsigned_q <= dec_unsigned;
        e_csr_q      <= dec_csr;
        e_csr_op_q   <= dec_csr_op;
        e_csr_wr_q   <= dec_csr_wr;
        e_mret_q     <= dec_mret;
        e_fencei_q   <= dec_fencei;
        e_exc_q      <= d_exc;
        e_cause_q    <= d_cause;
        e_tval_q     <= d_tval;

        // EX -> MEM
        m_pc_q       <= e_pc_q;
        m_insn_q     <= e_insn_q;
        m_rd_q       <= e_rd_q;
        m_rd_we_q    <= m_rd_we_d;
        m_result_q   <= ex_result;
        m_addr_q     <= alu_y;
        m_wdata_q    <= lsu_wdata;
        m_wstrb_q    <= lsu_wstrb;
        m_csr_src_q  <= m_csr_src_d;
        m_load_q     <= e_load_q;
        m_store_q    <= e_store_q;
        m_size_q     <= e_size_q;
        m_unsigned_q <= e_unsigned_q;
        m_csr_q      <= e_csr_q;
        m_csr_op_q   <= e_csr_op_q;
        m_csr_wr_q   <= e_csr_wr_q;
        m_mret_q     <= e_mret_q;
        m_fencei_q   <= e_fencei_q;
        m_exc_q      <= ex_exc;
        m_cause_q    <= ex_cause;
        m_tval_q     <= ex_tval;

        // MEM -> WB
        w_pc_q       <= m_pc_q;
        w_insn_q     <= m_insn_q;
        w_rd_q       <= m_rd_q;
        w_rd_we_q    <= m_rd_we_q;
        w_data_q     <= w_data_d;
        w_addr_q     <= m_addr_q;
        w_wdata_q    <= w_wdata_d;
        w_wstrb_q    <= w_wstrb_d;
        w_load_q     <= m_load_q;
        w_store_q    <= m_store_q;
        w_size_q     <= m_size_q;
        w_unsigned_q <= m_unsigned_q;
    end

endmodule

`default_nettype wire
