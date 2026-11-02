# =============================================================================
# hw_common.tcl - open the JTAG connection to the Nexys A7 (Vivado 2018.2)
# -----------------------------------------------------------------------------
# Purpose : Shared by program.tcl and flash.tcl. Written for Vivado 2018.2,
#           with the fixes found on this board in the earlier audio-filter
#           project:
#             - 2018.2 calls the hardware manager 'open_hw' (later releases:
#               open_hw_manager); whichever exists is used.
#             - get_hw_targets can come back empty for a second or two after
#               connect_hw_server, so it is retried.
#             - the target is selected explicitly with current_hw_target
#               before open_hw_target.
# Usage   : source hw_common.tcl ; set dev [nrv_open_board] ; ... ; nrv_close_board
# =============================================================================

proc nrv_open_board {} {
    if {[llength [info commands open_hw_manager]]} { open_hw_manager } else { open_hw }
    connect_hw_server
    set tgt ""
    for {set i 0} {$i < 10} {incr i} {
        set tl [get_hw_targets -quiet]
        if {[llength $tl] > 0} {
            set tgt [lindex $tl 0]
            break
        }
        puts "waiting for the JTAG cable (try [expr {$i + 1}] of 10) ..."
        after 1000
        catch { refresh_hw_server }
    }
    if {$tgt eq ""} {
        error "no JTAG target: board switched on (SW16)? micro-USB in J6 PROG/UART? cable driver installed?"
    }
    current_hw_target $tgt
    open_hw_target
    set dev [lindex [get_hw_devices -quiet xc7a50t*] 0]
    if {$dev eq ""} {
        error "no xc7a50t on the JTAG chain (found: [get_hw_devices -quiet]); is this a Nexys A7-50T?"
    }
    current_hw_device $dev
    refresh_hw_device -update_hw_probes false $dev
    puts "JTAG: target $tgt, device $dev"
    return $dev
}

proc nrv_close_board {} {
    catch { close_hw_target }
    catch { disconnect_hw_server }
    if {[llength [info commands close_hw_manager]]} { catch { close_hw_manager } } else { catch { close_hw } }
}
