`timescale 1ns/1ps

module tb_rxd_sync_2ff;

    logic clk;
    logic rst_n;
    logic rxd_async;
    logic rxd_sync;

    rxd_sync_2ff dut (
        .clk(clk),
        .rst_n(rst_n),
        .rxd_async(rxd_async),
        .rxd_sync(rxd_sync)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("results/rxd_sync_2ff.vcd");
        $dumpvars(0, tb_rxd_sync_2ff);

        rst_n = 1'b0;
        rxd_async = 1'b1;

        repeat (2) @(negedge clk);

        if (rxd_sync !== 1'b1)
            $fatal(
                1,
                "RESET FAILED: rxd_sync=%b expected=1",
                rxd_sync
            );
        
        $display("RESET PASS");

        rst_n = 1'b1;

        #2;
        rxd_async = 1'b0;

        @(negedge clk);

        if (
            dut.rxd_meta !== 1'b0 ||
            rxd_sync !== 1'b1
        )
            $fatal(
                1,
                "FALL STAGE 1 FAILED: meta=%b sync=%b",
                dut.rxd_meta,
                rxd_sync
            );
        
        @(negedge clk);

        if (rxd_sync !== 1'b0)
            $fatal(
                1,
                "FALL STAGE 2 FAILED: rxd_sync=%b expected=0",
                rxd_sync
            );
        
        $display("FALL PIPELINE PASS");

        #2
        rxd_async = 1'b1;

        @(negedge clk);

        if (
            dut.rxd_meta !== 1'b1 ||
            rxd_sync !== 1'b0
        )
            $fatal(
                1,
                "RISE STAGE 1 FAILED: meta=%b sync=%b",
                dut.rxd_meta,
                rxd_sync
            );
        
        @(negedge clk);

        if (rxd_sync !== 1'b1)
            $fatal(
                1,
                "RISE STAGE 2 FAILED: rxd_sync=%b expected=1",
                rxd_sync
            );
        
        $display("RISE PIPELINE PASS");
        $display("RXD SYNC ALL PASS");

        $finish;
    end

endmodule