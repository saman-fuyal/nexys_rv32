#!/usr/bin/env python3
# =============================================================================
# rvload.py - load and run a program on the board through the UART bootloader
# -----------------------------------------------------------------------------
# Purpose : The PC side of sw/boot/boot.c. Load a new C program over the
#           Nexys A7 USB-UART without rebuilding or reprogramming the FPGA.
# Behavior: 1. ping: send 'P', skip any banner text, expect "KRVBL" + version
#              and the RAM window the bootloader accepts
#           2. write: send the RAM image in 1 KB blocks ('W' addr len, wait
#              for 'K', data, CRC-32, wait for 'K' crc)
#           3. verify (optional, default on): read every block back ('R') and
#              compare
#           4. go: 'G' entry, wait for 'K'; then (with --term) print what the
#              program sends until Ctrl-C, --expect text appears, or --timeout
#           Exit code 0 on success; with --expect, 0 only if the text arrived.
# Ports   : --port COM5 (Windows), /dev/ttyUSB1 (Linux), 'auto' to find the
#           board by pinging every serial port, or 'sim' for the
#           software board model (model/board_model.py, no hardware needed).
#           A real port needs pyserial:  py -m pip install pyserial
# Also    : --emit-stream FILE writes the exact byte stream, with the pauses
#           the bootloader needs between replies, for the RTL testbench
#           (sim/tb/tb_soc.v +uartin=FILE). No port is opened then.
# Usage   : py host/rvload.py sw/prebuilt/hello.elf --port auto --term
# =============================================================================
import argparse
import json
import os
import struct
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
import elf as elf_mod   # noqa: E402

CFG = json.load(open(os.path.join(HERE, "soc_params.json")))
BLOCK = 1024


class ProtocolError(Exception):
    pass


# -----------------------------------------------------------------------------
# transports
# -----------------------------------------------------------------------------
class SerialPort(object):
    def __init__(self, name, baud):
        try:
            import serial
        except ImportError:
            raise SystemExit("pyserial is missing: py -m pip install pyserial")
        self.s = serial.Serial(name, baud, timeout=0.2)
        self.s.reset_input_buffer()

    def write(self, b):
        self.s.write(b)

    def read(self, n, timeout=2.0):
        out = bytearray()
        end = time.time() + timeout
        while len(out) < n and time.time() < end:
            out += self.s.read(n - len(out))
        return bytes(out)

    def read_any(self):
        return self.s.read(self.s.in_waiting or 1)


class SimPort(object):
    """The software board: ISS running the real boot ROM image."""

    def __init__(self, boot_elf=None):
        import board_model
        self.b = board_model.BoardModel(boot_elf) if boot_elf else board_model.BoardModel()

    def write(self, b):
        self.b.write(b)

    def read(self, n, timeout=2.0):
        return self.b.read(n, budget=int(2e6 * max(timeout, 0.5)))

    def read_any(self):
        return self.b.drain(20000)


