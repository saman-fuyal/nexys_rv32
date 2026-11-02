# =============================================================================
# flash.tcl - write the bitstream into the on-board Quad-SPI flash
# -----------------------------------------------------------------------------
# Purpose : Make the design start at power-up (with jumper JP1 on QSPI).
# Usage   : vivado -mode batch -source fpga/scripts/flash.tcl -tclargs [pipe|mc]
# Behavior: Builds an .mcs image for the 16 MB Spansion S25FL128S (the part
#           the Nexys A7 reference manual lists), programs it through the
#           FPGA's JTAG-to-SPI bridge, verifies, then reboots the FPGA from
#           flash. The flash part name below is Vivado's name for that device;
#           if your board carries a different flash revision, Vivado's
#           "Add Configuration Memory Device" dialog lists the right one.
# =============================================================================
set here [file normalize [file dirname [info script]]]
set root [file normalize "$here/../.."]
source "$here/params_gen.tcl"
set core $NRV_CORE
if {[llength $argv] > 0} { set core [lindex $argv 0] }
set bit "$root/fpga/build/$core/nexys_rv32_$core.bit"
set mcs "$root/fpga/build/$core/nexys_rv32_$core.mcs"
if {![file exists $bit]} { error "no bitstream $bit - run fpga\\build.bat first" }

write_cfgmem -force -format mcs -size 16 -interface SPIx4 -loadbit "up 0x00000000 $bit" -file $mcs

source "$here/hw_common.tcl"
set dev [nrv_open_board]
set part [lindex [get_cfgmem_parts {s25fl128sxxxxxx0-spi-x1_x2_x4}] 0]
if {$part eq ""} { error "flash part s25fl128sxxxxxx0-spi-x1_x2_x4 not known to this Vivado" }
create_hw_cfgmem -hw_device $dev -mem_dev $part
set mem [get_property PROGRAM.HW_CFGMEM $dev]
set_property PROGRAM.ADDRESS_RANGE {use_file} $mem
set_property PROGRAM.FILES [list $mcs] $mem
set_property PROGRAM.UNUSED_PIN_TERMINATION {pull-none} $mem
set_property PROGRAM.BLANK_CHECK 0 $mem
set_property PROGRAM.ERASE 1 $mem
set_property PROGRAM.CFG_PROGRAM 1 $mem
set_property PROGRAM.VERIFY 1 $mem
create_hw_bitstream -hw_device $dev [get_property PROGRAM.HW_CFGMEM_BITFILE $dev]
program_hw_devices $dev
refresh_hw_device $dev
program_hw_cfgmem -hw_cfgmem $mem
boot_hw_device $dev
puts "FLASH DONE: $mcs (set JP1 to QSPI to boot from flash at power-up)"
nrv_close_board
