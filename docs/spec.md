# Dual-clock UART Bridge Specification

## UART RX

### Frame format

- Format: 8N1
- Idle level: 1
- Start bit: 0
- Data bits: 8
- Data order: LSB first
- Parity: none
- Stop bit: 1

### Interface

Inputs:

- `clk`: UART RX clock
- `rst_n`: active-low reset
- `rxd`: asynchronous serial input

Outputs:

- `byte_data[7:0]`: received byte
- `byte_valid`: one-cycle pulse when a valid byte is received
- `frame_error`: one-cycle pulse when the stop bit is invalid

### Sampling

- `rxd` first passes through a two-flip-flop synchronizer.
- The receiver uses a 16x sampling tick.
- The start bit is checked near its midpoint.
- Each data bit is sampled once near its midpoint.
- A valid stop bit produces `byte_valid`.
- An invalid stop bit produces `frame_error` and no valid byte.
- After an invalid stop sample, the receiver enters `S_RECOVER`, waits for
  synchronized RX to become high, then returns to `S_IDLE`. Recovery does not
  guarantee synchronization for arbitrary malformed streams without a high interval.

## Asynchronous FIFO and Output

- Default FIFO storage is 16 entries of 8 bits. The supported depth is a power
  of two, at least 4, for the implemented pointer/full comparison.
- Write and read clocks are independent. Read/write progress is communicated
  using Gray-coded pointers and two-stage synchronization into the other domain.
- A read is accepted only when `rd_en && !empty`; its registered output is
  accompanied by `rd_valid`.
- A one-entry adapter requests a FIFO read, waits for `rd_valid`, and holds
  the returned byte until the consumer accepts it.
- Consumer acceptance occurs on `clk_b` rising edges with both `out_valid`
  and `out_ready` high. During backpressure, valid and data must remain held.
- With the adapter holding one byte, FIFO storage can retain another 16 bytes.
- A correctly received UART byte is written only when the FIFO is not full.
  On full, that new byte is dropped; previously accepted data is not replaced.

## Event Reporting

- `write_accept` reports each accepted FIFO write. `write_accept_data` is an
  observation signal, not an additional byte queue.
- `overflow_drop` reports a valid UART byte rejected because of FIFO full.
- `frame_error_drop` reports an invalid UART stop sample.
- Event outputs are one-cycle pulses in the `clk_a` domain.
- `overflow_cnt` and `frame_err_cnt` are 16-bit counters that stop incrementing
  at 65535 rather than wrapping to zero. Reset clears them.

## Reset Contract

- The top level receives one global active-low reset named `rst_n`.
- The global `rst_n` may assert and deassert asynchronously to all clocks.
- Each clock domain must instantiate its own `reset_sync`.
- Domain A uses `rst_a_n`, synchronized only by `clk_a`.
- Domain B uses `rst_b_n`, synchronized only by `clk_b`.
- Synchronized resets assert asynchronously and deassert after two rising clock edges.
- Every module must use the synchronized reset belonging to its own clock domain.
- Except for `reset_sync` instances, internal modules must not directly use the global `rst_n`.
- A synchronized reset must not be shared between different clock domains.
