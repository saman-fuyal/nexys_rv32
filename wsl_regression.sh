#!/usr/bin/env bash
# =============================================================================
# wsl_regression.sh - full regression in WSL (Verilator, Yosys, Icarus, GCC)
# -----------------------------------------------------------------------------
# Purpose : The long tests and the Verilator lint / Yosys latch checks need
#           Linux tools. This puts the OSS CAD Suite and the xPack GCC (both
#           unpacked in your Linux home folder, COMMANDS.md) on PATH for
#           this run only, so nothing in ~/.bashrc changes and LibreLane's
#           nix-shell is not affected, then runs sim/run_sim.py.
# Usage   : bash wsl_regression.sh [run_sim.py options]   (default --jobs 4)
#           --jobs 4 suits a WSL limited to 5 GB of RAM; use 2 if it swaps.
# =============================================================================
set -e
cd "$(dirname "$0")"
d="$HOME/xpack-riscv-none-elf-gcc-14.2.0-3/bin"
if [ ! -d "$d" ]; then
    echo "missing $d (see COMMANDS.md, 'Full regression in WSL')"
    exit 1
fi
PATH="$d:$PATH"
# Verilator, Yosys and Icarus: from the OSS CAD Suite if unpacked, else Ubuntu's packages
if [ -d "$HOME/oss-cad-suite/bin" ]; then PATH="$HOME/oss-cad-suite/bin:$PATH"; fi
export PATH
for t in verilator yosys iverilog riscv-none-elf-gcc make g++ python3; do
    command -v "$t" >/dev/null || { echo "missing tool: $t"; exit 1; }
done
if [ $# -eq 0 ]; then set -- --jobs 4; fi
exec python3 sim/run_sim.py "$@"
