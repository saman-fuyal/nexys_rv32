// =============================================================================
// uart.v - memory-mapped UART (TXDATA, RXDATA, STATUS)
// -----------------------------------------------------------------------------
// Purpose : Byte serial port to the Nexys A7 USB-UART bridge (FT2232HQ).
// Registers (word index):
//   0 TXDATA  W  write starts transmission if TX is idle, else ignored
//   1 RXDATA  R  last received byte; reading clears RX_VALID
//   2 STATUS  RW bit0 TX_BUSY, bit1 RX_VALID, bit2 RX_OVERRUN, bit3 FRAME_ERR
//                writing 1 to bit 2 or 3 clears it
// Behavior: One-byte receive buffer. A byte that arrives while RX_VALID is
//           still set replaces the old byte and sets RX_OVERRUN. Software
//           polls STATUS; at 115200 baud a byte takes 8680 clocks, ample for a
//           polling loop. Read data is registered (one-cycle bus latency).
// =============================================================================
`default_nettype none

module uart #(
    parameter integer DIV = 868
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        req,
    input  wire        we,
    input  wire [2:0]  idx,
    input  wire [7:0]  wdata,       // registers are at most 8 bits wide
    output wire [31:0] rdata,
    input  wire        rx_pin,      // asynchronous
    output wire        tx_pin
);

    //== Localparams/Wires
    wire       rx_sync;
    wire       tx_busy;
    wire       rx_valid_pulse;
    wire [7:0] rx_byte;
    wire       rx_ferr;

    reg        tx_start;
    reg        rx_valid_q,  rx_valid_d;
    reg [7:0]  rx_data_q,   rx_data_d;
    reg        overrun_q,   overrun_d;
    reg        ferr_q,      ferr_d;
    reg [31:0] rdata_q,     rdata_d;

    wire       wr = req & we;
    wire       rd = req & ~we;

    //== Combinational Logic
    sync2 #(.WIDTH(1), .RESET_VAL(1'b1)) u_sync (.clk(clk), .rst(rst), .d(rx_pin), .q(rx_sync));

    uart_tx #(.DIV(DIV)) u_tx (.clk(clk), .rst(rst), .start(tx_start), .data(wdata[7:0]),
                               .busy(tx_busy), .tx(tx_pin));

    uart_rx #(.DIV(DIV)) u_rx (.clk(clk), .rst(rst), .rx(rx_sync), .valid(rx_valid_pulse),
                               .data(rx_byte), .frame_err(rx_ferr));

    always @(*) begin
        tx_start   = wr && (idx == 3'd0) && !tx_busy;
        rx_valid_d = rx_valid_q;
        rx_data_d  = rx_data_q;
        overrun_d  = overrun_q;
        ferr_d     = ferr_q;
        rdata_d    = 32'd0;

        // Software actions first, so a byte arriving in the same cycle wins.
        if (rd && (idx == 3'd1)) begin
            rx_valid_d = 1'b0;
        end
        if (wr && (idx == 3'd2)) begin
            overrun_d = overrun_q & ~wdata[2];
            ferr_d    = ferr_q    & ~wdata[3];
        end
        if (rx_valid_pulse) begin
            rx_data_d  = rx_byte;
            rx_valid_d = 1'b1;
            if (rx_valid_q && !(rd && (idx == 3'd1))) begin
                overrun_d = 1'b1;
            end
            if (rx_ferr) begin
                ferr_d = 1'b1;
            end
        end

        if (rd) begin
            case (idx)
                3'd1:    rdata_d = {24'd0, rx_data_q};
                3'd2:    rdata_d = {28'd0, ferr_q, overrun_q, rx_valid_q, tx_busy};
                default: rdata_d = 32'd0;
            endcase
        end
    end

    assign rdata = rdata_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            rx_valid_q <= 1'b0;
            rx_data_q  <= 8'd0;
            overrun_q  <= 1'b0;
            ferr_q     <= 1'b0;
            rdata_q    <= 32'd0;
        end else begin
            rx_valid_q <= rx_valid_d;
            rx_data_q  <= rx_data_d;
            overrun_q  <= overrun_d;
            ferr_q     <= ferr_d;
            rdata_q    <= rdata_d;
        end
    end

endmodule

`default_nettype wire
