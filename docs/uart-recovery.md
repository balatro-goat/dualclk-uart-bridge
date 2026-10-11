# UART invalid-stop recovery

## Defect

The original receiver had IDLE, START, DATA and STOP states. After an invalid
stop sample it reported `frame_error`, suppressed `byte_valid` at that sample,
and returned directly to IDLE.

If the remaining low stop-bit tail was still visible after that return, it could
trigger a new START. For an observed timing phase, start confirmation accepted
this false start and subsequent idle-high input was sampled as eight ones.
The result was an extra valid `0xFF`, despite the original frame-error report.
This is phase-dependent, not the result of every possible malformed frame.

## Fix in the current RTL

`rtl/uart_rx.sv` now includes `S_RECOVER`. At the stop sampling tick:

```systemverilog
if (rxd_sync)
    next_state = S_IDLE;
else
    next_state = S_RECOVER;
```

RECOVER waits for `rxd_sync == 1` before returning to IDLE and clears receive
progress while waiting. It does not immediately treat the same low interval
as a new start. This is a wait-for-high policy, not a guarantee for all malformed
streams or a full bit-time qualification of the recovered high level.

## Evidence and reproduction

![Original and fixed UART recovery traces](figures/uart-recovery-interview.png)

The figure was drawn from saved original/fixed simulation observations sampled
after clock-edge updates. It is not a GTKWave screenshot or a continuous VCD.
Times are relative to the transmitted start bit. In this observed case, the
original reports an error at 3052 ns and emits FF at 6092 ns; the fixed receiver
enters RECOVER and emits no valid byte during the observed idle interval.
Clock and timing-tick tracks were omitted to make the state progression readable.

The README's standalone SV demo runs this bad-frame-then-idle stimulus on the
current fixed RTL and prints the expected `errors=1, valid_bytes=0` summary.
It also produces a full VCD for inspection. The historical unfixed version is
described here; it is not the current RTL checked into this repository.

The top-level scenario can be run separately:

```bash
source .venv/bin/activate
mkdir -p results tmp
make -C tb -f Makefile.top_bridge_lite \
  COCOTB_TESTCASE=test_bridge_bad_stop_bit WAVES=1
```

This scenario sends a bad A5, keeps the line high for one bit, then sends a valid
3C. It expects only 3C at the consumer, one frame-error count and no overflow.
It complements the standalone demo's long idle observation.

The existing UART and top-level suites are also run to check that the change
does not break their normal reception, reset and buffering scenarios. Passing
these finite checks does not prove correctness for every asynchronous phase
or every malformed input stream.
