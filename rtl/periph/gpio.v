// =============================================================================
// gpio.v - LEDs, slide switches and push buttons
// -----------------------------------------------------------------------------
// Purpose : Give software the 16 LEDs, 16 switches and 5 buttons of the board.
// Registers (word index):
//   0 LEDS     RW  LED[15:0], 1 = on (LEDs are active high on the Nexys A7)
//   1 SWITCHES R   SW[15:0] after a two-flop synchronizer
//   2 BUTTONS  R   {BTND, BTNR, BTNL, BTNU, BTNC} debounced, 1 = pressed
//   3 BTN_EDGE RW  sticky bit per button, set on each debounced press,
//                  write 1 to clear
// Behavior: Buttons are synchronized and then debounced (DEBOUNCE clocks).
//           A press and a software clear in the same cycle leave the bit set,
//           so no press is lost.
// =============================================================================
`default_nettype none

module gpio #(
    parameter integer DEBOUNCE = 1000000
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        req,
    input  wire        we,
    input  wire [2:0]  idx,
    input  wire [15:0] wdata,       // registers are at most 16 bits wide
    output wire [31:0] rdata,
    input  wire [15:0] sw_pin,      // asynchronous
    input  wire [4:0]  btn_pin,     // asynchronous, active high
    output wire [15:0] led
);

    //== Localparams/Wires
    wire [15:0] sw_sync;
    wire [4:0]  btn_sync;
    wire [4:0]  btn_db;
    reg  [15:0] led_q,  led_d;
    reg  [4:0]  btn_prev_q;
    reg  [4:0]  edge_q, edge_d;
    reg  [31:0] rdata_q, rdata_d;
    wire        wr = req & we;
    wire        rd = req & ~we;
    genvar      gi;

    //== Combinational Logic
    sync2 #(.WIDTH(16)) u_sw_sync  (.clk(clk), .rst(rst), .d(sw_pin),  .q(sw_sync));
    sync2 #(.WIDTH(5))  u_btn_sync (.clk(clk), .rst(rst), .d(btn_pin), .q(btn_sync));

    generate
        for (gi = 0; gi < 5; gi = gi + 1) begin : g_db
            debounce #(.CYCLES(DEBOUNCE), .CW(24)) u_db (
                .clk(clk), .rst(rst), .d(btn_sync[gi]), .q(btn_db[gi]));
        end
    endgenerate

    always @(*) begin
        led_d   = led_q;
        edge_d  = edge_q;
        rdata_d = 32'd0;
        if (wr && (idx == 3'd0)) begin
            led_d = wdata[15:0];
        end
        if (wr && (idx == 3'd3)) begin
            edge_d = edge_q & ~wdata[4:0];
        end
        edge_d = edge_d | (btn_db & ~btn_prev_q);
        if (rd) begin
            case (idx)
                3'd0:    rdata_d = {16'd0, led_q};
                3'd1:    rdata_d = {16'd0, sw_sync};
                3'd2:    rdata_d = {27'd0, btn_db};
                3'd3:    rdata_d = {27'd0, edge_q};
                default: rdata_d = 32'd0;
            endcase
        end
    end

    assign led   = led_q;
    assign rdata = rdata_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            led_q      <= 16'd0;
            btn_prev_q <= 5'd0;
            edge_q     <= 5'd0;
            rdata_q    <= 32'd0;
        end else begin
            led_q      <= led_d;
            btn_prev_q <= btn_db;
            edge_q     <= edge_d;
            rdata_q    <= rdata_d;
        end
    end

endmodule

`default_nettype wire
