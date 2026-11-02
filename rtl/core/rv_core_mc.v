// =============================================================================
// rv_core_mc.v - multi-cycle RV32I + Zicsr core
// -----------------------------------------------------------------------------
// Purpose : The reference core: one instruction at a time, no hazards, easy to
//           follow. It shares the decoder, ALU, register file, load/store
//           helpers and CSR file with the pipelined core, so the two differ
//           only in control.
// Behavior: Four states.
//   FETCH  : take a pending interrupt, or request the word at pc_q.
//   DECODE : the word arrives (one-cycle memory latency); latch it in ir_q and
//            read rs1/rs2 from the register file.
//   EXEC   : ALU, branch, CSR, exceptions. Non-load instructions finish here
//            and retire; loads issue their bus request and go to MEM.
//   MEM    : align/extend the load data, write rd, retire.
//   CPI is 3 for every instruction except loads (4). Exceptions are detected
//   in EXEC before any state changes, so they are precise by construction.
// Retire: rvfi_* outputs mirror rv_core_pipe for the testbench trace.
// =============================================================================
`default_nettype none

module rv_core_mc #(
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
    output wire        ibus_req,
    output wire [31:0] ibus_addr,
    input  wire [31:0] ibus_rdata,
    input  wire        ibus_fault,
    output wire        dbus_req,
    output wire        dbus_we,
    output wire [31:0] dbus_addr,
    output wire [1:0]  dbus_size,
    output wire [3:0]  dbus_wstrb,
    output wire [31:0] dbus_wdata,
    input  wire [31:0] dbus_rdata,
    input  wire        dbus_fault,
    input  wire        irq_mtip,
    output wire        rvfi_valid,
    output wire [31:0] rvfi_pc,
    output wire [31:0] rvfi_insn,
    output wire [4:0]  rvfi_rd,
    output wire [31:0] rvfi_rd_wdata,
    output wire [1:0]  rvfi_mem,
    output wire [31:0] rvfi_mem_addr,
    output wire [3:0]  rvfi_mem_wstrb,
    output wire [31:0] rvfi_mem_wdata,
    output wire        rvfi_trap,
    output wire [31:0] rvfi_trap_cause,
    output wire [31:0] rvfi_trap_epc,
    output wire [31:0] rvfi_trap_tval,
    output wire [5:0]  perf_ev          // {trap, irq, 0, 0, 0, 0}
);

    //== Localparams/Wires
    `include "rv_defs.vh"

    localparam [1:0] S_FETCH  = 2'd0;
    localparam [1:0] S_DECODE = 2'd1;
    localparam [1:0] S_EXEC   = 2'd2;
    localparam [1:0] S_MEM    = 2'd3;

    reg  [1:0]  state_q, state_d;
    reg  [31:0] pc_q, pc_d;
    reg  [31:0] ir_q, ir_d;
    reg         fault_q, fault_d;
    reg  [31:0] a_q, a_d;           // rs1 value
    reg  [31:0] b_q, b_d;           // rs2 value
    reg  [31:0] addr_q, addr_d;     // load address, kept for MEM

    wire        dec_illegal, dec_rd_we;
    wire [3:0]  dec_alu_op;
    wire [1:0]  dec_asel;
    wire        dec_bsel;
    wire [2:0]  dec_imm_type;
    wire [1:0]  dec_wb_sel;
    wire        dec_branch, dec_jal, dec_jalr, dec_load, dec_store;
    wire [1:0]  dec_size;
    wire        dec_unsigned, dec_csr;
    wire [1:0]  dec_csr_op;
    wire        dec_csr_wr, dec_ecall, dec_ebreak, dec_mret;
    wire [31:0] imm;
    wire [31:0] rf_rdata1, rf_rdata2;
    reg  [31:0] alu_a, alu_b;
    wire [31:0] alu_y;
    wire        br_taken;
    wire        lsu_misaligned;
    wire [3:0]  lsu_wstrb;
    wire [31:0] lsu_wdata;
    wire [31:0] load_data;
    wire [31:0] csr_rdata, csr_mtvec, csr_mepc;
    wire        csr_illegal, irq_pending;

    reg         in_exec, in_mem, irq_take;
    reg         taken;
    reg  [31:0] target;
    reg         exc;                // exception detected before the bus
    reg  [3:0]  cause;
    reg  [31:0] tval;
    reg         mem_fault, csr_trap, trap;
    reg  [31:0] trap_cause, trap_tval;
    reg         retire;
    reg         rf_we;
    reg  [31:0] rf_wdata;
    reg  [31:0] store_mask;

    //== Combinational Logic
    // Waiver: three decoder outputs are intentionally unconnected (see below).
    /* verilator lint_off PINCONNECTEMPTY */
    rv_decode #(.ZICSR(ZICSR), .ZIFENCEI(ZIFENCEI)) u_dec (
        .insn(ir_q), .illegal(dec_illegal),
        // no hazards and no prefetch: register-use and FENCE.I flags are not needed
        .uses_rs1(), .uses_rs2(), .rd_we(dec_rd_we), .alu_op(dec_alu_op),
        .alu_a_sel(dec_asel), .alu_b_sel(dec_bsel), .imm_type(dec_imm_type),
        .wb_sel(dec_wb_sel), .is_branch(dec_branch), .is_jal(dec_jal),
        .is_jalr(dec_jalr), .is_load(dec_load), .is_store(dec_store),
        .mem_size(dec_size), .mem_unsigned(dec_unsigned), .is_csr(dec_csr),
        .csr_op(dec_csr_op), .csr_wr_intent(dec_csr_wr), .is_ecall(dec_ecall),
        .is_ebreak(dec_ebreak), .is_mret(dec_mret), .is_fencei());
    /* verilator lint_on PINCONNECTEMPTY */

    rv_imm u_imm (.insn(ir_q[31:7]), .imm_type(dec_imm_type), .imm(imm));

    // Registers are read from the word arriving in DECODE.
    rv_regfile u_rf (
        .clk(clk), .we(rf_we), .waddr(ir_q[11:7]), .wdata(rf_wdata),
        .raddr1(ibus_rdata[19:15]), .raddr2(ibus_rdata[24:20]),
        .rdata1(rf_rdata1), .rdata2(rf_rdata2));

    always @(*) begin
        alu_a = a_q;
        case (dec_asel)
            ASEL_RS1:  alu_a = a_q;
            ASEL_PC:   alu_a = pc_q;
            ASEL_ZERO: alu_a = 32'd0;
            default:   alu_a = a_q;
        endcase
        alu_b = (dec_bsel == BSEL_IMM) ? imm : b_q;
    end

    rv_alu u_alu (.a(alu_a), .b(alu_b), .op(dec_alu_op), .br_funct3(ir_q[14:12]),
                  .y(alu_y), .br_taken(br_taken));

    rv_lsu_req u_lsu_req (.addr_lo(alu_y[1:0]), .size(dec_size), .store_data(b_q),
                          .misaligned(lsu_misaligned), .wstrb(lsu_wstrb), .wdata(lsu_wdata));

    rv_lsu_load u_lsu_load (.raw(dbus_rdata), .addr_lo(addr_q[1:0]), .size(dec_size),
                            .is_unsigned(dec_unsigned), .data(load_data));

    rv_csr #(.TIMER_IRQ(TIMER_IRQ), .MISA(MISA), .MIMPID(MIMPID)) u_csr (
        .clk(clk), .rst(rst),
        .csr_addr(ir_q[31:20]), .csr_op(dec_csr_op),
        .csr_src(ir_q[14] ? imm : a_q), .csr_wr_intent(dec_csr_wr),
        .csr_en(in_exec && !trap && dec_csr),
        .csr_rdata(csr_rdata), .csr_illegal(csr_illegal),
        .trap_en(trap), .trap_cause(trap_cause), .trap_epc(pc_q[31:2]),
        .trap_tval(trap_tval), .mret_en(in_exec && !trap && dec_mret),
        .instret_en(retire), .irq_mtip(irq_mtip), .mtvec(csr_mtvec),
        .mepc(csr_mepc), .irq_pending(irq_pending));

    // Exception detection and commit decision
    always @(*) begin
        in_exec  = (state_q == S_EXEC);
        in_mem   = (state_q == S_MEM);
        irq_take = (state_q == S_FETCH) && irq_pending;

        taken  = dec_jal || dec_jalr || (dec_branch && br_taken);
        target = dec_jalr ? {alu_y[31:1], 1'b0} : (pc_q + imm);

        exc   = 1'b0;
        cause = EXC_ILLEGAL[3:0];
        tval  = 32'd0;
        if (fault_q) begin
            exc = 1'b1;  cause = EXC_INSN_FAULT[3:0];       tval = pc_q;
        end else if (dec_illegal) begin
            exc = 1'b1;  cause = EXC_ILLEGAL[3:0];          tval = ir_q;
        end else if (dec_ebreak) begin
            exc = 1'b1;  cause = EXC_BREAKPOINT[3:0];       tval = pc_q;
        end else if (dec_ecall) begin
            exc = 1'b1;  cause = EXC_ECALL_M[3:0];          tval = 32'd0;
        end else if (taken && target[1]) begin
            exc = 1'b1;  cause = EXC_INSN_MISALIGNED[3:0];  tval = target;
        end else if ((dec_load || dec_store) && lsu_misaligned) begin
            exc = 1'b1;
            cause = dec_store ? EXC_STORE_MISALIGNED[3:0] : EXC_LOAD_MISALIGNED[3:0];
            tval = alu_y;
        end

        mem_fault = in_exec && !exc && (dec_load || dec_store) && dbus_fault;
        csr_trap  = in_exec && !exc && dec_csr && csr_illegal;
        trap      = irq_take || (in_exec && exc) || mem_fault || csr_trap;

        trap_cause = {28'd0, cause};
        trap_tval  = tval;
        if (irq_take) begin
            trap_cause = {1'b1, IRQ_MTIMER};
            trap_tval  = 32'd0;
        end else if (mem_fault) begin
            trap_cause = {28'd0, (dec_store ? EXC_STORE_FAULT[3:0] : EXC_LOAD_FAULT[3:0])};
            trap_tval  = alu_y;
        end else if (csr_trap) begin
            trap_cause = {28'd0, EXC_ILLEGAL[3:0]};
            trap_tval  = ir_q;
        end

        retire = (in_exec && !trap && !dec_load) || in_mem;

        rf_we    = retire && dec_rd_we;
        rf_wdata = alu_y;
        case (dec_wb_sel)
            WB_ALU:  rf_wdata = alu_y;
            WB_PC4:  rf_wdata = pc_q + 32'd4;
            WB_MEM:  rf_wdata = load_data;
            WB_CSR:  rf_wdata = csr_rdata;
            default: rf_wdata = alu_y;
        endcase

        store_mask = {{8{lsu_wstrb[3]}}, {8{lsu_wstrb[2]}}, {8{lsu_wstrb[1]}}, {8{lsu_wstrb[0]}}};
    end

    // Next-state
    always @(*) begin
        state_d = state_q;
        pc_d    = pc_q;
        ir_d    = ir_q;
        fault_d = fault_q;
        a_d     = a_q;
        b_d     = b_q;
        addr_d  = addr_q;
        case (state_q)
            S_FETCH: begin
                if (irq_take) begin
                    pc_d = csr_mtvec;
                end else begin
                    fault_d = ibus_fault;
                    state_d = S_DECODE;
                end
            end
            S_DECODE: begin
                ir_d    = ibus_rdata;
                a_d     = rf_rdata1;
                b_d     = rf_rdata2;
                state_d = S_EXEC;
            end
            S_EXEC: begin
                state_d = S_FETCH;
                if (trap) begin
                    pc_d = csr_mtvec;
                end else if (dec_load) begin
                    addr_d  = alu_y;
                    state_d = S_MEM;
                end else if (dec_mret) begin
                    pc_d = csr_mepc;
                end else if (taken) begin
                    pc_d = target;
                end else begin
                    pc_d = pc_q + 32'd4;
                end
            end
            S_MEM: begin
                pc_d    = pc_q + 32'd4;
                state_d = S_FETCH;
            end
            default: state_d = S_FETCH;
        endcase
    end

    assign ibus_req   = (state_q == S_FETCH) && !irq_take;
    assign ibus_addr  = pc_q;
    assign dbus_req   = in_exec && (dec_load || dec_store) && !exc;
    assign dbus_we    = dec_store;
    assign dbus_addr  = alu_y;
    assign dbus_size  = dec_size;
    assign dbus_wstrb = dec_store ? lsu_wstrb : 4'b0000;
    assign dbus_wdata = lsu_wdata;

    assign rvfi_valid      = retire;
    assign rvfi_pc         = pc_q;
    assign rvfi_insn       = ir_q;
    assign rvfi_rd         = (rf_we && (ir_q[11:7] != 5'd0)) ? ir_q[11:7] : 5'd0;
    assign rvfi_rd_wdata   = (rf_we && (ir_q[11:7] != 5'd0)) ? rf_wdata : 32'd0;
    assign rvfi_mem        = dec_load ? 2'd1 : (dec_store ? 2'd2 : 2'd0);
    assign rvfi_mem_addr   = in_mem ? addr_q : alu_y;
    assign rvfi_mem_wstrb  = dec_store ? lsu_wstrb : 4'b0000;
    assign rvfi_mem_wdata  = lsu_wdata & store_mask;
    assign rvfi_trap       = trap;
    assign rvfi_trap_cause = trap_cause;
    assign rvfi_trap_epc   = pc_q;
    assign rvfi_trap_tval  = trap_tval;
    assign perf_ev         = {trap, irq_take, 4'b0000};

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            state_q <= S_FETCH;
            pc_q    <= RESET_VECTOR;
            fault_q <= 1'b0;
        end else begin
            state_q <= state_d;
            pc_q    <= pc_d;
            fault_q <= fault_d;
        end
    end

    always @(posedge clk) begin
        ir_q   <= ir_d;
        a_q    <= a_d;
        b_q    <= b_d;
        addr_q <= addr_d;
    end

endmodule

`default_nettype wire
