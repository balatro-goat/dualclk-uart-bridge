import cocotb, random

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge

# 始终准备好：消费端 ready=1，向 FIFO 写入 A5/5A/C3，检查 adapter 按顺序输出这 3 个字节。
@cocotb.test()
async def test_always_ready(dut):
    cocotb.start_soon(
        Clock(dut.wr_clk, 10, unit="ns").start()
    )
    cocotb.start_soon(
        Clock(dut.rd_clk, 14, unit="ns").start()
    )

    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.out_ready.value = 1

    await ClockCycles(dut.wr_clk, 3)
    await ClockCycles(dut.rd_clk, 3)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    expected = [0xA5, 0x5A, 0xC3]
    received = []

    async def collect_outputs():
        for _ in range(80):
            await FallingEdge(dut.rd_clk)

            if int(dut.out_valid.value) == 1:
                received.append(int(dut.out_data.value))

                if len(received) == len(expected):
                    return

        assert False, "Timed out waiting for adapter output"

    collector = cocotb.start_soon(collect_outputs())

    for value in expected:
        await FallingEdge(dut.wr_clk)
        dut.wr_data.value = value
        dut.wr_en.value = 1

        await RisingEdge(dut.wr_clk)
        await FallingEdge(dut.wr_clk)
        dut.wr_en.value = 0
    
    await collector

    assert received == expected, (
        f"ALWAYS READY FAILED: "
        f"received={received}, expected={expected}"
    )

# 随机背压：写入 8 项并随机切换 ready，检查未交付数据保持不变，恢复后逐项交付。
@cocotb.test()
async def test_random_backpressure(dut):
    cocotb.start_soon(Clock(dut.wr_clk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rd_clk, 14, unit="ns").start())

    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.out_ready.value = 0

    await ClockCycles(dut.wr_clk, 3)
    await ClockCycles(dut.rd_clk, 3)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    expected = [0xA5, 0x5A, 0xC3, 0x00, 0xFF, 0x12, 0x80, 0x7E]
    received = []
    stalled_data = None
    stall_cycles = 0
    rng = random.Random(12)

    async def write_bytes():
        for value in expected:
            await FallingEdge(dut.wr_clk)
            dut.wr_data.value = value
            dut.wr_en.value = 1

            await RisingEdge(dut.wr_clk)
            await FallingEdge(dut.wr_clk)
            dut.wr_en.value = 0
        
    writer = cocotb.start_soon(write_bytes())

    for cycle in range(300):
        await FallingEdge(dut.rd_clk)

        ready = 0 if cycle < 20 else rng.randint(0, 1)
        dut.out_ready.value = ready

        valid = int(dut.out_valid.value)
        data = int(dut.out_data.value) if valid else None

        if stalled_data is not None:
            assert valid == 1 and data == stalled_data, (
                f"DATA CHANGED DURING STALL: "
                f"previous={stalled_data}, now={data}, valid={valid}"
            )
        
        if valid and not ready:
            stalled_data = data
            stall_cycles += 1

        await RisingEdge(dut.rd_clk)

        if valid and ready:
            received.append(data)
            stalled_data = None

            if len(received) == len(expected):
                break
    else:
        assert False, f"Timed out: received={received}"

    await writer

    assert stall_cycles > 0, "Test never exercised backpressure"
    assert received == expected, (
        f"BACKPRESSURE FAILED: received={received}, expected={expected}"
    )

# 长时间暂停：持有首字节期间停收 50 拍，检查 valid/data 保持且不再请求读 FIFO，恢复后收到两项。
@cocotb.test()
async def test_long_stall_recovery(dut):
    cocotb.start_soon(Clock(dut.wr_clk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rd_clk, 14, unit="ns").start())

    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.out_ready.value = 0

    await ClockCycles(dut.wr_clk, 3)
    await ClockCycles(dut.rd_clk, 3)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    expected = [0x3C, 0xA7]

    for value in expected:
        await FallingEdge(dut.wr_clk)
        dut.wr_data.value = value
        dut.wr_en.value = 1

        await RisingEdge(dut.wr_clk)
        await FallingEdge(dut.wr_clk)
        dut.wr_en.value = 0

    for _ in range(40):
        await FallingEdge(dut.rd_clk)
        if int(dut.out_valid.value) == 1:
            break
    else:
        assert False, "First byte did not appear"

    assert int(dut.out_data.value) == expected[0], (
        "First output byte is incorrect"
    )

    for _ in range(50):
        await FallingEdge(dut.rd_clk)

        assert int(dut.out_valid.value) == 1, (
            "out_valid disappeared during stall"
        )
        assert int(dut.out_data.value) == expected[0], (
            "out_data changed during stall"
        )
        assert int(dut.fifo_rd_en.value) == 0, (
            "Adapter requested another FIFO read while holding data"
        )
    
    received = []

    for _ in range(40):
        await FallingEdge(dut.rd_clk)
        dut.out_ready.value = 1

        valid = int(dut.out_valid.value)
        data = int(dut.out_data.value) if valid else None

        await RisingEdge(dut.rd_clk)

        if valid:
            received.append(data)

    assert received == expected, (
        f"LONG STALL RECOVERY FAILED: "
        f"received={received}, expected={expected}"
    )

# 连续库存：预存 1~12 后持续允许消费，检查依次交付 12 项，收完后继续观察 8 拍无额外 valid。
@cocotb.test()
async def test_continuous_fifo_data(dut):
    cocotb.start_soon(Clock(dut.wr_clk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rd_clk, 14, unit="ns").start())

    dut.wr_rst_n.value = 0
    dut.rd_rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.out_ready.value = 0

    await ClockCycles(dut.wr_clk, 3)
    await ClockCycles(dut.rd_clk, 3)

    dut.wr_rst_n.value = 1
    dut.rd_rst_n.value = 1

    await ClockCycles(dut.wr_clk, 2)
    await ClockCycles(dut.rd_clk, 2)

    expected = list(range(1, 13))

    for value in expected:
        await FallingEdge(dut.wr_clk)

        assert int(dut.full.value) == 0, (
            f"FIFO unexpectedly full before writing {value}"
        )

        dut.wr_data.value = value
        dut.wr_en.value = 1

        await RisingEdge(dut.wr_clk)
        await FallingEdge(dut.wr_clk)
        dut.wr_en.value = 0

    for _ in range(40):
        await FallingEdge(dut.rd_clk)
        if int(dut.out_valid.value) == 1:
            break
    else:
        assert False, "First output byte did not appear"

    assert int(dut.out_data.value) == expected[0], (
        "First output byte is incorrect"
    ) 

    received = []

    for _ in range(120):
        await FallingEdge(dut.rd_clk)
        dut.out_ready.value = 1

        valid = int(dut.out_valid.value)
        data = int(dut.out_data.value) if valid else None

        await RisingEdge(dut.rd_clk)

        if valid:
            expected_byte = expected[len(received)]
            assert data == expected_byte, (
                f"Wrong byte at position {len(received)}: "
                f"got={data}, expected={expected_byte}"
            )

            received.append(data)

            if len(received) == len(expected):
                break
    else:
        assert False, f"Timed out: received={received}"

    for _ in range(8):
        await FallingEdge(dut.rd_clk)
        assert int(dut.out_valid.value) == 0, (
            "Unexpected extra output after all bytes were received"
        )

    assert received == expected
