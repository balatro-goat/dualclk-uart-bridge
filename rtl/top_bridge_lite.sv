`timescale 1ns/1ps

module top_bridge_lite #(
    parameter integer RX_TICK_DIV = 2,
    parameter integer FIFO_DEPTH = 16
) (
    input logic clk_a,
    input logic clk_b,
    input logic rst_n,
    input logic rxd,

    output logic [7:0] out_data,
    output logic out_valid,
    input logic out_ready,

    output logic [15:0] overflow_cnt,
    output logic [15:0] frame_err_cnt,

    output logic write_accept,
    output logic [7:0] write_accept_data,
    output logic overflow_drop,
    output logic frame_error_drop
);

    logic rst_a_n;
    logic rst_b_n;

    logic [7:0] rx_byte_data;
    logic rx_byte_valid;
    logic rx_frame_error;

    logic fifo_wr_en;
    logic fifo_full;

    logic fifo_rd_en;
    logic [7:0] fifo_rd_data;
    logic fifo_rd_valid;
    logic fifo_empty;

    assign fifo_wr_en = rst_a_n && rx_byte_valid && !fifo_full;

    reset_sync u_reset_a (
        .clk(clk_a),
        .rst_n_async(rst_n),
        .rst_n_sync(rst_a_n)
    );

    reset_sync u_reset_b (
        .clk(clk_b),
        .rst_n_async(rst_n),
        .rst_n_sync(rst_b_n)
    );

    uart_rx #(
        .RX_TICK_DIV(RX_TICK_DIV)
    ) u_uart_rx (
        .clk(clk_a),
        .rst_n(rst_a_n),
        .rxd(rxd),

        .byte_data(rx_byte_data),
        .byte_valid(rx_byte_valid),
        .frame_error(rx_frame_error)
    );

    async_fifo #(
        .WIDTH(8),
        .DEPTH(FIFO_DEPTH)
    ) u_fifo (
        .wr_clk(clk_a),
        .wr_rst_n(rst_a_n),
        .wr_en(fifo_wr_en),
        .wr_data(rx_byte_data),
        .full(fifo_full),

        .rd_clk(clk_b),
        .rd_rst_n(rst_b_n),
        .rd_en(fifo_rd_en),
        .rd_data(fifo_rd_data),
        .rd_valid(fifo_rd_valid),
        .empty(fifo_empty)
    );

    fifo_read_adapter #(
        .WIDTH(8)
    ) u_read_adapter (
        .clk(clk_b),
        .rst_n(rst_b_n),

        .fifo_empty(fifo_empty),
        .fifo_rd_en(fifo_rd_en),
        .fifo_rd_valid(fifo_rd_valid),
        .fifo_rd_data(fifo_rd_data),

        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data)
    );

    always @(posedge clk_a or negedge rst_a_n) begin
        if (!rst_a_n) begin
            write_accept <= 1'b0;
            write_accept_data <= 8'h00;
            overflow_drop <= 1'b0;
            frame_error_drop <= 1'b0;

            overflow_cnt <= 16'd0;
            frame_err_cnt <= 16'd0;
        end
        else begin
            write_accept <= 1'b0;
            overflow_drop <= 1'b0;
            frame_error_drop <= 1'b0;

            if (fifo_wr_en) begin
                write_accept <= 1'b1;
                write_accept_data <= rx_byte_data;
            end
            else if (rx_byte_valid && fifo_full) begin
                overflow_drop <= 1'b1;
                
                if (overflow_cnt != 16'hffff)
                    overflow_cnt <= overflow_cnt + 16'd1;
            end

            if (rx_frame_error) begin
                frame_error_drop <= 1'b1;

                if (frame_err_cnt != 16'hffff)
                    frame_err_cnt <= frame_err_cnt + 16'd1;
            end
        end
    end

endmodule