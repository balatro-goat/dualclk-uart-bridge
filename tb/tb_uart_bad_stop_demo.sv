`timescale 1ns/1ps

module tb_uart_bad_stop_demo;

    localparam integer BIT_TIME_NS = 320;

    logic clk = 1'b0;
    logic rst_n;
    logic rxd;

    logic [7:0] byte_data;
    logic byte_valid;
    logic frame_error;

    logic [7:0] tx_data;
    integer error_count = 0;
    integer valid_count = 0;

    uart_rx #(
        .RX_TICK_DIV(2)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .rxd(rxd),
        .byte_data(byte_data),
        .byte_valid(byte_valid),
        .frame_error(frame_error)
    );

    always #5 clk = ~clk;

    always @(posedge clk) begin
        #1;

        if (rst_n) begin
            if (frame_error) begin
                error_count = error_count + 1;
                $display("[%0.0f ns] frame_error=1", $realtime);
            end

            if (byte_valid) begin
                valid_count = valid_count + 1;
                $display("[%0.0f ns] byte_valid=1, data=%02h",
                         $realtime, byte_data);
            end
        end
    end

    initial begin
        $dumpfile("results/uart_bad_stop_demo.vcd");
        $dumpvars(0, tb_uart_bad_stop_demo);

        rst_n = 1'b0;
        rxd = 1'b1;
        tx_data = 8'hA5;

        #40;
        rst_n = 1'b1;

        #33;

        rxd = 1'b0;
        #(BIT_TIME_NS);

        for (integer i = 0; i < 8; i = i + 1) begin
            rxd = tx_data[i];
            #(BIT_TIME_NS);
        end


        rxd = 1'b0;
        #(BIT_TIME_NS);

        rxd = 1'b1;
        #(12 * BIT_TIME_NS);

        $display("SUMMARY: errors=%0d, valid_bytes=%0d",
                 error_count, valid_count);
        $display("Expected for correct behavior: errors=1, valid_bytes=0");

        $finish;
    end

endmodule