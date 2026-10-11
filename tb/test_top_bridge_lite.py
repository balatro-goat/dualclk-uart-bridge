import random

import cocotb

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer


CLK_A_PERIOD_NS = 10
CLK_B_PERIOD_NS = 14
RX_TICK_DIV = 2
BIT_TIME_NS = CLK_A_PERIOD_NS * RX_TICK_DIV * 16

async def send_uart_byte(
    dut,
    data,
    bit_time_ns=BIT_TIME_NS,
    stop_bit=1
):
    dut.rxd.value = 0
    await Timer(bit_time_ns, unit="ns")

    for bit_index in range(8):
        dut.rxd.value = (data >> bit_index) & 1
        await Timer(bit_time_ns, unit="ns")

    dut.rxd.value = stop_bit
    await Timer(bit_time_ns, unit="ns")

    dut.rxd.value = 1

async def reset_bridge(dut):
    dut.rst_n.value = 0
    dut.rxd.value = 1
    dut.out_ready.value = 0

    await ClockCycles(dut.clk_a, 4)
    await ClockCycles(dut.clk_b, 4)

    await FallingEdge(dut.clk_a)
    dut.rst_n.value = 1

    await ClockCycles(dut.clk_a, 4)
    await ClockCycles(dut.clk_b, 4)

async def start_bridge(
    dut,
    clk_a_period_ns=CLK_A_PERIOD_NS,
    clk_b_period_ns=CLK_B_PERIOD_NS,
):
    # Start both clocks and reset the bridge.
    cocotb.start_soon(
        Clock(dut.clk_a, clk_a_period_ns, unit="ns").start()
    )
    cocotb.start_soon(
        Clock(dut.clk_b, clk_b_period_ns, unit="ns").start()
    )

    await reset_bridge(dut)


async def send_uart_bytes(dut, data_bytes):
    for data in data_bytes:
        await send_uart_byte(dut, data)


async def record_bridge_events(dut, cycles):
    events = {
        "accepted": [],
        "overflow": 0,
        "frame_error": 0,
    }

    for _ in range(cycles):
        await FallingEdge(dut.clk_a)

        accepted = int(dut.write_accept.value)
        overflow = int(dut.overflow_drop.value)
        frame_error = int(dut.frame_error_drop.value)

        assert not (accepted and overflow), (
            "A byte cannot be accepted and overflow-dropped together"
        )

        if accepted:
            data = int(dut.write_accept_data.value)
            events["accepted"].append(data)

        if overflow:
            events["overflow"] += 1

        if frame_error:
            events["frame_error"] += 1
        
    return events


async def check_bridge_output(
    dut, expected, random_backpressure=False, cycles=30000, random_seed=13
):
    # Emulate the consumer and check every transfer.
    received = []

    rng = random.Random(random_seed)

    ready = 0 if random_backpressure else 1
    remaining_cycles = 600
    stalled_data = None
    stall_cycles = 0

    # Keep observing after all expected bytes, to catch extra outputs.
    for _ in range(cycles):
        await FallingEdge(dut.clk_b)

        if random_backpressure and remaining_cycles == 0:
            if ready == 0:
                ready = 1
                remaining_cycles = rng.randint(100, 200)
            else:
                ready = 0
                remaining_cycles = rng.randint(600, 1000)

        dut.out_ready.value = ready
        if random_backpressure:
            remaining_cycles -= 1

        valid = int(dut.out_valid.value)
        data = int(dut.out_data.value) if valid else None

        if stalled_data is not None:
            assert valid == 1 and data == stalled_data, (
                f"OUTPUT CHANGED DURING STALL: "
                f"previous={stalled_data}, now={data}, valid={valid}"
            )

        if valid and not ready:
            stalled_data = data
            stall_cycles += 1

        await RisingEdge(dut.clk_b)

        if valid and ready:
            assert len(received) < len(expected), (
                f"Unexpected extra output: data=0x{data:02X}"
            )

            index = len(received)
            assert data == expected[index], (
                f"BYTE {index} FAILED: "
                f"got=0x{data:02X}, expected=0x{expected[index]:02X}"
            )

            received.append(data)
            stalled_data = None

    assert received == expected, (
        f"Missing data: received {len(received)} "
        f"of {len(expected)} bytes"
    )

    if random_backpressure:
        assert stall_cycles > 0, (
            "Test never held a valid byte under backpressure"
        )


def check_no_errors(dut):

    assert int(dut.overflow_cnt.value) == 0, (
        "Unexpected FIFO overflow"
    )

    assert int(dut.frame_err_cnt.value) == 0, (
        "Unexpected UART frame error"
    )


