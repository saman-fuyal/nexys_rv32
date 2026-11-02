// =============================================================================
// uart_rx.v - 8N1 UART receiver
// -----------------------------------------------------------------------------
// Purpose : Deserialize bytes from a synchronized RX line.
// Behavior: A falling edge while idle starts a frame. The start bit is
//           re-checked at its middle (DIV/2 clocks later); a high level there
//           is treated as a glitch and the receiver returns to idle. Data bits
//           are sampled every DIV clocks at their middles, LSB first. 'valid'
//           pulses for one clock after the stop-bit sample; 'frame_err' is set
//           with it when the stop bit reads 0.
// =============================================================================
`default_nettype none

module uart_rx #(
    parameter integer DIV = 868,
    parameter integer CW  = 16
) (
    //== Ports
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,          // already synchronized, idle high
    output wire       valid,
    output wire [7:0] data,
    output wire       frame_err
);

    //== Localparams/Wires
    localparam [1:0] S_IDLE  = 2'd0;
    localparam [1:0] S_START = 2'd1;
    localparam [1:0] S_DATA  = 2'd2;
    localparam [1:0] S_STOP  = 2'd3;

    reg [1:0]    state_q, state_d;
    reg [CW-1:0] cnt_q,   cnt_d;
    reg [2:0]    bit_q,   bit_d;
    reg [7:0]    shift_q, shift_d;
    reg          rx_prev_q;
    reg          valid_q, valid_d;
    reg          ferr_q,  ferr_d;
    wire         tick_half = (cnt_q == (DIV[CW-1:0] >> 1));
    wire         tick_full = (cnt_q == DIV[CW-1:0] - 1'b1);

    //== Combinational Logic
    always @(*) begin
        state_d = state_q;
        cnt_d   = cnt_q + 1'b1;
        bit_d   = bit_q;
        shift_d = shift_q;
        valid_d = 1'b0;
        ferr_d  = 1'b0;
        case (state_q)
            S_IDLE: begin
                cnt_d = {CW{1'b0}};
                if (rx_prev_q && !rx) begin
                    state_d = S_START;
                end
            end
            S_START: begin
                if (tick_half) begin
                    cnt_d   = {CW{1'b0}};
                    bit_d   = 3'd0;
                    state_d = rx ? S_IDLE : S_DATA;
                end
            end
            S_DATA: begin
                if (tick_full) begin
                    cnt_d   = {CW{1'b0}};
                    shift_d = {rx, shift_q[7:1]};
                    bit_d   = bit_q + 3'd1;
                    if (bit_q == 3'd7) begin
                        state_d = S_STOP;
                    end
                end
            end
            S_STOP: begin
                if (tick_full) begin
                    valid_d = 1'b1;
                    ferr_d  = ~rx;
                    state_d = S_IDLE;
                end
            end
            default: state_d = S_IDLE;
        endcase
    end

    assign valid     = valid_q;
    assign data      = shift_q;
    assign frame_err = ferr_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            state_q   <= S_IDLE;
            cnt_q     <= {CW{1'b0}};
            bit_q     <= 3'd0;
            shift_q   <= 8'd0;
            rx_prev_q <= 1'b1;
            valid_q   <= 1'b0;
            ferr_q    <= 1'b0;
        end else begin
            state_q   <= state_d;
            cnt_q     <= cnt_d;
            bit_q     <= bit_d;
            shift_q   <= shift_d;
            rx_prev_q <= rx;
            valid_q   <= valid_d;
            ferr_q    <= ferr_d;
        end
    end

endmodule

`default_nettype wire
