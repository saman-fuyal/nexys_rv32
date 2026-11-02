// =============================================================================
// timer.v - machine timer (mtime / mtimecmp) and timer interrupt
// -----------------------------------------------------------------------------
// Purpose : The memory-mapped machine timer of the Privileged ISA.
// Registers (word index):
//   0 MTIME_LO  1 MTIME_HI  2 MTIMECMP_LO  3 MTIMECMP_HI  (all RW)
// Behavior: mtime increments once every DIV clocks (1 MHz by default, so one
//           tick = 1 us). mtimecmp resets to all ones so no interrupt fires
//           before software programs it. mtip = (mtime >= mtimecmp) is
//           registered: the 64-bit compare then has a full cycle and the
//           interrupt is seen one clock later, which software cannot observe
//           at 1 us resolution. A write to a half of mtime replaces that half
//           and skips the tick in that cycle.
// =============================================================================
`default_nettype none

module timer #(
    parameter integer DIV = 100,
    parameter integer CW  = 16
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        req,
    input  wire        we,
    input  wire [2:0]  idx,
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire        mtip
);

    //== Localparams/Wires
    reg  [CW-1:0] pre_q, pre_d;
    reg  [63:0]   mtime_q, mtime_d;
    reg  [63:0]   cmp_q,   cmp_d;
    reg           mtip_q,  mtip_d;
    reg  [31:0]   rdata_q, rdata_d;
    reg           tick;
    wire          wr = req & we;
    wire          rd = req & ~we;

    //== Combinational Logic
    always @(*) begin
        tick  = (pre_q == DIV[CW-1:0] - 1'b1);
        pre_d = tick ? {CW{1'b0}} : (pre_q + 1'b1);

        mtime_d = tick ? (mtime_q + 64'd1) : mtime_q;
        cmp_d   = cmp_q;
        if (wr) begin
            case (idx)
                3'd0:    mtime_d = {mtime_q[63:32], wdata};
                3'd1:    mtime_d = {wdata, mtime_q[31:0]};
                3'd2:    cmp_d   = {cmp_q[63:32], wdata};
                3'd3:    cmp_d   = {wdata, cmp_q[31:0]};
                default: cmp_d   = cmp_q;
            endcase
        end
        mtip_d = (mtime_q >= cmp_q);

        rdata_d = 32'd0;
        if (rd) begin
            case (idx)
                3'd0:    rdata_d = mtime_q[31:0];
                3'd1:    rdata_d = mtime_q[63:32];
                3'd2:    rdata_d = cmp_q[31:0];
                3'd3:    rdata_d = cmp_q[63:32];
                default: rdata_d = 32'd0;
            endcase
        end
    end

    assign rdata = rdata_q;
    assign mtip  = mtip_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            pre_q   <= {CW{1'b0}};
            mtime_q <= 64'd0;
            cmp_q   <= {64{1'b1}};
            mtip_q  <= 1'b0;
            rdata_q <= 32'd0;
        end else begin
            pre_q   <= pre_d;
            mtime_q <= mtime_d;
            cmp_q   <= cmp_d;
            mtip_q  <= mtip_d;
            rdata_q <= rdata_d;
        end
    end

endmodule

`default_nettype wire
