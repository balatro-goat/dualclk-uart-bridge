import cocotb
import random

from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ClockCycles, RisingEdge, Timer

CLK_PERIOD_NS = 10
RX_TICK_DIV = 2
BIT_TIME_NS = CLK_PERIOD_NS * RX_TICK_DIV * 16

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

# 正常接收：发送 00/FF/55/AA/A3/34，检查每次 byte_valid 对应的字节正确且没有帧错误。
@cocotb.test()
async def test_uart_rx_normal_frame(dut):
    cocotb.start_soon(
        Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start()
    )

    dut.rst_n.value = 0
    dut.rxd.value = 1
    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    test_bytes = [0x00, 0xFF, 0x55, 0xAA, 0xA3, 0x34]

    for expected in test_bytes:
        send_task = cocotb.start_soon(
            send_uart_byte(dut, expected)
        )
    
        await RisingEdge(dut.byte_valid)

        assert int(dut.byte_data.value) == expected, (
            f"DATA FAILED: got=0x{int(dut.byte_data.value):02X},"
            f"expected=0x{expected:02X}"
        )

        assert int(dut.frame_error.value) == 0, (
            f"UNEXPECTED FRAME ERROR for 0x{expected:02X}"
        )

        await FallingEdge(dut.byte_valid)
        await send_task

# 坏停止位：发送停止位为 0 的 5A，检查报错当时 byte_valid=0；本用例未长时间观察后续假字节。
@cocotb.test()
async def test_uart_rx_bad_stop_bit(dut):
    cocotb.start_soon(
        Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start()
    )

    dut.rst_n.value = 0
    dut.rxd.value = 1
    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    send_task = cocotb.start_soon(
        send_uart_byte(dut, 0x5A, stop_bit=0)
    )

    await RisingEdge(dut.frame_error)

    assert int(dut.byte_valid.value) == 0, (
        "BAD STOP BIT incorrectly produced byte_valid"
    )

    await FallingEdge(dut.frame_error)
    await send_task

# 随机起始相位：将起始位相对时钟偏移 1~9ns，发送 8 个随机字节，检查接收内容及帧错误。
@cocotb.test()
async def test_uart_rx_random_start_phase(dut):
    cocotb.start_soon(
        Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start()
    )

    dut.rst_n.value = 0
    dut.rxd.value = 1
    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # 固定种子让随机测试可以重复复现
    rng = random.Random(20260912)

    for case_index in range(8):
        expected = rng.randrange(0x100)
        phase_ns = rng.randrange(1, CLK_PERIOD_NS)

        # 先对齐到上升沿，再故意偏移1～9ns
        await RisingEdge(dut.clk)
        await Timer(phase_ns, unit="ns")

        send_task = cocotb.start_soon(
            send_uart_byte(dut, expected)
        )

        await RisingEdge(dut.byte_valid)

        assert int(dut.byte_data.value) == expected, (
            f"RANDOM PHASE CASE {case_index} FAILED: "
            f"phase={phase_ns}ns, "
            f"got=0x{int(dut.byte_data.value):02X}, "
            f"expected=0x{expected:02X}"
        )

        assert int(dut.frame_error.value) == 0, (
            f"RANDOM PHASE CASE {case_index}: "
            f"phase={phase_ns}ns produced frame_error"
        )

        await FallingEdge(dut.byte_valid)
        await send_task

# 位时间偏差：分别用标称位时间的 98% 和 102% 发送 69/96，检查这两组场景仍可正确接收。
@cocotb.test()
async def test_uart_rx_baud_tolerance(dut):
    cocotb.start_soon(
        Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start()
    )

    dut.rst_n.value = 0
    dut.rxd.value = 1
    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    test_cases = [
        (0x69, BIT_TIME_NS * 0.98, "2% fast"),
        (0x96, BIT_TIME_NS * 1.02, "2% slow"),
    ]

    for expected, tx_bit_time_ns, description in test_cases:
        await Timer(3, unit="ns")
        
        send_task = cocotb.start_soon(
            send_uart_byte(
                dut,
                expected, 
                bit_time_ns=tx_bit_time_ns
            )
        )

        await RisingEdge(dut.byte_valid)

        assert int(dut.byte_data.value) == expected, (
            f"{description} FAILED: "
            f"got=0x{int(dut.byte_data.value):02X}, "
            f"expected=0x{expected:02X}"
        )

        assert int(dut.frame_error.value) == 0, (
            f"{description} produced frame_error"
        )

        await FallingEdge(dut.byte_valid)
        await send_task

# 接收中复位：D6 发送途中复位并放弃该帧，释放复位后重新发送 A5，检查可以恢复正常接收。
@cocotb.test()
async def test_uart_rx_reset_mid_frame(dut):
    cocotb.start_soon(
        Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start()
    )

    dut.rst_n.value = 0
    dut.rxd.value = 1
    await ClockCycles(dut.clk, 2)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    interrupted_task = cocotb.start_soon(
        send_uart_byte(dut, 0xD6)
    )

    await Timer(BIT_TIME_NS * 3.5, unit="ns")

    dut.rst_n.value = 0

    await interrupted_task
    await ClockCycles(dut.clk, 2)

    assert int(dut.byte_valid.value) == 0, (
        "RESET MID-FRAME incorrectly produced byte_valid"
    )

    assert int(dut.frame_error.value) == 0, (
        "RESET MID-FRAME incorrectly produced frame_error"
    )

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    recovery_task = cocotb.start_soon(
        send_uart_byte(dut, 0xA5)
    )

    await RisingEdge(dut.byte_valid)

    assert int(dut.byte_data.value) == 0xA5, (
        f"RECOVERY FAILED: "
        f"got=0x{int(dut.byte_data.value):02X}, "
        "expected=0xA5"
    )

    assert int(dut.frame_error.value) == 0, (
        "RECOVERY produced frame_error"
    )

    await FallingEdge(dut.byte_valid)
    await recovery_task
    
