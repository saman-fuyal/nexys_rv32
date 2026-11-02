#!/usr/bin/env python3
# =============================================================================
# board_model.py - software copy of the board for testing host tools
# -----------------------------------------------------------------------------
# Purpose : Let host/rvload.py talk to "a board" before the real one exists:
#           the golden ISS runs the real boot ROM image, and the UART is a
#           pair of byte queues.
# Behavior: BoardModel.write(data) queues bytes on the UART receiver;
#           read(n, budget) runs the ISS until n bytes have been transmitted
#           or the instruction budget is spent. Timing is not modelled (the
#           ISS UART never reports busy), so this checks protocol and data,
#           not baud-rate behaviour; the RTL bootloader test in run_sim.py
#           checks the same exchange at the real baud rate on the pins.
#           As a script it serves a pseudo-terminal (Linux/WSL) so the real
#           serial-port code path of rvload.py can be exercised:
#               py model/board_model.py --pty
# =============================================================================
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import iss as iss_mod        # noqa: E402
import params as params_mod  # noqa: E402

DEFAULT_BOOT = os.path.join(HERE, "..", "sw", "build", "boot", "boot.elf")
if not os.path.exists(DEFAULT_BOOT):   # fresh unzip without a compiler: use the shipped copy
    DEFAULT_BOOT = os.path.join(HERE, "..", "sw", "prebuilt", "boot.elf")


class BoardModel(object):
    def __init__(self, boot_elf=DEFAULT_BOOT, switches=0):
        P = params_mod.load()
        self.iss = iss_mod.Iss(P)
        iss_mod.load_program(self.iss, boot_elf)
        self.iss.pc = P.reset_vector
        self.iss.soc.switches = switches
        self.tx = bytearray()
        self.iss.soc.uart.on_tx = self.tx.append
        self.steps = 0

    def write(self, data):
        self.iss.soc.uart.rx.extend(bytearray(data))

    def step(self, n):
        for _ in range(n):
            self.iss.step()
        self.steps += n

    def read(self, n, budget=5000000):
        """Run until n bytes were transmitted (or budget instructions)."""
        spent = 0
        while len(self.tx) < n and spent < budget:
            self.step(500)
            spent += 500
        out = bytes(self.tx[:n])
        del self.tx[:n]
        return out

    def drain(self, budget=200000):
        """Run for a while and return whatever was transmitted."""
        self.step(budget)
        out = bytes(self.tx)
        self.tx.clear()
        return out

    @property
    def tohost(self):
        return self.iss.soc.tohost


def serve_pty():
    import pty
    import select
    import tty
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    print(os.ttyname(slave), flush=True)
    b = BoardModel()
    while True:
        r, _, _ = select.select([master], [], [], 0)
        if r:
            b.write(os.read(master, 4096))
        b.step(200)
        if b.tx:
            os.write(master, bytes(b.tx))
            b.tx.clear()


if __name__ == "__main__":
    if "--pty" in sys.argv:
        serve_pty()
    else:
        print(__doc__ if __doc__ else "use --pty")