class StreamWriter(object):
    """Records the byte stream for the RTL testbench instead of talking."""

    def __init__(self, cpu_hz, baud):
        self.entries = []
        self.bit_cycles = cpu_hz // baud

    def write(self, b):
        self.entries += list(bytearray(b))

    def expect_reply(self, nbytes):
        # The bootloader is transmitting nbytes; wait for them (10 bits each)
        # plus margin, so the next command does not overrun its 1-byte buffer.
        cycles = (nbytes + 2) * 10 * self.bit_cycles + 20000
        while cycles > 0:
            step = min(cycles, 0x7FFF * 1024)
            self.entries.append(0x8000 | ((step + 1023) // 1024))
            cycles -= step

    def save(self, path):
        with open(path, "w", newline="\n") as fh:
            fh.write("// rvload.py --emit-stream: byte < 0x100, 0x8000|n = pause n*1024 cycles\n")
            for e in self.entries:
                fh.write("%04x\n" % e)


# -----------------------------------------------------------------------------
# protocol
# -----------------------------------------------------------------------------
def u32(b):
    return struct.unpack("<I", b)[0]


def expect_ok(port, what):
    r = port.read(1, timeout=3.0)
    if r == b"K":
        return
    if r == b"E":
        code = port.read(1)
        raise ProtocolError("%s: bootloader error %r" % (what, code))
    raise ProtocolError("%s: no reply (got %r)" % (what, r))


def ping(port, tries=5):
    for _ in range(tries):
        port.write(b"P")
        buf = b""
        end = time.time() + 2.0
        while time.time() < end:
            buf += port.read(1, timeout=0.5)
            i = buf.find(b"KRVBL")
            if i >= 0:
                rest = buf[i + 5:] + port.read(13 - len(buf[i + 5:]), timeout=2.0)
                ver = rest[0]
                base, size, limit = struct.unpack("<III", rest[1:13])
                return ver, base, size, limit
    raise ProtocolError("no answer to ping: is the FPGA programmed and the right port open?")


def find_port(baud, log=print):
    """--port auto: try each USB serial port (the board's FTDI ports first) and
    return the name of the one where the bootloader answers a ping."""
    try:
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial is missing: py -m pip install pyserial")
    ports = sorted(list_ports.comports(), key=lambda p: (p.vid != 0x0403, p.device), reverse=False)
    if not ports:
        raise SystemExit("no serial ports found: is the board on and the cable in J6 PROG/UART?")
    for p in ports:
        try:
            sp = SerialPort(p.device, baud)
        except Exception as e:      # busy (another terminal) or not a UART
            log("  %s: cannot open (%s)" % (p.device, str(e).splitlines()[0][:60]))
            continue
        try:
            ping(sp, tries=2)
            log("  %s: bootloader answered" % p.device)
            sp.s.close()
            return p.device
        except ProtocolError:
            log("  %s: no bootloader" % p.device)
            sp.s.close()
    raise SystemExit("no port answered. Program the FPGA (fpga\\program.bat), press CPU_RESET, close any "
                     "terminal program, and make sure SW15 is down.")


def open_port(name, baud, log=print):
    """'sim' = software board, 'auto' = search, else a port name."""
    if name == "sim":
        return SimPort()
    if name == "auto":
        log("searching for the board ...")
        name = find_port(baud, log)
    return SerialPort(name, baud)


def ram_image(elf_path, base_ok, limit):
    e = elf_mod.load(elf_path)
    segs = []
    for addr, data, memsz in e.segments:
        if 0x40000000 <= addr < 0x40001000:
            continue
        if not (base_ok <= addr and addr + len(data) <= limit):
            raise SystemExit("segment 0x%08x+%d is outside the loadable RAM 0x%08x..0x%08x"
                             % (addr, len(data), base_ok, limit))
        if data:
            segs.append((addr, bytes(data)))
    return e.entry, segs


def load(port, entry, segs, verify=True, log=print):
    total = sum(len(d) for _, d in segs)
    sent = 0
    t0 = time.time()
    for addr, data in segs:
        for off in range(0, len(data), BLOCK):
            chunk = data[off:off + BLOCK]
            a = addr + off
            port.write(b"W" + struct.pack("<II", a, len(chunk)))
            expect_ok(port, "write header at 0x%08x" % a)
            crc = zlib.crc32(chunk) & 0xFFFFFFFF
            port.write(chunk + struct.pack("<I", crc))
            expect_ok(port, "write data at 0x%08x" % a)
            got = u32(port.read(4))
            if got != crc:
                raise ProtocolError("CRC echo mismatch at 0x%08x" % a)
            sent += len(chunk)
            log("\rloading %6d / %d bytes" % (sent, total), end="")
    log("  (%.1f s)" % (time.time() - t0))
    if verify:
        for addr, data in segs:
            for off in range(0, len(data), BLOCK):
                chunk = data[off:off + BLOCK]
                port.write(b"R" + struct.pack("<II", addr + off, len(chunk)))
                expect_ok(port, "read header")
                back = port.read(len(chunk), timeout=5.0)
                crc = u32(port.read(4))
                if back != chunk or crc != (zlib.crc32(chunk) & 0xFFFFFFFF):
                    raise ProtocolError("verify failed at 0x%08x" % (addr + off))
        log("verify ok")
    port.write(b"G" + struct.pack("<I", entry))
    expect_ok(port, "go")
    log("running at 0x%08x" % entry)


def emit_stream(path, entry, segs):
    w = StreamWriter(CFG["cpu_hz"], CFG["baud"])
    w.write(b"P")
    w.expect_reply(18)
    for addr, data in segs:
        for off in range(0, len(data), BLOCK):
            chunk = data[off:off + BLOCK]
            w.write(b"W" + struct.pack("<II", addr + off, len(chunk)))
            w.expect_reply(1)
            w.write(chunk + struct.pack("<I", zlib.crc32(chunk) & 0xFFFFFFFF))
            w.expect_reply(5)
    w.write(b"G" + struct.pack("<I", entry))
    w.expect_reply(1)
    w.save(path)
    print("stream: %d entries -> %s" % (len(w.entries), path))


def terminal(port, expect=None, timeout=None):
    seen = b""
    end = time.time() + timeout if timeout else None
    try:
        while True:
            b = port.read_any()
            if b:
                sys.stdout.write(b.decode("latin-1"))
                sys.stdout.flush()
                seen += b
                if expect and expect.encode() in seen:
                    return True
            if end and time.time() > end:
                return expect is None
    except KeyboardInterrupt:
        return expect is None


def main():
    ap = argparse.ArgumentParser(description="nexys_rv32 UART loader")
    ap.add_argument("program", help="ELF built by sw/build.py")
    ap.add_argument("--port", help="COMn, /dev/ttyUSBn, 'auto' (search) or 'sim' (software board)")
    ap.add_argument("--baud", type=int, default=CFG["baud"])
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--term", action="store_true", help="show program output after starting it")
    ap.add_argument("--expect", help="with --term: stop with success when this text appears")
    ap.add_argument("--timeout", type=float, help="with --term: stop after this many seconds")
    ap.add_argument("--emit-stream", metavar="FILE")
    a = ap.parse_args()

    base = CFG["ram_base"]
    limit = CFG["ram_base"] + CFG["ram_size"] - CFG["boot_stack"]
    if a.emit_stream:
        entry, segs = ram_image(a.program, base, limit)
        emit_stream(a.emit_stream, entry, segs)
        return 0
    if not a.port:
        raise SystemExit("--port is required (e.g. --port auto, --port COM5, or --port sim)")
    port = open_port(a.port, a.baud)
    ver, rbase, rsize, rlimit = ping(port)
    print("bootloader v%d, RAM 0x%08x + %d, loadable up to 0x%08x" % (ver, rbase, rsize, rlimit))
    entry, segs = ram_image(a.program, rbase, rlimit)
    load(port, entry, segs, verify=not a.no_verify)
    if a.term or a.expect:
        ok = terminal(port, a.expect, a.timeout)
        print("")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProtocolError as e:
        sys.exit("rvload: " + str(e))
