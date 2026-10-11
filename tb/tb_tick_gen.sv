`timescale 1ns/1ps

module tb_tick_gen;

    logic clk;
    logic rst_n;
    logic tick_div5;
    logic tick_div2;
    logic tick_div1;
    integer cycle;

    tick_gen #(
        .DIV(1)
    ) dut_div1 (
        .clk(clk),
        .rst_n(rst_n),
        .tick(tick_div1)
    );

    tick_gen #(
        .DIV(2)
    ) dut_div2 (
        .clk(clk),
        .rst_n(rst_n),
        .tick(tick_div2)
    );

    tick_gen #(
        .DIV(5)
    ) dut_div5 (
        .clk(clk),
        .rst_n(rst_n),
        .tick (tick_div5)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("results/tick_gen.vcd");
        $dumpvars(0, tb_tick_gen);

        rst_n = 1'b0;
        repeat (2) @(negedge clk);

        if (tick_div5 !== 1'b0)
            $fatal(1, "DIV RESET FAILED: tick=%b", tick_div5);
        
        if (tick_div1 !== 1'b0)
            $fatal(1, "DIV1 RESET FAILED: tick=%b", tick_div1);

        if (tick_div2 !== 1'b0)
            $fatal(1, "DIV2 RESET FAILED: tick=%b", tick_div2);

        rst_n = 1'b1;

        for (cycle = 1; cycle <= 12; cycle = cycle + 1) begin
            @(negedge clk);

            if (tick_div1 !== 1'b1)
                $fatal(
                    1,
                    "DIV1 FAILED at cycle %0d: tick=%b expected=1",
                    cycle,
                    tick_div1
                );

            if (tick_div2 !== ((cycle % 2) == 0))
                $fatal(
                    1,
                    "DIV2 FAILED at cycle %0d: tick=%b expected=%b",
                    cycle,
                    tick_div2,
                    ((cycle % 2) == 0)
                );

            if (tick_div5 !== ((cycle % 5) == 0))
                $fatal(
                    1,
                    "DIV FAILED at cycle %0d: tick=%b expected=%b",
                    cycle,
                    tick_div5,
                    ((cycle % 5) == 0)
                );
        end

        $display("DIV1 PASS");
        $display("DIV2 PASS");
        $display("DIV5 PASS");
        $display("TICK_GEN ALL PASS");

        $finish;
    end

endmodule