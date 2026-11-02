// =============================================================================
// uart_tx.v - 8N1 UART transmitter
// -----------------------------------------------------------------------------
// Purpose : Serialize one byte: start bit (0), 8 data bits LSB first, stop
//           bit (1).
// Behavior: 'start' is accepted only while busy = 0. Each bit lasts DIV
//           clocks. The line idles high. busy stays high until the end of
//           the stop bit, so back-to-back bytes keep a full stop bit.
// =============================================================================
`default_nettype none

module uart_tx #(
    parameter integer DIV = 868,          // clocks per bit
    parameter integer CW  = 16            // divider counter width
) (
    //== Ports
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] data,
    output wire       busy,
    output wire       tx
);

    //== Localparams/Wires
    reg  [9:0]    shift_q, shift_d;       // {stop, data[7:0], start}, LSB first
    reg  [3:0]    nbits_q, nbits_d;       // bits left to send
    reg  [CW-1:0] cnt_q,   cnt_d;
    reg           tx_q,    tx_d;

    //== Combinational Logic
    always @(*) begin
        shift_d = shift_q;
        nbits_d = nbits_q;
        cnt_d   = cnt_q;
        tx_d    = tx_q;
        if (nbits_q == 4'd0) begin
            tx_d = 1'b1;
            if (start) begin
                shift_d = {1'b1, data, 1'b0};
                nbits_d = 4'd10;
                cnt_d   = {CW{1'b0}};
            end
        end else begin
            tx_d = shift_q[0];
            if (cnt_q == DIV[CW-1:0] - 1'b1) begin
                cnt_d   = {CW{1'b0}};
                shift_d = {1'b1, shift_q[9:1]};
                nbits_d = nbits_q - 4'd1;
            end else begin
                cnt_d = cnt_q + 1'b1;
            end
        end
    end

    assign busy = (nbits_q != 4'd0);
    assign tx   = tx_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            shift_q <= 10'h3FF;
            nbits_q <= 4'd0;
            cnt_q   <= {CW{1'b0}};
            tx_q    <= 1'b1;
        end else begin
            shift_q <= shift_d;
            nbits_q <= nbits_d;
            cnt_q   <= cnt_d;
            tx_q    <= tx_d;
        end
    end

endmodule

`default_nettype wire
