import cocotb
import random

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer
from collections import deque

WR_CLK_PERIOD_NS = 10
RD_CLK_PERIOD_NS = 14

async def reset_fifo(dut):
    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0

    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.rd_en.value = 0

    await ClockCycles(dut.wr_clk, 3)
    await ClockCycles(dut.rd_clk, 3)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

# 复位为空：检查 full=0、empty=1、rd_valid=0。
@cocotb.test()
async def test_fifo_empty_reset(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    assert int(dut.full.value) == 0, (
        "RESET FAILED: full should be 0"
    )

    assert int(dut.empty.value) == 1, (
        "RESET FAILED: empty should be 1"
    )

    assert int(dut.rd_valid.value) == 0, (
        "RESET FAILED: rd_valid should be 0"
    )

# 单字节读写：写入 A5，等待跨域可见后读出，检查数据正确、重新为空且 rd_valid 仅保持一拍。
@cocotb.test()
async def test_fifo_single_write_read(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    expected = 0xA5

    await FallingEdge(dut.wr_clk)

    dut.wr_data.value = expected
    dut.wr_en.value = 1

    await RisingEdge(dut.wr_clk)

    await FallingEdge(dut.wr_clk)
    dut.wr_en.value = 0

    for _ in range(8):
        await FallingEdge(dut.rd_clk)

        if int(dut.empty.value) == 0:
            break
        
    assert int(dut.empty.value) == 0, (
        "FIFO stayed empty after one write"
    )

    dut.rd_en.value = 1

    await RisingEdge(dut.rd_clk)

    await FallingEdge(dut.rd_clk)
    dut.rd_en.value = 0

    assert int(dut.rd_valid.value) == 1, (
        "READ FAILED: rd_valid should be 1"
    )

    assert int(dut.rd_data.value) == expected, (
        f"READ FAILED: got=0x{int(dut.rd_data.value):02X}, "
        f"expected=0x{expected:02X}"
    )

    assert int(dut.empty.value) == 1, (
        "FIFO should be empty after reading its only byte"
    )
    
    await RisingEdge(dut.rd_clk)
    await FallingEdge(dut.rd_clk)

    assert int(dut.rd_valid.value) == 0, (
        "rd_valid should only last for one read cycle"
    )

# 满后拒写：写满 16 项再请求写 EE，检查 full 和写指针不变；本用例未排空核对原存储内容。
@cocotb.test()
async def test_fifo_full_and_reject_write(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    depth = 16

    for value in range(depth):
        await FallingEdge(dut.wr_clk)

        assert int(dut.full.value) == 0, (
            f"FIFO became full too early before write {value}"
        )

        dut.wr_data.value = value
        dut.wr_en.value = 1

        await RisingEdge(dut.wr_clk)
        await FallingEdge(dut.wr_clk)

        dut.wr_en.value = 0

    assert int(dut.full.value) == 1, (
        "FIFO did not become full after 16 writes"
    )

    pointer_before = int(dut.wbin.value)

    dut.wr_data.value = 0xEE
    dut.wr_en.value = 1

    await RisingEdge(dut.wr_clk)
    await FallingEdge(dut.wr_clk)

    dut.wr_en.value = 0

    assert int(dut.full.value) == 1, (
        "FIFO unexpectedly left full state"
    )

    assert int(dut.wbin.value) == pointer_before, (
        "Write pointer moved while FIFO was full"
    )

# 空时拒读：空 FIFO 收到读请求，检查读指针和输出数据不变、rd_valid 不产生。
@cocotb.test()
async def test_fifo_reject_read_when_empty(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    pointer_before = int(dut.rbin.value)
    data_before = int(dut.rd_data.value)

    await FallingEdge(dut.rd_clk)
    dut.rd_en.value = 1

    await RisingEdge(dut.rd_clk)
    await FallingEdge(dut.rd_clk)

    dut.rd_en.value = 0

    assert int(dut.empty.value) == 1, (
        "Empty FIFO unexpectedly left empty state"
    )

    assert int(dut.rbin.value) == pointer_before, (
        "Read pointer moved while FIFO was empty"
    )

    assert int(dut.rd_valid.value) == 0, (
        "Empty read incorrectly produced rd_valid"
    )

    assert int(dut.rd_data.value) == data_before, (
        "rd_data changed after rejected empty read"
    )

async def fifo_write_byte(dut, value):
    for _ in range(16):
        await FallingEdge(dut.wr_clk)

        if int(dut.full.value) == 0:
            break
        
    assert int(dut.full.value) == 0, (
        "Timed out waiting for FIFO write space"
    )

    dut.wr_data.value = value
    dut.wr_en.value = 1

    await RisingEdge(dut.wr_clk)
    await FallingEdge(dut.wr_clk)

    dut.wr_en.value = 0

async def fifo_read_byte(dut):
    for _ in range(16):
        await FallingEdge(dut.rd_clk)

        if int(dut.empty.value) == 0:
            break
        
    assert int(dut.empty.value) == 0, (
        "Timed out waiting for FIFO read data"
    )

    dut.rd_en.value = 1

    await RisingEdge(dut.rd_clk)
    await FallingEdge(dut.rd_clk)

    dut.rd_en.value = 0

    assert int(dut.rd_valid.value) == 1, (
        "Accepted read did not produce rd_valid"
    )

    return int(dut.rd_data.value)

# 指针回绕：分 4 批各写后读 8 项，总计传输 32 项，检查地址循环使用时仍保持内容和顺序。
@cocotb.test()
async def test_fifo_multiple_wraps(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    for batch_start in range(0, 32, 8):
        batch = list(range(batch_start, batch_start + 8))

        for value in batch:
            await fifo_write_byte(dut, value)

        for expected in batch:
            actual = await fifo_read_byte(dut)

            assert actual == expected, (
                f"WRAP FAILED: got=0x{actual:02X}, "
                f"expected=0x{expected:02X}"
            )

    assert int(dut.empty.value) == 1, (
        "FIFO should be empty after all wraparound reads"
    )

# 写快读慢：写时钟 8ns、读时钟 20ns，并发传输 40 项，满时等待，核对最终读取列表。
@cocotb.test()
async def test_fifo_write_fast_read_slow(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, 8, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, 20, unit="ns").start()
    )

    await reset_fifo(dut)

    expected_values = list(range(40))
    received_values = []

    async def writer():
        for value in expected_values:
            await fifo_write_byte(dut, value)
    
    async def reader():
        for _ in expected_values:
            value = await fifo_read_byte(dut)
            received_values.append(value)

    writer_task = cocotb.start_soon(writer())
    reader_task = cocotb.start_soon(reader())

    await writer_task
    await reader_task

    assert received_values == expected_values, (
        f"WRITE-FAST FAILED:\n"
        f"received={received_values}\n"
        f"expected={expected_values}"
    )

# 读快写慢：写时钟 20ns、读时钟 8ns，并发传输 40 项，空时等待，核对最终读取列表。
@cocotb.test()
async def test_fifo_read_fast_write_slow(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, 20, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, 8, unit="ns").start()
    )

    await reset_fifo(dut)

    expected_values = list(range(40))
    received_values = []

    async def writer():
        for value in expected_values:
            await fifo_write_byte(dut, value)

    async def reader():
        for _ in expected_values:
            value = await fifo_read_byte(dut)
            received_values.append(value)

    writer_task = cocotb.start_soon(writer())
    reader_task = cocotb.start_soon(reader())

    await writer_task
    await reader_task

    assert received_values == expected_values, (
        f"READ-FAST FAILED:\n"
        f"received={received_values}\n"
        f"expected={expected_values}"
    )

# 随机读写：独立随机读写间隔与 64 个随机数据，用队列逐项比较实际读取内容及顺序。
@cocotb.test()
async def test_fifo_random_scoreboard(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, 10, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, 17, unit="ns").start()
    )

    await reset_fifo(dut)

    data_rng = random.Random(20260918)
    writer_rng = random.Random(1001)
    reader_rng = random.Random(2002)

    test_values = [
        data_rng.randrange(256)
        for _ in range(64)
    ]

    expected_queue = deque()

    async def writer():
        for value in test_values:
            await ClockCycles(
                dut.wr_clk,
                writer_rng.randrange(1,4)
            )

            await fifo_write_byte(dut, value)

            expected_queue.append(value)

    async def reader():
        for read_index in range(len(test_values)):
            await ClockCycles(
                dut.rd_clk,
                reader_rng.randrange(1, 5)
            )

            actual = await fifo_read_byte(dut)

            assert len(expected_queue) > 0, (
                "SCOREBOARD FAILED: "
                "FIFO produced data with no expected byte"
            )

            expected = expected_queue.popleft()

            assert actual == expected, (
                f"SCOREBOARD FAILED at read {read_index}: "
                f"got=0x{actual:02X}, "
                f"expected=0x{expected:02X}"
            )
        
    writer_task = cocotb.start_soon(writer())   
    reader_task = cocotb.start_soon(reader())

    await writer_task
    await reader_task

    assert len(expected_queue) == 0, (
        f"SCOREBOARD FAILED: "
        f"{len(expected_queue)} expected bytes were never read"
    )

# 有数据时复位：先存 6 项再异步复位，检查旧数据不再可读，复位后新写入的 3 项能正常读出。
@cocotb.test()
async def test_fifo_reset_mid_activity(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, WR_CLK_PERIOD_NS, unit="ns").start()
    )

    cocotb.start_soon(
        Clock(dut.rd_clk, RD_CLK_PERIOD_NS, unit="ns").start()
    )

    await reset_fifo(dut)

    old_values = [0x10, 0x11, 0x12, 0x13, 0x14, 0x15]

    for value in old_values:
        await fifo_write_byte(dut, value)

    await Timer(3, unit="ns")

    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0

    await Timer(1, unit="ns")

    assert int(dut.full.value) == 0, (
        "MID-RESET FAILED: full should clear immediately"
    )

    assert int(dut.empty.value) == 1, (
        "MID-RESET FAILED: empty should assert immediately"
    )

    assert int(dut.rd_valid.value) == 0, (
        "MID-RESET FAILED: rd_valid should clear immediately"
    )

    assert int(dut.wbin.value) == 0, (
        "MID-RESET FAILED: write pointer did not clear"
    )

    assert int(dut.rbin.value) == 0, (
        "MID-RESET FAILED: read pointer did not clear"
    )

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    assert int(dut.empty.value) == 1, (
        "FIFO exposed old data after reset"
    )

    assert int(dut.rd_valid.value) == 0, (
        "FIFO produced stale rd_valid after reset"
    )

    new_values = [0xA5, 0x5A, 0xC3]

    for value in new_values:
        await fifo_write_byte(dut, value)

    for expected in new_values:
        actual = await fifo_read_byte(dut)

        assert actual == expected, (
            f"RESET RECOVERY FAILED: "
            f"got=0x{actual:02X}, "
            f"expected=0x{expected:02X}"
        )

    assert int(dut.empty.value) == 1, (
        "FIFO should be empty after reset recovery reads"
    )
