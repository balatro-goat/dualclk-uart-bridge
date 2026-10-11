`timescale 1ns/1ps

module tb_fifo_read_adapter;
    
    logic wr_clk;
    logic rd_clk;
    logic wr_rst_n;
    logic rd_rst_n;

    logic wr_en;
    logic [7:0] wr_data;
    logic full;

    logic fifo_empty;
    logic fifo_rd_en;
    logic fifo_rd_valid;
    logic [7:0] fifo_rd_data;

    logic out_ready;
    logic out_valid;
    logic [7:0] out_data;

    async_fifo #(
        .WIDTH(8),
        .DEPTH(16)
    ) fifo (
        .wr_clk(wr_clk),
        .wr_rst_n(wr_rst_n),
        .wr_en(wr_en),
        .wr_data(wr_data),
        .full(full),

        .rd_clk(rd_clk),
        .rd_rst_n(rd_rst_n),
        .rd_en(fifo_rd_en),
        .rd_data(fifo_rd_data),
        .rd_valid(fifo_rd_valid),
        .empty(fifo_empty)
    );

    fifo_read_adapter #(
        .WIDTH(8)
    ) adapter (
        .clk(rd_clk),
        .rst_n(rd_rst_n),

        .fifo_empty(fifo_empty),
        .fifo_rd_en(fifo_rd_en),
        .fifo_rd_valid(fifo_rd_valid),
        .fifo_rd_data(fifo_rd_data),

        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data)
    );

endmodule