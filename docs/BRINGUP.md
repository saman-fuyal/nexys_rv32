# Board bring-up checklist (Nexys A7-50T)

Tick each line in order. Stop at the first line that does not match and note what you saw.
`board_day.bat` runs the main steps in one go (preflight, program, hello, measurements, on-board
self-test, results). This list is the detailed version, with what to look for on the board.

## Before power

- [ ] Board is a **Nexys A7-50T**: FPGA XC7A50T in the industrial, low-power version (Vivado part
      `xc7a50ticsg324-1L`, as in Digilent's board files). The bitstream will not load on a -100T.
- [ ] JP1 (mode) on **JTAG**. JP3 (power source, next to the power jack) on **USB**.
- [ ] Micro-USB cable in **J6 PROG/UART** (the port next to the power switch), PC end in a USB port.
- [ ] All 16 slide switches down. SW15 down matters: up means "run the program already in RAM".

## Power and drivers

- [ ] Power switch on: the red power LED (LD22) lights. A factory demo may run; that is fine.
- [ ] Windows Device Manager shows **USB Serial Port (COMn)** under Ports. The commands below use COM6;
      use your number instead, or `--port auto`.
- [ ] If not: run `C:\Xilinx\Vivado\2018.2\data\xicom\cable_drivers\nt64\install_drivers_wrapper.bat`
      as Administrator, unplug and replug.

## Program the FPGA

- [ ] `fpga\build\pipe\nexys_rv32_pipe.bit` exists (`fpga\build.bat pipe`, see COMMANDS.md).
- [ ] `fpga\program.bat pipe` ends with `PROGRAM DONE`. The FPGA's **DONE** LED (marked DONE on the
      board) lights.
- [ ] 7-segment display shows **B0070001** (bootloader version 1). LED15 is on.
- [ ] Open a terminal (PuTTY or `py -m serial.tools.miniterm COM6 115200`), press **CPU_RESET**:
      > `nexys_rv32 boot v1, RAM 80000000+00010000, waiting for rvload`
      Close the terminal again (only one program can own the COM port).

## First program

- [ ] `py host\rvload.py sw\prebuilt\hello.elf --port COM6 --term --timeout 5`
      (`--port auto` also works: it tries each COM port and uses the one where the bootloader answers)
      > `bootloader v1, RAM 0x80000000 + 65536, loadable up to 0x8000ff00`
      > `loading 4xxx / 4xxx bytes`, `verify ok`, `running at 0x80000000`
      > `Hello from nexys_rv32!`, `core : 5-stage pipeline`, `clock : 50000000 Hz`
- [ ] 7-segment shows **00C0FFEE**, LED0 on.

## Interactive programs (press CPU_RESET before each load)

- [ ] `switches_leds`: each switch lights the LED above it; the display shows the switch value in hex;
      the terminal prints `SW=xxxx` on each change; BTND (down) ends it.
- [ ] `seg7_counter`: counts up in decimal 10 times a second. BTNC pauses, BTNU resets, BTNL counts down,
      BTNR up, BTND prints the count and stops. Each press acts once (debounce).
- [ ] `timer_irq`: LED0 blinks at 1 Hz (toggles every 500 interrupts at 1 kHz); terminal prints
      `ticks=1000`, `ticks=2000`, ... once a second.

## Measurements

- [ ] `py host\board_bench.py --port COM6` > `board_bench: ALL OK`, files `results\board_*.json`.
      Without a RISC-V GCC it uses `sw\prebuilt\*_board.elf` by itself.
- [ ] CoreMark line `Correct operation validated.` and run time at least 10 s (CoreMark run rule).
- [ ] Board Dhrystone and CoreMark per-MHz numbers equal the simulation numbers in
      `docs\RESULTS.md` within 1 % (no caches, so cycle counts should match exactly for the same binary).

## On-board self-test

