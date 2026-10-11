# Dual-clock UART Bridge

A SystemVerilog learning project that receives UART bytes in one clock domain
and delivers them to a ready/valid consumer in another. Functional verification
uses Python/cocotb and Icarus Verilog. This is not a UVM implementation, an FPGA
board demonstration, or a production CDC sign-off result. UART TX is not included.

```text
                    clk_a                           clk_b
rxd -> 2-FF sync -> UART RX -> asynchronous FIFO -> read adapter -> consumer
                                   16 x 8 bits        1 byte       valid/ready
```

## Behavior

- UART: 8N1, LSB first, idle high. A 16x timing tick locates the start-bit
  confirmation and one sample near the midpoint of each data bit.
- The default `RX_TICK_DIV=2` with a 10 ns `clk_a` period gives a nominal
  320 ns bit time. These are simulation settings, not a standard board baud rate.
- FIFO: default depth 16, width 8. Gray-coded read/write pointers pass through
  two-stage synchronizers; byte contents are transferred through the FIFO memory.
- The adapter prefetches and holds one byte. Delivery occurs on a `clk_b` rising
  edge when `out_valid && out_ready`; a stalled output retains valid and data.
- With the consumer paused long enough for prefetch, the bridge can retain
  17 bytes: one in the adapter and 16 in the FIFO. Further valid UART bytes are
  dropped when the write side reports full.
- An invalid stop sample generates a frame-error event, not a valid byte. The
  current receiver enters `S_RECOVER` and waits for synchronized RX to return
  high before re-enabling start detection. See [the recovery bug note](docs/uart-recovery.md).
- `overflow_cnt` and `frame_err_cnt` saturate at `16'hFFFF`. Individual event
  pulses continue even after their counter saturates.
- Reset asserts asynchronously and releases through a separate reset synchronizer
  in each clock domain. Reset discards buffered/in-flight data and clears counters.

## Quick start (Ubuntu / WSL)

Tested tool versions: Python 3.10.12, Icarus Verilog 11.0 and cocotb 2.0.1.
The following commands run from the repository root:

```bash
sudo apt update
sudo apt install -y iverilog make python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p results tmp
make -C tb -f Makefile.top_bridge_lite
```

For an existing environment, activate `.venv` and skip installation. Test results
are generated under `results/`; build files are generated under `tmp/`. Neither
the virtual environment nor generated outputs are checked into Git.

### Run the module suites

```bash
make -C tb -f Makefile.uart_rx
make -C tb -f Makefile.async_fifo
make -C tb -f Makefile.fifo_read_adapter
```

### Run one scenario and generate its waveform

```bash
make -C tb -f Makefile.top_bridge_lite \
  COCOTB_TESTCASE=test_bridge_overflow WAVES=1
# Optional viewer; install gtkwave separately if needed.
gtkwave tmp/cocotb_top_bridge_lite/top_bridge_lite.fst
```

## Verification scope

Each test has a short purpose comment immediately above its `@cocotb.test()`.

| Suite | Cases | Main checks |
|---|---:|---|
| UART RX | 5 | Valid bytes, invalid stop sample, start phase, selected bit-time offsets, mid-frame reset |
| Asynchronous FIFO | 9 | Empty/full, rejected operations, wraparound, opposite clock ratios, randomized queue comparison, reset |
| Read adapter | 4 | Ordered delivery, randomized backpressure, long stall, continuous inventory |
| Top-level bridge | 9 | End-to-end data, backpressure, overflow, invalid frame, reset, event reports, clock ratios, saturation |

The top-level checker records output handshakes and compares byte content, order
and count against an expected list. It also checks stalled-data stability and
continues observing after the expected output to detect extra deliveries.
The overflow scenario sends 0 through 19 while consumption is paused: the expected
output is 0 through 16, with three dropped bytes and an overflow count of three.

Passing tests means the implemented assertions passed for the exercised inputs
and timings; it is not exhaustive verification or a coverage-percentage claim.
In particular:

- The original UART invalid-stop unit case checks the error sample but does not
  observe a long idle interval afterward. A separate SV demo below observes it.
- The FIFO full/reject case checks pointer/full protection but does not drain and
  compare all previously stored contents after the rejected write.
- The saturation test deposits counters at 65534 before real error events; it
  does not naturally accumulate 65535 errors.
- Recovery waits for a high input before returning to idle. It does not guarantee
  resynchronization for arbitrary malformed streams without a high separator.

## Standalone SV waveform demo

This small demo sends a bad A5 frame followed by idle high. It prints event counts
and produces a VCD without Python. Expected counts with the current RTL are
`errors=1, valid_bytes=0`. The demo prints counts; it is not an assertion-based test.

```bash
mkdir -p results
iverilog -g2012 -Wall -s tb_uart_bad_stop_demo \
  -o results/uart_bad_stop_demo.vvp \
  rtl/rxd_sync_2ff.sv rtl/tick_gen.sv rtl/uart_rx.sv \
  tb/tb_uart_bad_stop_demo.sv
vvp results/uart_bad_stop_demo.vvp
gtkwave results/uart_bad_stop_demo.vcd
```

Additional small SV testbenches are included for reset synchronization, RX input
synchronization, the tick generator and normal UART reception.

## Optional lint and generic synthesis

Install Verilator or Yosys separately to run these optional checks:

```bash
verilator --lint-only -Wall --top-module top_bridge_lite \
  rtl/reset_sync.sv rtl/rxd_sync_2ff.sv rtl/tick_gen.sv \
  rtl/uart_rx.sv rtl/async_fifo.sv rtl/fifo_read_adapter.sv \
  rtl/top_bridge_lite.sv
mkdir -p results
yosys -l results/top_bridge_lite_synth.log syn/top_bridge_lite.ys
```

Generic synthesis is not physical timing closure, device resource measurement,
or CDC verification. Digital simulation does not model analog metastability.

## Source map

- `rtl/`: seven bridge RTL modules.
- `tb/`: four cocotb suites and their Makefiles, the adapter wrapper, and SV demos.
- `docs/spec.md`: interface and behavior contract.
- `docs/uart-recovery.md`: the invalid-stop recovery defect and fix.
- `syn/top_bridge_lite.ys`: optional generic synthesis script.
- `requirements.txt`: pinned Python dependencies.

This is a personal learning project developed with AI-assisted explanations,
test scaffolding and documentation. No independent UVM environment or commercial
verification-tool experience is claimed.
