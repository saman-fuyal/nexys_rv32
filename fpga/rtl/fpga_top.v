// =============================================================================
// fpga_top.v - Nexys A7-50T top level: pins, clock, reset
// -----------------------------------------------------------------------------
// Purpose : Connect rv_soc to the board. Port names match the Digilent
//           Nexys-A7-50T-Master.xdc so the constraint file needs no renaming.
// Behavior:
//   Clock : CPU_HZ = 100 MHz uses CLK100MHZ directly (Vivado adds a BUFG).
//           50 or 75 MHz instantiate an MMCME2_BASE (VCO 1000 / 900 MHz) and
//           hold reset until it locks; this is the fallback if the 100 MHz
//           build misses timing.
//   Reset : CPU_RESETN (active low, asynchronous button) passes a two-flop
//           synchronizer. A power-on counter then keeps reset asserted for
//           256 clocks after configuration or after the button is released.
//           The counter relies on the FPGA configuring every flip-flop to 0
//           (GSR); in simulation the testbench presses CPU_RESETN first.
//           The SoC sees a purely synchronous reset.
//   Pins  : buttons and switches go to the SoC raw; it synchronizes them.
//           UART_TXD_IN is the FPGA input (data from the PC), UART_RXD_OUT
//           the FPGA output (names are from the FT2232's point of view).
// =============================================================================
`default_nettype none

module fpga_top #(
    parameter CORE_PIPE = 1          // 1 = 5-stage pipeline, 0 = multi-cycle
) (
    //== Ports
    input  wire        CLK100MHZ,
    input  wire        CPU_RESETN,
    input  wire        UART_TXD_IN,
    output wire        UART_RXD_OUT,
    input  wire [15:0] SW,
    output wire [15:0] LED,
    input  wire        BTNC,
    input  wire        BTNU,
    input  wire        BTNL,
    input  wire        BTNR,
    input  wire        BTND,
    output wire        CA,
    output wire        CB,
    output wire        CC,
    output wire        CD,
    output wire        CE,
    output wire        CF,
    output wire        CG,
    output wire        DP,
    output wire [7:0]  AN
);

    //== Localparams/Wires
    `include "soc_params.vh"

    localparam integer OSC_HZ = 100000000;

    wire       clk;
    wire       mmcm_locked;
    (* ASYNC_REG = "TRUE" *) reg rst_meta_q;
    (* ASYNC_REG = "TRUE" *) reg rst_sync_q;
    reg  [7:0] por_q, por_d;
    reg        rst_q, rst_d;
    wire [6:0] seg_n;
    wire       rst_req = ~CPU_RESETN;

    //== Combinational Logic
    generate
        if (CPU_HZ == OSC_HZ) begin : g_clk
            assign clk         = CLK100MHZ;
            assign mmcm_locked = 1'b1;
        end else begin : g_clk
            wire clk_fb, clk_mmcm;
            MMCME2_BASE #(
                .CLKIN1_PERIOD    (10.000),
                .DIVCLK_DIVIDE    (1),
                .CLKFBOUT_MULT_F  ((CPU_HZ == 75000000) ? 9.0 : 10.0),
                .CLKOUT0_DIVIDE_F ((CPU_HZ == 75000000) ? 12.0 : 20.0)
            ) u_mmcm (
                .CLKIN1(CLK100MHZ), .CLKFBIN(clk_fb), .CLKFBOUT(clk_fb),
                .CLKOUT0(clk_mmcm), .LOCKED(mmcm_locked), .RST(1'b0), .PWRDWN(1'b0));
            BUFG u_bufg (.I(clk_mmcm), .O(clk));
        end
    endgenerate

    always @(*) begin
        por_d = por_q;
        rst_d = 1'b1;
        if (rst_sync_q || !mmcm_locked) begin
            por_d = 8'd0;
        end else if (por_q != 8'hFF) begin
            por_d = por_q + 8'd1;
        end else begin
            rst_d = 1'b0;
        end
    end

    rv_soc #(.CORE_PIPE(CORE_PIPE)) u_soc (
        .clk(clk), .rst(rst_q),
        .uart_rx(UART_TXD_IN), .uart_tx(UART_RXD_OUT),
        .sw(SW), .btn({BTND, BTNR, BTNL, BTNU, BTNC}),
        .led(LED), .an_n(AN), .seg_n(seg_n), .dp_n(DP),
        // Waiver: simulation-only outputs, intentionally unconnected here.
        /* verilator lint_off PINCONNECTEMPTY */
        .rvfi_valid(), .rvfi_pc(), .rvfi_insn(), .rvfi_rd(), .rvfi_rd_wdata(),
        .rvfi_mem(), .rvfi_mem_addr(), .rvfi_mem_wstrb(), .rvfi_mem_wdata(),
        .rvfi_trap(), .rvfi_trap_cause(), .rvfi_trap_epc(), .rvfi_trap_tval(),
        .perf_ev(), .tohost()
        /* verilator lint_on PINCONNECTEMPTY */
    );

    assign {CG, CF, CE, CD, CC, CB, CA} = seg_n;

    //== Sequential Logic
    always @(posedge clk) begin
        rst_meta_q <= rst_req;
        rst_sync_q <= rst_meta_q;
        por_q      <= por_d;
        rst_q      <= rst_d;
    end

endmodule

`default_nettype wire
