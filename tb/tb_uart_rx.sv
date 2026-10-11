`timescale 1ns/1ps

module tb_uart_rx;

    localparam integer RX_TICK_DIV = 2;
    localparam integer CLK_PERIOD_NS = 10;
    localparam integer BIT_TIME_NS = CLK_PERIOD_NS * RX_TICK_DIV * 16;

    logic clk;
    logic rst_n;
    logic rxd;

    logic [7:0] byte_data;
    logic byte_valid;
    logic frame_error;

    integer valid_count;
    logic [7:0] captured_data;

    uart_rx #(
        .RX_TICK_DIV(RX_TICK_DIV)
    ) dut (
        .clk (clk),
        .rst_n (rst_n),
        .rxd (rxd),
        .byte_data (byte_data),
        .byte_valid (byte_valid),
        .frame_error (frame_error)
    );

    initial clk = 1'b0;

    always #(CLK_PERIOD_NS / 2)
        clk = ~clk;
    
    task send_uart_byte(
        input logic [7:0] data
    );
        integer i;

        begin
            rxd = 1'd0;
            #(BIT_TIME_NS);

            for (i=0; i<8; i=i+1) begin
                rxd = data[i];
                #(BIT_TIME_NS);
            end

            rxd = 1'b1;
            #(BIT_TIME_NS);
        end

    endtask

    always @(negedge clk) begin
        if (byte_valid) begin
            valid_count = valid_count + 1;
            captured_data = byte_data;
        end

        if (frame_error)
            $fatal(
                1,
                "UNEXPECTED FRAME ERROR"
            );
    end

    initial begin
        $dumpfile("results/uart_rx.vcd");
        $dumpvars(0, tb_uart_rx);

        rst_n = 1'b0;
        rxd = 1'b1;

        valid_count = 0;
        captured_data = 8'h00;

        repeat (2) @(negedge clk);
        
        rst_n = 1'b1;

        repeat (2) @(negedge clk);

        send_uart_byte(8'h34);

        repeat (4) @(negedge clk);

        if (valid_count != 1)
            $fatal(
                1,
                "VALID COUNT FAILED: count=%0d expected=1",
                valid_count
            );

        if (captured_data !== 8'h34)
            $fatal(
                1,
                "DATA FAILED: data=%h expected=34",
                captured_data
            );

        $display(
            "UART RX NORMAL FRAME PASS: data=%h",
            captured_data
        );

        $finish;

    end

endmodule