# 正常传输：发送 100 个合法字节，逐项检查消费者收到的内容、顺序、数量，且错误计数为 0。
@cocotb.test()
async def test_bridge_normal_frames(dut):
    await start_bridge(dut)

    await FallingEdge(dut.clk_b)
    dut.out_ready.value = 1

    expected = [0x00, 0xFF, 0x55, 0xAA] + list(range(96))
    sender = cocotb.start_soon(send_uart_bytes(dut, expected))
    await check_bridge_output(dut, expected)
    await sender
    check_no_errors(dut)


# 随机背压：消费端随机暂停/恢复，检查等待期间数据保持、恢复后有序交付且无溢出或帧错误。
@cocotb.test()
async def test_bridge_random_backpressure(dut):
    await start_bridge(dut)

    expected = [0x00, 0xFF, 0x55, 0xAA] + list(range(96))
    sender = cocotb.start_soon(send_uart_bytes(dut, expected))
    await check_bridge_output(dut, expected, random_backpressure=True)
    await sender
    check_no_errors(dut)


# 缓存溢出：暂停消费后发送 0~19，检查依次交付 0~16、丢弃 17~19，且溢出计数为 3。
@cocotb.test()
async def test_bridge_overflow(dut):
    await start_bridge(dut)

    dut.out_ready.value = 0
    sent = list(range(20))
    await send_uart_bytes(dut, sent)

    await ClockCycles(dut.clk_a, 4)
    await FallingEdge(dut.clk_a)

    assert int(dut.overflow_cnt.value) == 3, (
        f"Expected 3 dropped bytes, got {int(dut.overflow_cnt.value)}"
    )
    assert int(dut.frame_err_cnt.value) == 0, (
        "Unexpected UART frame error"
    )

    expected = sent[:17]
    await check_bridge_output(dut, expected)

    assert int(dut.overflow_cnt.value) == 3, (
        "Overflow count changed unexpectedly during draining"
    )

# 坏帧后恢复：发送坏停止位 A5，空闲一位后发送正常 3C；只允许交付 3C，并报告一次帧错误。
@cocotb.test()
async def test_bridge_bad_stop_bit(dut):
    await start_bridge(dut)

    await send_uart_byte(dut, 0xA5, stop_bit=0)

    await Timer(BIT_TIME_NS, unit="ns")

    await send_uart_byte(dut, 0x3C)

    await check_bridge_output(dut, [0x3C])

    assert int(dut.frame_err_cnt.value) == 1, (
        f"Expected 1 frame error, got {int(dut.frame_err_cnt.value)}"
    )
    assert int(dut.overflow_cnt.value) == 0, (
        "Unexpected FIFO overflow"
    )

# 中途复位：已有缓存且新帧只发了 3 个数据位时复位，检查旧数据作废、计数清零、随后可接收 5A。
@cocotb.test()
async def test_bridge_reset_mid_frame(dut):
    await start_bridge(dut)

    await send_uart_bytes(dut, [0x11, 0x22, 0x33])

    await FallingEdge(dut.clk_b)
    assert int(dut.out_valid.value) == 1, (
        "Setup failed: adapter has no pending byte"
    )
    assert int(dut.out_data.value) == 0x11, (
        "Setup failed: adapter should hold 0x11"
    )

    dut.rxd.value = 0
    await Timer(BIT_TIME_NS, unit="ns")

    for bit_index in range(3):
        dut.rxd.value = (0xA5 >> bit_index) & 1
        await Timer(BIT_TIME_NS, unit="ns")

    await reset_bridge(dut)

    await check_bridge_output(dut, [])
    check_no_errors(dut)

    sender = cocotb.start_soon(send_uart_byte(dut, 0x5A))
    await check_bridge_output(dut, [0x5A])
    await sender 
    check_no_errors(dut)

# 事件统计：暂停消费并发送 20 个好帧和 1 个坏帧，核对接受列表、3 次溢出、1 次帧错及对应计数。
@cocotb.test()
async def test_bridge_event_reports(dut):
    await start_bridge(dut)

    monitor = cocotb.start_soon(record_bridge_events(dut, 8000))

    await send_uart_bytes(dut, list(range(20)))

    await send_uart_byte(dut, 0xA5, stop_bit=0)
    await Timer(BIT_TIME_NS, unit="ns")

    events = await monitor
    expected = list(range(17))

    assert events == {
        "accepted": expected,
        "overflow": 3,
        "frame_error": 1,
    }, f"Unexpected event records: {events}"

    await check_bridge_output(dut, expected)

    assert int(dut.overflow_cnt.value) == events["overflow"], (
        "Overflow counter does not match recorded events"
    )
    assert int(dut.frame_err_cnt.value) == events["frame_error"], (
        "Frame-error counter does not match recorded events"
    )


