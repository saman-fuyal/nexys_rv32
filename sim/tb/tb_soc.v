// =============================================================================
// tb_soc.v - system testbench for rv_soc (Icarus Verilog and Vivado xsim)
// -----------------------------------------------------------------------------
// Purpose : Run one program on the full SoC and record everything the checks
//           need: the retired-instruction trace (same format as the golden
//           ISS), the UART output decoded from the TX pin, the 7-segment
//           digits decoded from the AN/segment pins, LEDs and tohost.
// Plusargs: +hex=<file>        preload RAM (32-bit words, $readmemh format)
//           +trace=<file>      write the retirement trace
//           +uartlog=<file>    write bytes decoded from the uart_tx pin
//           +uartin=<file>     bytes ($readmemh, one per line) sent on uart_rx
//           +uartin_at=<n>     clock cycle at which UART input starts
//           +max_cycles=<n>    stop with TIMEOUT after n cycles
//           +sw=<hex>          switch value; +sw2=<hex> +sw2_at=<n> change it
//           +btn=<hex> +btn_at=<n> +btn_len=<n>  press buttons for a while
//           +settle=<n>        keep simulating n cycles after the end (display scan)
//           +vcd=<file>        dump waveforms (+vcd_start=<n> +vcd_len=<n>
//                              limit the dump to a window of clock cycles)
//           +sigfile=<file> +sig_begin=<hex> +sig_end=<hex>
//                              dump RAM words [begin,end) after the run
//                              (riscv-arch-test signatures)
// Params  : CORE_PIPE (1 pipelined / 0 multi-cycle), START_PC (0 = boot ROM),
//           SIM_RAM_AW (0 = board RAM; else RAM address bits, arch-test runs)
// Output  : a final line "TB_RESULT ..." parsed by sim/run_sim.py
// Language: Verilog-2005 only, so both simulators accept it unchanged.
// =============================================================================
`timescale 1ns / 1ps

module tb_soc;

    parameter        CORE_PIPE  = 1;
    parameter [31:0] START_PC   = 32'h80000000;
    parameter integer SIM_RAM_AW = 0;           // 0 = board RAM size

    `include "soc_params.vh"

    localparam integer RAM_WORDS = (1 << (((SIM_RAM_AW != 0) ? SIM_RAM_AW : RAM_AW) - 2));

    reg         clk = 1'b0;
    reg         rst = 1'b1;
    reg         uart_rx = 1'b1;
    reg  [15:0] sw = 16'h0000;
    reg  [4:0]  btn = 5'b00000;
    wire        uart_tx;
    wire [15:0] led;
    wire [7:0]  an_n;
    wire [6:0]  seg_n;
    wire        dp_n;
    wire        rvfi_valid, rvfi_trap;
    wire [31:0] rvfi_pc, rvfi_insn, rvfi_rd_wdata, rvfi_mem_addr, rvfi_mem_wdata;
    wire [31:0] rvfi_trap_cause, rvfi_trap_epc, rvfi_trap_tval, tohost;
    wire [4:0]  rvfi_rd;
    wire [1:0]  rvfi_mem;
    wire [3:0]  rvfi_mem_wstrb;
    wire [5:0]  perf_ev;

    rv_soc #(.CORE_PIPE(CORE_PIPE), .START_PC(START_PC), .SIM_DEBOUNCE(50),
             .SIM_RAM_AW(SIM_RAM_AW)) dut (
        .clk(clk), .rst(rst), .uart_rx(uart_rx), .uart_tx(uart_tx), .sw(sw), .btn(btn),
        .led(led), .an_n(an_n), .seg_n(seg_n), .dp_n(dp_n),
        .rvfi_valid(rvfi_valid), .rvfi_pc(rvfi_pc), .rvfi_insn(rvfi_insn),
        .rvfi_rd(rvfi_rd), .rvfi_rd_wdata(rvfi_rd_wdata), .rvfi_mem(rvfi_mem),
        .rvfi_mem_addr(rvfi_mem_addr), .rvfi_mem_wstrb(rvfi_mem_wstrb),
        .rvfi_mem_wdata(rvfi_mem_wdata), .rvfi_trap(rvfi_trap),
        .rvfi_trap_cause(rvfi_trap_cause), .rvfi_trap_epc(rvfi_trap_epc),
        .rvfi_trap_tval(rvfi_trap_tval), .perf_ev(perf_ev), .tohost(tohost));

    always #5 clk = ~clk;      // 100 MHz

    // ---- settings ------------------------------------------------------------
    reg [8*1024-1:0] hexfile, tracefile, uartlogfile, uartinfile, vcdfile;
    integer      trace_fd, uart_fd;
    reg          do_trace, do_uartlog;
    integer      max_cycles, uartin_at, sw2_at, btn_at, btn_len, vcd_start, vcd_len;
    reg [15:0]   sw2;
    reg [4:0]    btn_val;
    integer      i;

    // ---- counters ------------------------------------------------------------
    integer      cycles = 0;
    integer      retired = 0;
    integer      traps = 0;
    integer      ev_cnt [0:5];
    reg          done = 1'b0;
    reg          xerr = 1'b0;

    initial begin
        for (i = 0; i < 6; i = i + 1) ev_cnt[i] = 0;
        if (!$value$plusargs("max_cycles=%d", max_cycles)) max_cycles = 2000000;
        if (!$value$plusargs("uartin_at=%d", uartin_at))   uartin_at  = 100;
        if (!$value$plusargs("sw=%h", sw))                  sw         = 16'h0000;
        if (!$value$plusargs("sw2=%h", sw2))                sw2        = sw;
        if (!$value$plusargs("sw2_at=%d", sw2_at))          sw2_at     = -1;
        if (!$value$plusargs("btn=%h", btn_val))            btn_val    = 5'b00000;
        if (!$value$plusargs("btn_at=%d", btn_at))          btn_at     = -1;
        if (!$value$plusargs("btn_len=%d", btn_len))        btn_len    = 200;
        if (!$value$plusargs("vcd_start=%d", vcd_start))    vcd_start  = 0;
        if (!$value$plusargs("vcd_len=%d", vcd_len))        vcd_len    = 0;

        // Power-up state on the FPGA: block RAM and LUT RAM configure to zero.
        for (i = 0; i < RAM_WORDS; i = i + 1) dut.u_ram.ram_mem[i] = 32'h00000000;
        for (i = 0; i < 32; i = i + 1) dut.g_core.u_core.u_rf.rf_mem[i] = 32'h00000000;
        if ($value$plusargs("hex=%s", hexfile)) begin
            $readmemh(hexfile, dut.u_ram.ram_mem);
        end

        do_trace = $value$plusargs("trace=%s", tracefile);
        if (do_trace) trace_fd = $fopen(tracefile, "w");
        do_uartlog = $value$plusargs("uartlog=%s", uartlogfile);
        if (do_uartlog) uart_fd = $fopen(uartlogfile, "w");
        if ($value$plusargs("vcd=%s", vcdfile)) begin
            $dumpfile(vcdfile);
            $dumpvars(0, tb_soc);
            if (vcd_len > 0) $dumpoff;
        end

        repeat (20) @(posedge clk);
        rst <= 1'b0;
    end

    // ---- retirement trace (same text format as model/iss.py) ------------------
    always @(posedge clk) begin
        if (!rst && !done) begin
            cycles = cycles + 1;
            for (i = 0; i < 6; i = i + 1) begin
                if (perf_ev[i]) ev_cnt[i] = ev_cnt[i] + 1;
            end
            if (rvfi_valid) begin
                retired = retired + 1;
                if ((^rvfi_rd_wdata === 1'bx) || (^rvfi_pc === 1'bx) || (^rvfi_insn === 1'bx)) begin
                    xerr = 1'b1;
                end
                if (do_trace) begin
                    $fwrite(trace_fd, "R %08x %08x %0d%0d %08x ", rvfi_pc, rvfi_insn,
                            rvfi_rd / 10, rvfi_rd % 10, rvfi_rd_wdata);
                    if (rvfi_mem == 2'd1)
                        $fwrite(trace_fd, "L:%08x\n", rvfi_mem_addr);
                    else if (rvfi_mem == 2'd2)
                        $fwrite(trace_fd, "S:%08x:%x:%08x\n", rvfi_mem_addr, rvfi_mem_wstrb, rvfi_mem_wdata);
                    else
                        $fwrite(trace_fd, "-\n");
                end
            end
            if (rvfi_trap) begin
                traps = traps + 1;
                if (do_trace) begin
                    $fwrite(trace_fd, "T %08x %08x %08x\n", rvfi_trap_cause, rvfi_trap_epc, rvfi_trap_tval);
                end
            end
        end
    end

    // ---- UART receiver on the TX pin (pin-level check) -----------------------
    integer     ub;
    reg  [7:0]  uchar;
    integer     uart_count = 0;
    initial begin
        forever begin
            @(negedge uart_tx);
            if (!rst) begin
                repeat (UART_DIV / 2) @(posedge clk);
                if (uart_tx == 1'b0) begin
                    for (ub = 0; ub < 8; ub = ub + 1) begin
                        repeat (UART_DIV) @(posedge clk);
                        uchar[ub] = uart_tx;
                    end
                    repeat (UART_DIV) @(posedge clk);
                    if (uart_tx != 1'b1) begin
                        $display("[tb] UART framing error on TX pin");
                    end
                    uart_count = uart_count + 1;
                    $write("%c", uchar);
                    if (do_uartlog) $fwrite(uart_fd, "%c", uchar);
                end
            end
        end
    end

    // ---- UART transmitter onto the RX pin --------------------------------------
    // +uartin file: one 16-bit hex entry per line; < 0x100 is a byte to send,
    // 0x8000|n is a pause of n*1024 clocks (host/rvload.py --emit-stream).
    reg  [15:0] uin [0:131071];      // unwritten entries stay x (end marker)
    integer     uin_n, ui, uj;
    initial begin
        if ($value$plusargs("uartin=%s", uartinfile)) begin
            $readmemh(uartinfile, uin);
            uin_n = 0;
            while (uin_n < 131072 && uin[uin_n] !== 16'hxxxx) uin_n = uin_n + 1;
            wait (cycles >= uartin_at);
            for (ui = 0; ui < uin_n; ui = ui + 1) begin
                if (uin[ui][15]) begin
                    repeat ({17'd0, uin[ui][14:0]} * 1024) @(posedge clk);
                end else begin
                    uart_rx <= 1'b0;                               // start
                    repeat (UART_DIV) @(posedge clk);
                    for (uj = 0; uj < 8; uj = uj + 1) begin
                        uart_rx <= uin[ui][uj];
                        repeat (UART_DIV) @(posedge clk);
                    end
                    uart_rx <= 1'b1;                               // stop
                    repeat (UART_DIV) @(posedge clk);
                end
            end
        end
    end

    // ---- switches and buttons, waveform window ---------------------------------
    always @(posedge clk) begin
        if (vcd_len > 0 && cycles == vcd_start) $dumpon;
        if (vcd_len > 0 && cycles == vcd_start + vcd_len) $dumpoff;
        if (cycles == sw2_at) sw <= sw2;
        if (cycles == btn_at) btn <= btn_val;
        if (cycles == btn_at + btn_len) btn <= 5'b00000;
    end

    // ---- 7-segment display decoded from the pins ------------------------------
    reg [3:0]  seg_digit [0:7];
    integer    seg_last  [0:7];            // clock (tclk) at which the digit was last lit
    integer    tclk = 0;                   // free-running, keeps counting after the end
    integer    sd;
    function [3:0] seg_decode;
        input [6:0] s;          // active-high {g,f,e,d,c,b,a}
        begin
            case (s)
                7'b0111111: seg_decode = 4'h0;  7'b0000110: seg_decode = 4'h1;
                7'b1011011: seg_decode = 4'h2;  7'b1001111: seg_decode = 4'h3;
                7'b1100110: seg_decode = 4'h4;  7'b1101101: seg_decode = 4'h5;
                7'b1111101: seg_decode = 4'h6;  7'b0000111: seg_decode = 4'h7;
                7'b1111111: seg_decode = 4'h8;  7'b1101111: seg_decode = 4'h9;
                7'b1110111: seg_decode = 4'hA;  7'b1111100: seg_decode = 4'hB;
                7'b0111001: seg_decode = 4'hC;  7'b1011110: seg_decode = 4'hD;
                7'b1111001: seg_decode = 4'hE;  7'b1110001: seg_decode = 4'hF;
                default:    seg_decode = 4'hX;
            endcase
        end
    endfunction
    initial begin
        for (sd = 0; sd < 8; sd = sd + 1) begin
            seg_digit[sd] = 4'h0;
            seg_last[sd]  = -1;
        end
    end
    always @(posedge clk) begin
        tclk = tclk + 1;
        for (sd = 0; sd < 8; sd = sd + 1) begin
            if (an_n == ~(8'd1 << sd)) begin
                seg_digit[sd] <= seg_decode(~seg_n);
                seg_last[sd]  <= tclk;
            end
        end
    end

    // ---- interrupt latency: MTIP rising edge to trap entry ---------------------
    integer    irq_rise = -1;
    integer    irq_lat_min = 0, irq_lat_max = 0, irq_n = 0;
    reg        mtip_prev = 1'b0;
    always @(posedge clk) begin
        mtip_prev <= dut.irq_mtip;
        if (dut.irq_mtip && !mtip_prev) irq_rise = cycles;
        if (perf_ev[4] && irq_rise >= 0) begin
            if (irq_n == 0 || cycles - irq_rise < irq_lat_min) irq_lat_min = cycles - irq_rise;
            if (cycles - irq_rise > irq_lat_max) irq_lat_max = cycles - irq_rise;
            irq_n = irq_n + 1;
            irq_rise = -1;
        end
    end

    // ---- end of test ----------------------------------------------------------
    reg [8*8-1:0] seg_str;
    integer       settle;
    reg [8*1024-1:0]  sigfile;
    reg [31:0]    sig_begin, sig_end, sa;
    integer       sig_fd;
    always @(posedge clk) begin
        if (!rst && !done && ((tohost != 32'd0) || (cycles >= max_cycles) || xerr)) begin
            done <= 1'b1;
            // let the UART finish the byte in flight (the receiver above
            // needs the full stop bit)
            while (dut.u_uart.tx_busy) @(posedge clk);
            repeat (2 * UART_DIV) @(posedge clk);
            // optional settle time, e.g. so the 7-segment scan shows the final value
            if ($value$plusargs("settle=%d", settle)) repeat (settle) @(posedge clk);
            for (sd = 0; sd < 8; sd = sd + 1) begin
                // a digit counts as shown if it was lit during the last full scan
                seg_str[8*sd +: 8] = (seg_last[sd] >= 0 && tclk - seg_last[sd] <= 9 * SEG7_DIV)
                                     ? ((seg_digit[sd] < 10) ? (8'h30 + seg_digit[sd]) : (8'h37 + seg_digit[sd]))
                                     : 8'h2D;
            end
            $display("");
            $display("TB_RESULT status=%0s tohost=%08x cycles=%0d retired=%0d traps=%0d uart_bytes=%0d led=%04x seg7_reg=%08x seg7_pins=%0s ev_stall=%0d ev_flush=%0d ev_fwd_mem=%0d ev_fwd_wb=%0d ev_irq=%0d ev_trap=%0d",
                     xerr ? "XPROP" : ((tohost != 32'd0) ? "TOHOST" : "TIMEOUT"),
                     tohost, cycles, retired, traps, uart_count, led,
                     dut.u_seg7.value_q, seg_str,
                     ev_cnt[0], ev_cnt[1], ev_cnt[2], ev_cnt[3], ev_cnt[4], ev_cnt[5]);
            if ($value$plusargs("sigfile=%s", sigfile) && $value$plusargs("sig_begin=%h", sig_begin)
                && $value$plusargs("sig_end=%h", sig_end)) begin
                sig_fd = $fopen(sigfile, "w");
                for (sa = sig_begin; sa < sig_end; sa = sa + 4)
                    $fwrite(sig_fd, "%08x\n", dut.u_ram.ram_mem[(sa - RAM_BASE) >> 2]);
                $fclose(sig_fd);
            end
            $display("TB_IRQ count=%0d lat_min=%0d lat_max=%0d", irq_n, irq_lat_min, irq_lat_max);
            if (do_trace) $fclose(trace_fd);
            if (do_uartlog) $fclose(uart_fd);
            $finish;
        end
    end

endmodule
