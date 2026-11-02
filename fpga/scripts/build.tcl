# =============================================================================
# build.tcl - Vivado 2018.2 non-project build: synthesis to bitstream
# -----------------------------------------------------------------------------
# Purpose : Build fpga_top for the Nexys A7-50T with one command and keep
#           every report the write-up needs.
# Usage   : vivado -mode batch -source fpga/scripts/build.tcl -tclargs [pipe|mc]
#           (fpga\build.bat wraps this; default core from params.json)
# Output  : fpga/build/<core>/
#             nexys_rv32_<core>.bit       bitstream
#             post_route.dcp              checkpoint (open in the Vivado GUI)
#             utilization.rpt, utilization_hier.rpt, timing_summary.rpt,
#             timing_paths.rpt (10 worst setup paths), drc.rpt, power.rpt,
#             clock_utilization.rpt, methodology.rpt
#           results/vivado_<core>.json    WNS, Fmax, resources (parsed by
#                                         tools/collect_results.py)
# Notes   : Non-project mode avoids project files and works the same on any
#           Vivado version that supports these commands; every command used
#           here exists in 2018.2. Paths must not contain spaces.
# =============================================================================
set here [file normalize [file dirname [info script]]]
set root [file normalize "$here/../.."]
source "$here/params_gen.tcl"

set core $NRV_CORE
if {[llength $argv] > 0} { set core [lindex $argv 0] }
if {$core ne "pipe" && $core ne "mc"} { error "core must be pipe or mc" }
set core_pipe [expr {$core eq "pipe" ? 1 : 0}]
set out "$root/fpga/build/$core"
file mkdir $out
file mkdir "$root/results"

# ---- sources ------------------------------------------------------------------
foreach f [concat [glob $root/rtl/core/*.v] [glob $root/rtl/soc/*.v] [glob $root/rtl/periph/*.v] \
               [list $root/rtl/gen/bootrom.v $root/fpga/rtl/fpga_top.v]] {
    read_verilog $f
}
read_xdc "$root/fpga/constraints/nexys_a7_50t.xdc"
read_xdc "$root/fpga/constraints/clock_gen.xdc"

# ---- synthesis ------------------------------------------------------------------
synth_design -top fpga_top -part $NRV_PART -generic CORE_PIPE=$core_pipe \
    -include_dirs [list "$root/rtl/core" "$root/rtl/gen"] -flatten_hierarchy rebuilt
write_checkpoint -force "$out/post_synth.dcp"
report_utilization -file "$out/utilization_synth.rpt"
report_timing_summary -file "$out/timing_synth.rpt"

# ---- implementation ---------------------------------------------------------------
opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force "$out/post_route.dcp"

# ---- reports ------------------------------------------------------------------------
report_utilization -file "$out/utilization.rpt"
report_utilization -hierarchical -file "$out/utilization_hier.rpt"
report_timing_summary -max_paths 10 -file "$out/timing_summary.rpt"
report_timing -max_paths 10 -nworst 1 -sort_by slack -file "$out/timing_paths.rpt"
report_clock_utilization -file "$out/clock_utilization.rpt"
report_drc -file "$out/drc.rpt"
report_methodology -file "$out/methodology.rpt"
report_power -file "$out/power.rpt"

# ---- key numbers as JSON -------------------------------------------------------------
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]
set wpath  [get_timing_paths -max_paths 1 -nworst 1 -setup]
set period [get_property PERIOD [get_clocks [get_property ENDPOINT_CLOCK $wpath]]]
set fmax [expr {1000.0 / ($period - $wns)}]
proc count {filter} { return [llength [get_cells -hier -filter $filter]] }
# LUT, FF and latch counts as the utilization report states them
set urpt [report_utilization -return_string]
proc urow {rpt name} {
    if {[regexp "\\|\\s+$name\\s+\\|\\s+(\\d+)" $rpt -> v]} { return $v }
    return -1
}
set lut    [urow $urpt {Slice LUTs}]
set ff     [urow $urpt {Register as Flip Flop}]
set latch  [urow $urpt {Register as Latch}]
set ramb36 [count {REF_NAME == RAMB36E1}]
set ramb18 [count {REF_NAME == RAMB18E1}]
set lutram [count {PRIMITIVE_GROUP == DMEM}]
set dsp    [count {REF_NAME == DSP48E1}]
set crit   [get_property NAME [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set startp [get_property NAME [get_property STARTPOINT_PIN [get_timing_paths -max_paths 1 -nworst 1 -setup]]]
set endp   [get_property NAME [get_property ENDPOINT_PIN [get_timing_paths -max_paths 1 -nworst 1 -setup]]]
set fh [open "$root/results/vivado_$core.json" w]
puts $fh "\{"
puts $fh "  \"tool\": \"[version -short]\","
puts $fh "  \"core\": \"$core\","
puts $fh "  \"part\": \"$NRV_PART\","
puts $fh "  \"clock_period_ns\": $period,"
puts $fh "  \"wns_ns\": $wns,"
puts $fh "  \"whs_ns\": $whs,"
puts $fh "  \"fmax_mhz\": [format %.1f $fmax],"
puts $fh "  \"lut\": $lut, \"lutram_cells\": $lutram, \"ff\": $ff, \"latch\": $latch,"
puts $fh "  \"ramb36\": $ramb36, \"ramb18\": $ramb18, \"dsp\": $dsp,"
puts $fh "  \"critical_start\": \"$startp\","
puts $fh "  \"critical_end\": \"$endp\""
puts $fh "\}"
close $fh

# ---- bitstream -------------------------------------------------------------------------
write_bitstream -force "$out/nexys_rv32_$core.bit"
puts "BUILD DONE core=$core WNS=$wns ns Fmax~[format %.1f $fmax] MHz LUT=$lut FF=$ff RAMB36=$ramb36"
if {$wns < 0} {
    puts "WARNING: timing not met at $NRV_CPU_HZ Hz. Lower cpu_hz in params.json (COMMANDS.md, 'FPGA build')."
}
