# Commands

Every command used in this project, in the order you would run them. Windows commands go in
Command Prompt, opened in the project folder (the path must not contain spaces, which Vivado 2018.2
needs):

```bat
cd /d C:\path\to\nexys_rv32
```

The board shows up as a USB serial port. The examples use COM6; check Device Manager, under Ports, for
yours, or use `--port auto` and let the tools find it.

## 1. One-time setup on Windows

```bat
py -m pip install matplotlib pyserial
```
Python packages for the figures and the board tools (Python 3.10 or newer).

Icarus Verilog 12 is expected in `C:\iverilog` (`run_sim.bat` adds it to the PATH by itself). Vivado
2018.2 is expected in `C:\Xilinx\Vivado\2018.2`; for another folder, `set VIVADO_DIR=D:\Xilinx\Vivado\2018.2`
first.

The xPack RISC-V GCC 14.2.0-3 is needed for the regression and to rebuild the software, not to run the
board (`sw\prebuilt\` has every program ready-made). Download
`xpack-riscv-none-elf-gcc-14.2.0-3-win32-x64.zip` from
https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v14.2.0-3, extract it to
`C:\tools`, and add its `bin` folder to your user PATH:

```bat
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ';C:\tools\xpack-riscv-none-elf-gcc-14.2.0-3\bin', 'User')"
```
Open a new Command Prompt afterwards.

```bat
riscv-none-elf-gcc --version
C:\iverilog\bin\iverilog -V
```
Confirms GCC 14.2.0 and Icarus 12.

```bat
preflight.bat
```
Checks Python, the packages, the compiler, Icarus, Vivado, the prebuilt programs, the bitstreams and the
board's serial port, and says how to fix each gap. It changes nothing.

## 2. Model and simulation

```bat
py model\iss.py sw\prebuilt\hello.elf
```
Runs a program on the golden model (the Python instruction-set simulator) and prints its UART output.

```bat
run_sim.bat --quick
```
Quick regression on Icarus: static checks, unit tests, directed tests, riscv-tests, riscv-arch-test, a
few random seeds and the self-test programs, on both cores. Verilator lint and the Yosys latch check show
N/A on Windows. Ends with ALL PASS after about 5 to 10 minutes and writes `results\regression_quick.md`.

```bat
run_sim.bat --quick --core pipe --only arch
```
Runs part of it: one core, and only the tests whose name matches the regular expression after `--only`.

```bat
run_sim.bat --list
```
Lists every test without running anything.

```bat
py tools\check_rules.py
```
Checks the RTL coding rules (synthesizable code, no latches, separate sequential and combinational
logic, file sections).

```bat
py tools\check_tcl.py
```
Checks the Vivado Tcl scripts without Vivado.

```bat
sw\build.bat
sw\build.bat hello
```
Builds the boot ROM and every C program into `sw\build\`, or one program.

```bat
py tools\make_prebuilt.py
```
Rebuilds `sw\prebuilt\` (the board programs and the 158 self-test programs). The regression checks
that it equals a fresh build.

```bat
py tools\gen_all.py
```
Regenerates every file that comes from `params.json` (Verilog and C headers, linker scripts, clock
constraint, memory map tables). Run it after any change to `params.json`, then `sw\build.bat` and
`py tools\make_prebuilt.py` so the boot ROM and the programs follow.

## 3. Full regression in WSL or Linux

The long tests (C programs, benchmarks, the bootloader at the real baud rate, 100 random seeds per core,
all self-test programs), Verilator lint and the Yosys latch proof need Linux tools. One-time setup in
Ubuntu:

```bash
sudo apt update
sudo apt install -y make g++ verilator yosys iverilog clang lld llvm python3-matplotlib python3-serial wget
cd ~ && wget https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v14.2.0-3/xpack-riscv-none-elf-gcc-14.2.0-3-linux-x64.tar.gz
tar xzf xpack-riscv-none-elf-gcc-14.2.0-3-linux-x64.tar.gz
```
Installs the simulators, Yosys, clang (the second compiler some tests use) and the xPack GCC in
`~/xpack-riscv-none-elf-gcc-14.2.0-3`. If `~/oss-cad-suite/bin` exists, `wsl_regression.sh` uses its
Verilator and Yosys instead of Ubuntu's.

```bash
rm -rf ~/nexys_rv32 && cp -r /mnt/c/path/to/nexys_rv32 ~/nexys_rv32
cd ~/nexys_rv32 && bash wsl_regression.sh --jobs 4
```
Copies the project into Linux and runs the full regression. It ends with
`854 checks/runs: 854 passed, ... 0 failed` and ALL PASS, after 10 to 25 minutes. Use `--jobs 2` if WSL
runs short of memory.

```bash
cp ~/nexys_rv32/results/regression.json ~/nexys_rv32/results/regression.md /mnt/c/path/to/nexys_rv32/results/
```
Copies the result back to Windows.

```bash
python3 sim/run_sim.py --coverage
```
A Verilator coverage build of the regression, then line, toggle and functional coverage in
`results/coverage.md`.

```bash
python3 tools/mutation_test.py
```
Injects 16 realistic bugs into copies of the RTL, one at a time, and checks that the regression catches
each one: `results/mutation.md`.

```bash
python3 tools/test_host.py
```
Runs the board tools through a real serial device against the software copy of the board (Linux only;
it is part of the full regression).

## 4. FPGA build and programming

```bat
fpga\build.bat pipe
fpga\build.bat mc
```
Synthesis, place and route, reports and bitstream for the pipelined and the multi-cycle core, without
the Vivado GUI (10 to 20 minutes each). Each ends with
`BUILD DONE core=<core> WNS=<n> ns Fmax~<n> MHz LUT=<n> FF=<n> RAMB36=<n>`. WNS must be 0 or more.
Output goes to `fpga\build\<core>\` and `results\vivado_<core>.json`. If WNS is negative, lower
`clock.cpu_hz` in `params.json` (50000000 and 75000000 are supported), then run `py tools\gen_all.py`,
`sw\build.bat`, `py tools\make_prebuilt.py` and the build again.

```bat
fpga\program.bat pipe
```
Loads the bitstream into the FPGA over USB (JP1 on JTAG). It ends with `PROGRAM DONE`, the DONE LED
lights and the display shows `B0070001`. It is lost at power-off.

```bat
fpga\flash.bat pipe
```
Writes the design into the board's Quad-SPI flash. With JP1 on QSPI the board then starts the
bootloader by itself at power-on.

```bat
call fpga\vivado_env.bat
py sim\run_sim.py --sim xsim --quick --core pipe
```
Optional: the quick regression on Vivado's own simulator.

## 5. Board tests

Keep SW15 down. Press CPU_RESET (the red button) before each load: every program except the self-test
ones ends by stopping, and reset returns to the bootloader.

```bat
board_day.bat pipe
```
Everything below in one go: preflight, programming, hello, the benchmarks, the self-test and the
results update. It stops at the first problem.

```bat
py host\rvload.py sw\prebuilt\hello.elf --port COM6 --term --timeout 5
```
Loads a program, verifies it and shows its output: `Hello from nexys_rv32!`, the core and
`clock : 50000000 Hz`. The display shows `00C0FFEE`.

```bat
py host\rvload.py sw\prebuilt\switches_leds.elf --port auto --term
py host\rvload.py sw\prebuilt\seg7_counter.elf --port auto --term
py host\rvload.py sw\prebuilt\timer_irq.elf --port auto --term
```
The interactive programs. The LEDs follow the switches; the display counts (BTNC pause, BTNU reset,
BTNL down, BTNR up, BTND stop); LED0 blinks at 1 Hz from timer interrupts. Ctrl+C leaves the terminal.

```bat
py host\board_bench.py --port COM6
```
Runs hello, timer_irq, Dhrystone (1,000,000 runs) and CoreMark (1500 iterations) and saves
`results\board_<core>_<name>.json`. It ends with `board_bench: ALL OK`.

```bat
py host\board_hil.py --port COM6
```
On-board self-test: 100 random programs and 58 riscv-tests run one after another, and every byte each
one prints must equal the golden model's output. It ends with
`board_hil (<core> core): 158 of 158 programs identical to the model` after about 5 minutes.

```bat
fpga\program.bat mc
py host\board_bench.py --port COM6
py host\board_hil.py --port COM6
```
The same measurements for the multi-cycle core.

```bat
py host\rvload.py sw\prebuilt\hello.elf --port sim --term --timeout 10
py host\board_hil.py --port sim --seeds 2 --no-rvtests
```
The same tools against a software copy of the board (the golden model running the real boot ROM), no
board needed.

## 6. Results and figures

```bat
update_docs.bat
```
Collects every result file into `results\summary.json` and `docs\RESULTS.md`, redraws the figures in
`docs\figures\` and rewrites `README.md`.

```bat
py tools\check_diagrams.py
```
Checks that the block, flow and state diagrams have no diagonal or crossing lines and no text touching a
line.

```bat
py tools\collect_results.py --waves
```
Also re-runs two short simulations with waveform output for the waveform figures (needs the quick
regression first).