- [ ] `py host\board_hil.py --port COM6`, press **CPU_RESET** when asked (once; every program returns
      to the bootloader by itself).
      > `core in the bitstream: pipe; 158 programs to run`
      > one `PASS` line per program: `rand_0001` ... `rand_0100` (registers and 2 KB of memory, about 4.9 KB
        of text each) and `rv_rv32ui-*`, `rv_rv32mi-*` (result code)
      > `board_hil (pipe core): 158 of 158 programs identical to the model, ...; saved results\board_pipe_hil.json`
- [ ] Takes about 10 minutes. A `FAIL` line shows the first differing byte and both texts; keep
      `results\board_pipe_hil.log`.
- [ ] `update_docs.bat` rebuilds the results, figures and README.

## Multi-cycle core

- [ ] `fpga\program.bat mc`, repeat "First program" (`core : multi-cycle`), `board_bench.py` and
      `board_hil.py` (it reports `core in the bitstream: mc` and writes `results\board_mc_hil.json`).

## Persistent boot (optional)

- [ ] `fpga\flash.bat pipe` > `FLASH DONE`. Power off, JP1 to **QSPI**, power on: B0070001 appears
      within about a second, without the PC.

## If something fails

| Symptom | Likely cause | Check |
|---|---|---|
| program.bat: no xc7a50t found | cable or driver | Device Manager shows "Digilent USB Device"; reinstall cable drivers |
| Display blank after programming | bitstream for the wrong part, or reset held | part `xc7a50ticsg324-1L` in `params.json`; CPU_RESET not stuck |
| rvload: no answer to ping | wrong COM port, terminal still open, or SW15 up | check the COM number in Device Manager or use `--port auto`; close PuTTY; SW15 down, press CPU_RESET |
| Garbage characters | baud mismatch | terminal at 115200 8N1; `cpu_hz` in params.json matches the build |
| CRC errors while loading | USB hub or long cable | plug into a port on the PC directly; rvload retries are not automatic, re-run |
| A program prints `*** TRAP` | a software bug or a core bug | note mcause/mepc; the same ELF must show the same trap in `py model/iss.py <elf>` |
| preflight: MISSING lines | a tool or package not installed | follow the arrow under each MISSING line, run `preflight.bat` again |
| program.bat: `settings64.bat not found` | Vivado elsewhere | `set VIVADO_DIR=D:\Xilinx\Vivado\2018.2` (your folder), then retry |
| build.bat ends with WNS < 0 | the design misses the clock in params.json | lower `cpu_hz` in `params.json` (COMMANDS.md, "FPGA build"); the first path in `fpga\build\pipe\timing_paths.rpt` shows where |
| rvload: `cannot open (PermissionError)` | another program holds the port | close PuTTY / miniterm / Vivado serial terminal |
| board_bench: `no compiler and no ...prebuilt...` | files missing | clone or download again; `sw\prebuilt` must hold 11 `.elf` files |
| board_hil: `the probe program did not report the core` | board not in the bootloader | press CPU_RESET, SW15 down, run again |
| board_hil: `incomplete output (timeout)` | a program hung or the UART lost bytes | run again with `--seeds 5`; if the same program fails, keep `results\board_*_hil.log` |
| board_hil: `differs at byte ...` | the board computed something the model did not | keep `results\board_*_hil.log` and the program `sw\prebuilt\hil\<name>.elf`; it can be replayed in simulation |

## If Vivado 2018.2 fails

Vivado 2018.2 officially supports Windows 10 builds 1709 and 1803. Both builds in this project ran on
Windows 11, so this section is only a fallback.

1. Installer stops or crashes: run `xsetup.exe` as Administrator. If it still fails, install it inside a
   Windows 10 virtual machine and pass the board's USB device through to it for programming.
2. If that is not possible, a newer Vivado release can build the design: the scripts use only
   non-project Tcl commands and pick `open_hw` or `open_hw_manager`, whichever exists. Note the version
   you used in the paper, because timing and resource numbers differ between releases.
