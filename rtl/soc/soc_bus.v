// =============================================================================
// soc_bus.v - address decoder and read-data return for both core buses
// -----------------------------------------------------------------------------
// Purpose : Route the instruction bus to ROM/RAM port A and the data bus to
//           ROM/RAM port B or a peripheral, and report access faults.
// Behavior: Decoding is strict. A fetch outside ROM/RAM, a data access outside
//           ROM/RAM/IO, a store to ROM, an IO access that is not a 32-bit word
//           or hits an unimplemented register, all raise *_fault in the same
//           cycle, combinationally from the address. A faulting request
//           enables no slave, so it has no side effect.
//           Every slave answers one cycle after the request. The bus registers
//           which slave was selected and muxes its output in the next cycle.
//           Peripheral outputs are zero when not read, so they are OR-ed.
//           The instruction-side select only updates on a request, matching
//           the memories that hold their output while the core stalls.
// =============================================================================
`default_nettype none

module soc_bus #(
    parameter integer RAM_AW_P = 0          // 0 = RAM_AW from soc_params.vh
) (
    //== Ports
    input  wire        clk,
    input  wire        rst,
    // instruction bus from the core
    input  wire        ibus_req,
    // Waiver: only the region bits and bits 1:0 are decoded here; the word
    // offset goes straight from the core to the memories.
    /* verilator lint_off UNUSEDSIGNAL */
    input  wire [31:0] ibus_addr,
    /* verilator lint_on UNUSEDSIGNAL */
    output reg         ibus_fault,
    output wire [31:0] ibus_rdata,
    // data bus from the core
    input  wire        dbus_req,
    input  wire        dbus_we,
    input  wire [31:0] dbus_addr,
    input  wire [1:0]  dbus_size,
    output reg         dbus_fault,
    output wire [31:0] dbus_rdata,
    // memory ports
    output wire        rom_a_en,
    output wire        ram_a_en,
    output wire        rom_b_en,
    output wire        ram_b_en,
    input  wire [31:0] rom_a_rdata,
    input  wire [31:0] ram_a_rdata,
    input  wire [31:0] rom_b_rdata,
    input  wire [31:0] ram_b_rdata,
    // peripherals: one request line each, shared register index
    output wire [4:0]  per_req,       // {sysctrl, timer, seg7, gpio, uart}
    output wire [2:0]  per_idx,
    input  wire [31:0] per_rdata      // OR of all peripheral outputs
);

    //== Localparams/Wires
    `include "soc_params.vh"

    localparam integer RAMAW = (RAM_AW_P != 0) ? RAM_AW_P : RAM_AW;
    localparam [1:0] DS_ROM = 2'd0;
    localparam [1:0] DS_RAM = 2'd1;
    localparam [1:0] DS_IO  = 2'd2;

    wire        i_rom = (ibus_addr[31:ROM_AW] == ROM_BASE[31:ROM_AW]);
    wire        i_ram = (ibus_addr[31:RAMAW] == RAM_BASE[31:RAMAW]);
    wire        d_rom = (dbus_addr[31:ROM_AW] == ROM_BASE[31:ROM_AW]);
    wire        d_ram = (dbus_addr[31:RAMAW] == RAM_BASE[31:RAMAW]);
    wire        d_io  = (dbus_addr[31:IO_AW]  == IO_BASE[31:IO_AW]);
    wire [3:0]  pidx  = dbus_addr[11:8];
    wire [5:0]  ridx  = dbus_addr[7:2];
    reg         io_ok;
    reg  [4:0]  per_sel;
    reg         isel_ram_q, isel_ram_d;
    reg  [1:0]  dsel_q, dsel_d;

    //== Combinational Logic
    always @(*) begin
        ibus_fault = !(i_rom || i_ram) || (ibus_addr[1:0] != 2'b00);

        per_sel = 5'b00000;
        io_ok   = 1'b0;
        case (pidx)
            PIDX_UART:    begin per_sel = 5'b00001; io_ok = (ridx < NREGS_UART);    end
            PIDX_GPIO:    begin per_sel = 5'b00010; io_ok = (ridx < NREGS_GPIO);    end
            PIDX_SEG7:    begin per_sel = 5'b00100; io_ok = (ridx < NREGS_SEG7);    end
            PIDX_TIMER:   begin per_sel = 5'b01000; io_ok = (ridx < NREGS_TIMER);   end
            PIDX_SYSCTRL: begin per_sel = 5'b10000; io_ok = (ridx < NREGS_SYSCTRL); end
            default:      begin per_sel = 5'b00000; io_ok = 1'b0;                   end
        endcase
        io_ok = io_ok && d_io && (dbus_size == 2'd2) && (dbus_addr[1:0] == 2'b00);

        dbus_fault = !( d_ram || (d_rom && !dbus_we) || io_ok );

        isel_ram_d = ibus_req ? i_ram : isel_ram_q;
        dsel_d     = dsel_q;
        if (dbus_req) begin
            dsel_d = d_ram ? DS_RAM : (d_rom ? DS_ROM : DS_IO);
        end
    end

    assign rom_a_en = ibus_req && i_rom;
    assign ram_a_en = ibus_req && i_ram;
    assign rom_b_en = dbus_req && !dbus_fault && d_rom;
    assign ram_b_en = dbus_req && !dbus_fault && d_ram;
    assign per_req  = (dbus_req && !dbus_fault && d_io) ? per_sel : 5'b00000;
    assign per_idx  = ridx[2:0];

    assign ibus_rdata = isel_ram_q ? ram_a_rdata : rom_a_rdata;
    assign dbus_rdata = (dsel_q == DS_RAM) ? ram_b_rdata :
                        (dsel_q == DS_ROM) ? rom_b_rdata : per_rdata;

    //== Sequential Logic
    always @(posedge clk) begin
        if (rst) begin
            isel_ram_q <= 1'b0;
            dsel_q     <= DS_ROM;
        end else begin
            isel_ram_q <= isel_ram_d;
            dsel_q     <= dsel_d;
        end
    end

endmodule

`default_nettype wire
