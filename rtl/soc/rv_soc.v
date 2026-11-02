// =============================================================================
// rv_soc.v - SoC top: core, boot ROM, RAM, bus and peripherals
// -----------------------------------------------------------------------------
// Purpose : Everything except the FPGA-specific clocking/reset and pin
//           mapping (fpga/rtl/fpga_top.v), so the same module is simulated
//           and synthesized.
// Behavior: CORE_PIPE selects the core: 1 = rv_core_pipe, 0 = rv_core_mc.
//           The memory map, divisors and feature flags come from the
//           generated rtl/gen/soc_params.vh. Two parameters exist only for
//           simulation: START_PC != 0 overrides the reset vector (tests that
//           are preloaded into RAM skip the bootloader), and SIM_DEBOUNCE != 0
//           shortens the button debounce time, and SIM_RAM_AW != 0 enlarges
//           the RAM for the riscv-arch-test configuration (its jump tests
//           are larger than any on-chip RAM). All are 0 in the FPGA build.
//           'rst' must be synchronous to clk (fpga_top provides it).
// =============================================================================
`default_nettype none

module rv_soc #(
    parameter        CORE_PIPE    = 1,
    parameter [31:0] START_PC     = 32'h00000000,
    parameter integer SIM_DEBOUNCE = 0,
    parameter integer SIM_RAM_AW   = 0
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        uart_rx,
    output wire        uart_tx,
    input  wire [15:0] sw,
    input  wire [4:0]  btn,           // {BTND, BTNR, BTNL, BTNU, BTNC}
    output wire [15:0] led,
    output wire [7:0]  an_n,
    output wire [6:0]  seg_n,
    output wire        dp_n,
    // retirement report and status for the testbench (unused on the FPGA)
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
    output wire [5:0]  perf_ev,
    output wire [31:0] tohost
);

    //== Localparams/Wires
    `include "soc_params.vh"

    localparam [31:0]  BOOT_PC  = (START_PC != 32'h00000000) ? START_PC : RESET_VECTOR;
    localparam integer DEB      = (SIM_DEBOUNCE != 0) ? SIM_DEBOUNCE : DEBOUNCE_CYCLES;
    localparam integer RAMAW    = (SIM_RAM_AW != 0) ? SIM_RAM_AW : RAM_AW;
    localparam [31:0]  FEATURES = {28'd0, (CORE_PIPE != 0), FEAT_ZIFENCEI, FEAT_TIMER_IRQ, FEAT_ZICSR};

    wire        ibus_req, ibus_fault;
    wire [31:0] ibus_addr, ibus_rdata;
    wire        dbus_req, dbus_we, dbus_fault;
    wire [31:0] dbus_addr, dbus_wdata, dbus_rdata;
    wire [1:0]  dbus_size;
    wire [3:0]  dbus_wstrb;
    wire        irq_mtip;

    wire        rom_a_en, ram_a_en, rom_b_en, ram_b_en;
    wire [31:0] rom_a_rdata, ram_a_rdata, rom_b_rdata, ram_b_rdata;
    wire [4:0]  per_req;
    wire [2:0]  per_idx;
    wire [31:0] rd_uart, rd_gpio, rd_seg7, rd_timer, rd_sys;
    wire [31:0] per_rdata = rd_uart | rd_gpio | rd_seg7 | rd_timer | rd_sys;

    //== Combinational Logic
    generate
        if (CORE_PIPE != 0) begin : g_core
            rv_core_pipe #(
                .RESET_VECTOR(BOOT_PC), .ZICSR(FEAT_ZICSR), .ZIFENCEI(FEAT_ZIFENCEI),
                .TIMER_IRQ(FEAT_TIMER_IRQ), .MISA(MISA_VALUE), .MIMPID(MIMPID_VALUE)
            ) u_core (
                .clk(clk), .rst(rst),
                .ibus_req(ibus_req), .ibus_addr(ibus_addr), .ibus_rdata(ibus_rdata),
                .ibus_fault(ibus_fault),
                .dbus_req(dbus_req), .dbus_we(dbus_we), .dbus_addr(dbus_addr),
                .dbus_size(dbus_size), .dbus_wstrb(dbus_wstrb), .dbus_wdata(dbus_wdata),
                .dbus_rdata(dbus_rdata), .dbus_fault(dbus_fault), .irq_mtip(irq_mtip),
                .rvfi_valid(rvfi_valid), .rvfi_pc(rvfi_pc), .rvfi_insn(rvfi_insn),
                .rvfi_rd(rvfi_rd), .rvfi_rd_wdata(rvfi_rd_wdata), .rvfi_mem(rvfi_mem),
                .rvfi_mem_addr(rvfi_mem_addr), .rvfi_mem_wstrb(rvfi_mem_wstrb),
                .rvfi_mem_wdata(rvfi_mem_wdata), .rvfi_trap(rvfi_trap),
                .rvfi_trap_cause(rvfi_trap_cause), .rvfi_trap_epc(rvfi_trap_epc),
                .rvfi_trap_tval(rvfi_trap_tval), .perf_ev(perf_ev));
        end else begin : g_core
            rv_core_mc #(
                .RESET_VECTOR(BOOT_PC), .ZICSR(FEAT_ZICSR), .ZIFENCEI(FEAT_ZIFENCEI),
                .TIMER_IRQ(FEAT_TIMER_IRQ), .MISA(MISA_VALUE), .MIMPID(MIMPID_VALUE)
            ) u_core (
                .clk(clk), .rst(rst),
                .ibus_req(ibus_req), .ibus_addr(ibus_addr), .ibus_rdata(ibus_rdata),
                .ibus_fault(ibus_fault),
                .dbus_req(dbus_req), .dbus_we(dbus_we), .dbus_addr(dbus_addr),
                .dbus_size(dbus_size), .dbus_wstrb(dbus_wstrb), .dbus_wdata(dbus_wdata),
                .dbus_rdata(dbus_rdata), .dbus_fault(dbus_fault), .irq_mtip(irq_mtip),
                .rvfi_valid(rvfi_valid), .rvfi_pc(rvfi_pc), .rvfi_insn(rvfi_insn),
                .rvfi_rd(rvfi_rd), .rvfi_rd_wdata(rvfi_rd_wdata), .rvfi_mem(rvfi_mem),
                .rvfi_mem_addr(rvfi_mem_addr), .rvfi_mem_wstrb(rvfi_mem_wstrb),
                .rvfi_mem_wdata(rvfi_mem_wdata), .rvfi_trap(rvfi_trap),
                .rvfi_trap_cause(rvfi_trap_cause), .rvfi_trap_epc(rvfi_trap_epc),
                .rvfi_trap_tval(rvfi_trap_tval), .perf_ev(perf_ev));
        end
    endgenerate

    soc_bus #(.RAM_AW_P(RAMAW)) u_bus (
        .clk(clk), .rst(rst),
        .ibus_req(ibus_req), .ibus_addr(ibus_addr), .ibus_fault(ibus_fault),
        .ibus_rdata(ibus_rdata),
        .dbus_req(dbus_req), .dbus_we(dbus_we), .dbus_addr(dbus_addr),
        .dbus_size(dbus_size), .dbus_fault(dbus_fault), .dbus_rdata(dbus_rdata),
        .rom_a_en(rom_a_en), .ram_a_en(ram_a_en), .rom_b_en(rom_b_en), .ram_b_en(ram_b_en),
        .rom_a_rdata(rom_a_rdata), .ram_a_rdata(ram_a_rdata),
        .rom_b_rdata(rom_b_rdata), .ram_b_rdata(ram_b_rdata),
        .per_req(per_req), .per_idx(per_idx), .per_rdata(per_rdata));

    bootrom u_rom (
        .clk(clk),
        .a_en(rom_a_en), .a_addr(ibus_addr[ROM_AW-1:2]), .a_rdata(rom_a_rdata),
        .b_en(rom_b_en), .b_addr(dbus_addr[ROM_AW-1:2]), .b_rdata(rom_b_rdata));

    soc_ram #(.AW(RAMAW - 2)) u_ram (
        .clk(clk),
        .a_en(ram_a_en), .a_addr(ibus_addr[RAMAW-1:2]), .a_rdata(ram_a_rdata),
        .b_en(ram_b_en), .b_we(dbus_wstrb), .b_addr(dbus_addr[RAMAW-1:2]),
        .b_wdata(dbus_wdata), .b_rdata(ram_b_rdata));

    uart #(.DIV(UART_DIV)) u_uart (
        .clk(clk), .rst(rst), .req(per_req[0]), .we(dbus_we), .idx(per_idx),
        .wdata(dbus_wdata[7:0]), .rdata(rd_uart), .rx_pin(uart_rx), .tx_pin(uart_tx));

    gpio #(.DEBOUNCE(DEB)) u_gpio (
        .clk(clk), .rst(rst), .req(per_req[1]), .we(dbus_we), .idx(per_idx),
        .wdata(dbus_wdata[15:0]), .rdata(rd_gpio), .sw_pin(sw), .btn_pin(btn), .led(led));

    seg7 #(.DIV(SEG7_DIV)) u_seg7 (
        .clk(clk), .rst(rst), .req(per_req[2]), .we(dbus_we), .idx(per_idx),
        .wdata(dbus_wdata), .rdata(rd_seg7), .an_n(an_n), .seg_n(seg_n), .dp_n(dp_n));

    timer #(.DIV(TIMER_DIV)) u_timer (
        .clk(clk), .rst(rst), .req(per_req[3]), .we(dbus_we), .idx(per_idx),
        .wdata(dbus_wdata), .rdata(rd_timer), .mtip(irq_mtip));

    sysctrl #(.CLK_HZ(CPU_HZ), .FEATURES(FEATURES), .BUILD_ID(BUILD_ID)) u_sys (
        .clk(clk), .rst(rst), .req(per_req[4]), .we(dbus_we), .idx(per_idx),
        .wdata(dbus_wdata), .rdata(rd_sys), .tohost(tohost));

    //== Sequential Logic
    // (none: all state is inside the instantiated blocks)

endmodule

`default_nettype wire
