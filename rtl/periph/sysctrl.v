// =============================================================================
// sysctrl.v - system control and identification registers
// -----------------------------------------------------------------------------
// Purpose : A test-result mailbox (riscv-tests "tohost") and read-only
//           identification words so software can check what it runs on.
// Registers (word index):
//   0 TOHOST    RW  1 = pass, (n<<1)|1 = fail n; the testbench stops on write
//   1 TOHOST_HI RW  upper half of the riscv-tests tohost doubleword
//   2 CLK_HZ    R   CPU clock in Hz
//   3 FEATURES  R   bit0 zicsr, bit1 timer_irq, bit2 zifencei, bit3 pipelined
//   4 BUILD_ID  R   project build id
// Behavior: Writes to read-only words are ignored.
// =============================================================================
`default_nettype none

module sysctrl #(
    parameter [31:0] CLK_HZ   = 32'd100000000,
    parameter [31:0] FEATURES = 32'd0,
    parameter [31:0] BUILD_ID = 32'd0
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    input  wire        req,
    input  wire        we,
    input  wire [2:0]  idx,
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire [31:0] tohost
);

    //== Localparams/Wires
    reg [31:0] tohost_q,    tohost_d;
    reg [31:0] tohost_hi_q, tohost_hi_d;
    reg [31:0] rdata_q,     rdata_d;
    wire       wr = req & we;
    wire       rd = req & ~we;

    //== Combinational Logic
    always @(*) begin
        tohost_d    = tohost_q;
        tohost_hi_d = tohost_hi_q;
        rdata_d     = 32'd0;
        if (wr && (idx == 3'd0)) begin
            tohost_d = wdata;
        end
        if (wr && (idx == 3'd1)) begin
            tohost_hi_d = wdata;
        end
        if (rd) begin
            case (idx)
                3'd0:    rdata_d = tohost_q;
                3'd1:    rdata_d = tohost_hi_q;
                3'd2:    rdata_d = CLK_HZ;
                3'd3:    rdata_d = FEATURES;
                3'd4:    rdata_d = BUILD_ID;
                default: rdata_d = 32'd0;
            endcase
        end
    end

    assign rdata  = rdata_q;
    assign tohost = tohost_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            tohost_q    <= 32'd0;
            tohost_hi_q <= 32'd0;
            rdata_q     <= 32'd0;
        end else begin
            tohost_q    <= tohost_d;
            tohost_hi_q <= tohost_hi_d;
            rdata_q     <= rdata_d;
        end
    end

endmodule

`default_nettype wire