async def run_cp14_regression(dut, clk_b_period_ns, output_cycles):
    await start_bridge(dut, clk_a_period_ns=10, clk_b_period_ns=clk_b_period_ns)

    data_rng = random.Random(20260727)
    expected = [data_rng.randrange(256) for _ in range(300)]

    monitor = cocotb.start_soon(record_bridge_events(dut, 110000))
    sender = cocotb.start_soon(send_uart_bytes(dut, expected))

    await check_bridge_output(
        dut, 
        expected,
        random_backpressure=True,
        cycles=output_cycles,
        random_seed=20260727,
    )

    await sender
    events = await monitor

    assert events["accepted"] == expected, (
        "Accepted bytes differ from the 300 sent bytes"
    )
    assert events["overflow"] == 0, (
        f"Unexpected overflow events: {events['overflow']}"
    )
    assert events["frame_error"] == 0, (
        f"Unexpected frame-error events: {events['frame_error']}"
    )

    check_no_errors(dut)

# A 时钟较快：A=10ns、B=14ns，传输 300 个固定种子随机字节并施加背压，核对输入事件和最终输出。
@cocotb.test()
async def test_cp14_a_faster_than_b(dut):
    await run_cp14_regression(
        dut,
        clk_b_period_ns=14,
        output_cycles=80000,
    )


# B 时钟较快：A=10ns、B=6ns，重复 300 字节加背压检查，验证相反时钟快慢关系下的传输。
@cocotb.test()
async def test_cp14_b_faster_than_a(dut):
    await run_cp14_regression(
        dut,
        clk_b_period_ns=6,
        output_cycles=180000,
    )


# 计数饱和：将计数预置到 FFFE，再用真实错误事件检查 FFFF 后不回绕、事件仍报告，复位可清零。
@cocotb.test()
async def test_bridge_counter_saturation(dut):
    """Deposit near the limit for a boundary test; generate errors via UART.

    This does not claim to test 65535 naturally accumulated errors.
    Deposits are not forces: subsequent RTL updates remain enabled.
    """
    await start_bridge(dut)

    async def preset_near_limit(counter):
        await FallingEdge(dut.clk_a)
        counter.value = 0xFFFE
        await Timer(1, unit="ns")
        assert int(counter.value) == 0xFFFE, "Counter deposit failed"
        await FallingEdge(dut.clk_a)
        assert int(counter.value) == 0xFFFE, "Idle counter did not hold"

    async def check_error(counter, event_name, stop_bit):
        monitor = cocotb.start_soon(record_bridge_events(dut, 400))
        if stop_bit == 0:
            sender = cocotb.start_soon(send_uart_byte(dut, 0xA5, stop_bit=0))
            # Low across the stop-bit midpoint, then high before its end.
            # Isolate counter behavior from a long-low re-trigger of RX.
            await Timer(BIT_TIME_NS * 9 + BIT_TIME_NS * 3 // 4, unit="ns")
            dut.rxd.value = 1
            await sender
        else:
            await send_uart_byte(dut, 0xA5)
        events = await monitor
        assert int(counter.value) == 0xFFFF, "Counter wrapped or failed to increment"
        assert events[event_name] == 1, f"Missing/duplicate event: {events}"
        other = "frame_error" if event_name == "overflow" else "overflow"
        assert events[other] == 0, f"Unexpected other error: {events}"
        assert events["accepted"] == [], "Error byte was incorrectly accepted"

    # One byte held by the adapter plus sixteen in the FIFO; no consumption.
    await send_uart_bytes(dut, list(range(17)))
    await ClockCycles(dut.clk_a, 4)
    await FallingEdge(dut.clk_a)
    assert int(dut.fifo_full.value) == 1, "FIFO must be full for overflow test"
    assert int(dut.overflow_cnt.value) == 0
    await preset_near_limit(dut.overflow_cnt)
    await check_error(dut.overflow_cnt, "overflow", stop_bit=1)
    await check_error(dut.overflow_cnt, "overflow", stop_bit=1)
    dut._log.info("OVERFLOW: fffe -> ffff -> ffff; both events reported")

    await reset_bridge(dut)
    await FallingEdge(dut.clk_a)
    assert int(dut.overflow_cnt.value) == 0
    assert int(dut.frame_err_cnt.value) == 0
    await preset_near_limit(dut.frame_err_cnt)
    await check_error(dut.frame_err_cnt, "frame_error", stop_bit=0)
    await check_error(dut.frame_err_cnt, "frame_error", stop_bit=0)
    dut._log.info("FRAME ERROR: fffe -> ffff -> ffff; both events reported")

    await reset_bridge(dut)
    await FallingEdge(dut.clk_a)
    assert int(dut.overflow_cnt.value) == 0
    assert int(dut.frame_err_cnt.value) == 0
    assert int(dut.overflow_drop.value) == 0
    assert int(dut.frame_error_drop.value) == 0
    dut._log.info("SATURATION RESET: counters and event outputs cleared")
