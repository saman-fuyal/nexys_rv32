# =============================================================================
# program.tcl - load a bitstream into the Nexys A7 over USB-JTAG (volatile)
# -----------------------------------------------------------------------------
# Purpose : Program the FPGA without the GUI. The design is lost at power-off;
#           use flash.tcl to make it permanent.
# Usage   : vivado -mode batch -source fpga/scripts/program.tcl -tclargs [pipe|mc]
# Notes   : The JTAG connection (open_hw, retried get_hw_targets,
#           current_hw_target) is in hw_common.tcl. The board must be on,
#           the PROG/UART micro-USB cable connected, and the cable driver
#           installed (Vivado installer, or data\xicom\cable_drivers\nt64\
#           install_drivers_wrapper.bat as Administrator).
# =============================================================================
set here [file normalize [file dirname [info script]]]
set root [file normalize "$here/../.."]
source "$here/params_gen.tcl"
set core $NRV_CORE
if {[llength $argv] > 0} { set core [lindex $argv 0] }
set bit "$root/fpga/build/$core/nexys_rv32_$core.bit"
if {![file exists $bit]} { error "no bitstream $bit - run fpga\\build.bat first" }

source "$here/hw_common.tcl"
set dev [nrv_open_board]
set_property PROBES.FILE {} $dev
set_property FULL_PROBES.FILE {} $dev
set_property PROGRAM.FILE $bit $dev
program_hw_devices $dev
refresh_hw_device $dev
puts "PROGRAM DONE: $bit -> $dev (DONE LED should be on)"
nrv_close_board
